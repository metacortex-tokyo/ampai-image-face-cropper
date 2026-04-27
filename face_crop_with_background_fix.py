import os
import glob
import base64
import shutil
import sys
import termios
import tempfile
import tty
from datetime import datetime
import cv2
import numpy as np
from PIL import Image
import requests
from dotenv import load_dotenv
from face_crop_plus import Cropper
from tqdm import tqdm

load_dotenv()

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SKIP_FILE_NAMES = {".gitkeep", ".ds_store"}
BACKGROUND_EXPANSION_RATIO = 0.25
BACKGROUND_EXPANSION_METHOD = "inpaint"
DEFAULT_OUTPUT_WIDTH = 300
OUTPUT_WIDTH_OPTIONS = list(range(100, 1001, 100))
WEBP_QUALITY = 85
OPENAI_EXPAND_ENABLED = os.getenv("OPENAI_EXPAND_ENABLED", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_IMAGE_EDIT_MODEL = os.getenv("OPENAI_IMAGE_EDIT_MODEL", "gpt-image-1.5")
OPENAI_IMAGE_EDIT_QUALITY = os.getenv("OPENAI_IMAGE_EDIT_QUALITY", "high")
OPENAI_MAX_INPUT_LONG_SIDE = int(os.getenv("OPENAI_MAX_INPUT_LONG_SIDE", "1536"))
OPENAI_FACE_HEIGHT_RATIO_THRESHOLD = float(
    os.getenv("OPENAI_FACE_HEIGHT_RATIO_THRESHOLD", "0.52")
)
OPENAI_TOP_MARGIN_RATIO_THRESHOLD = float(
    os.getenv("OPENAI_TOP_MARGIN_RATIO_THRESHOLD", "0.08")
)
OPENAI_TOP_EXPANSION_RATIO = float(os.getenv("OPENAI_TOP_EXPANSION_RATIO", "0.35"))
OPENAI_EXPAND_PROMPT = os.getenv(
    "OPENAI_EXPAND_PROMPT",
    "Naturally extend the top of this portrait photo. Continue the hair, head, "
    "lighting, and background consistently without changing the existing face.",
)


def collect_valid_images(input_dir):
    """処理対象の画像のみを収集（隠しファイルや管理ファイルは除外）"""
    valid_images = []
    skipped_files = []

    for entry in sorted(os.listdir(input_dir)):
        full_path = os.path.join(input_dir, entry)
        if not os.path.isfile(full_path):
            continue

        lower_name = entry.lower()
        extension = os.path.splitext(lower_name)[1]

        if entry.startswith(".") or lower_name in SKIP_FILE_NAMES:
            skipped_files.append(entry)
            continue

        if extension in VALID_EXTENSIONS:
            valid_images.append(full_path)
        else:
            skipped_files.append(entry)

    return valid_images, skipped_files


def expand_background_with_reflect_padding(image, pad_x, pad_y):
    """反射パディングで背景を拡張"""
    return cv2.copyMakeBorder(
        image,
        pad_y,
        pad_y,
        pad_x,
        pad_x,
        cv2.BORDER_REFLECT_101,
    )


def expand_background_with_inpaint(image, pad_x, pad_y):
    """
    外側余白を inpaint で埋めて背景を生成する。
    まず反射で初期化してから inpaint することで、不自然な線化を抑えやすくする。
    """
    height, width = image.shape[:2]
    expanded = expand_background_with_reflect_padding(image, pad_x, pad_y)

    mask = np.zeros((height + pad_y * 2, width + pad_x * 2), dtype=np.uint8)
    # 追加された外周領域のみを inpaint 対象にする
    mask[:pad_y, :] = 255
    mask[-pad_y:, :] = 255
    mask[:, :pad_x] = 255
    mask[:, -pad_x:] = 255

    return cv2.inpaint(expanded, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)


def detect_largest_face(image):
    """OpenCVの軽量な顔検出で、生成拡張適用前の課金判定に使う。"""
    height, width = image.shape[:2]
    cascade_path = os.path.join(
        cv2.data.haarcascades,
        "haarcascade_frontalface_default.xml",
    )
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    min_size = max(30, int(min(width, height) * 0.12))
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(min_size, min_size),
    )
    if len(faces) == 0:
        return None

    x, y, face_width, face_height = max(faces, key=lambda face: face[2] * face[3])
    return {
        "x": int(x),
        "y": int(y),
        "width": int(face_width),
        "height": int(face_height),
        "image_width": int(width),
        "image_height": int(height),
        "height_ratio": face_height / height,
        "top_margin_ratio": y / height,
    }


def should_expand_with_openai(image_path):
    """顔が大きい、または上端に近い画像だけOpenAI生成拡張の候補にする。"""
    if not OPENAI_EXPAND_ENABLED:
        return False, "OPENAI_EXPAND_ENABLED is not enabled"

    if not OPENAI_API_KEY:
        return False, "OPENAI_API_KEY is missing"

    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        return False, "image could not be read"

    face = detect_largest_face(image)
    if face is None:
        return False, "face was not detected by local precheck"

    face_too_large = face["height_ratio"] >= OPENAI_FACE_HEIGHT_RATIO_THRESHOLD
    too_close_to_top = face["top_margin_ratio"] <= OPENAI_TOP_MARGIN_RATIO_THRESHOLD
    if face_too_large or too_close_to_top:
        triggers = []
        if face_too_large:
            triggers.append("large_face")
        if too_close_to_top:
            triggers.append("top_margin")
        reason = (
            f"trigger={'+'.join(triggers)}, "
            f"face_height_ratio={face['height_ratio']:.2f}, "
            f"top_margin_ratio={face['top_margin_ratio']:.2f}"
        )
        return True, reason

    reason = (
        f"below threshold: face_height_ratio={face['height_ratio']:.2f}, "
        f"top_margin_ratio={face['top_margin_ratio']:.2f}"
    )
    return False, reason


def collect_openai_expand_targets(image_paths):
    """処理開始前にOpenAI API呼び出し対象を事前集計する。"""
    targets = []
    for image_path in image_paths:
        should_expand, reason = should_expand_with_openai(image_path)
        if should_expand:
            targets.append((image_path, reason))
    return targets


def choose_openai_output_size(width, height):
    """OpenAI Images APIの対応サイズから、拡張後キャンバスに近いものを選ぶ。"""
    aspect_ratio = width / height
    if aspect_ratio < 0.8:
        return "1024x1536"
    if aspect_ratio > 1.25:
        return "1536x1024"
    return "1024x1024"


def resize_for_openai_input(source):
    """OpenAI APIに送る画像だけ長辺上限まで縮小する。"""
    if OPENAI_MAX_INPUT_LONG_SIDE <= 0:
        return source

    width, height = source.size
    long_side = max(width, height)
    if long_side <= OPENAI_MAX_INPUT_LONG_SIDE:
        return source

    scale = OPENAI_MAX_INPUT_LONG_SIDE / long_side
    resized_size = (
        max(1, int(width * scale)),
        max(1, int(height * scale)),
    )
    return source.resize(resized_size, Image.Resampling.LANCZOS)


def create_openai_outpaint_inputs(image_path, canvas_path, mask_path):
    """元画像を下寄せした透明キャンバスと、上部だけ編集するマスクを作る。"""
    source = resize_for_openai_input(Image.open(image_path).convert("RGBA"))
    width, height = source.size
    top_extension = max(1, int(height * OPENAI_TOP_EXPANSION_RATIO))
    canvas_height = height + top_extension

    canvas = Image.new("RGBA", (width, canvas_height), (0, 0, 0, 0))
    canvas.paste(source, (0, top_extension))
    canvas.save(canvas_path)

    # 透明領域を編集対象、元画像部分を保護領域として渡す。
    mask = Image.new("RGBA", (width, canvas_height), (255, 255, 255, 255))
    editable_area = Image.new("RGBA", (width, top_extension), (0, 0, 0, 0))
    mask.paste(editable_area, (0, 0))
    mask.save(mask_path)

    return width, canvas_height


def expand_top_with_openai(image_path, output_path):
    with tempfile.TemporaryDirectory() as temp_dir:
        canvas_path = os.path.join(temp_dir, "canvas.png")
        mask_path = os.path.join(temp_dir, "mask.png")
        width, height = create_openai_outpaint_inputs(
            image_path,
            canvas_path,
            mask_path,
        )
        output_size = choose_openai_output_size(width, height)

        with open(canvas_path, "rb") as canvas_file, open(mask_path, "rb") as mask_file:
            response = requests.post(
                "https://api.openai.com/v1/images/edits",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                },
                data={
                    "model": OPENAI_IMAGE_EDIT_MODEL,
                    "prompt": OPENAI_EXPAND_PROMPT,
                    "input_fidelity": "high",
                    "n": "1",
                    "output_format": "png",
                    "quality": OPENAI_IMAGE_EDIT_QUALITY,
                    "size": output_size,
                },
                files=[
                    ("image[]", ("canvas.png", canvas_file, "image/png")),
                    ("mask", ("mask.png", mask_file, "image/png")),
                ],
                timeout=180,
            )

        response.raise_for_status()
        data = response.json()
        image_b64 = data["data"][0]["b64_json"]
        with open(output_path, "wb") as output_file:
            output_file.write(base64.b64decode(image_b64))


def expand_background_for_crop(
    image_path,
    output_path,
    expansion_ratio=BACKGROUND_EXPANSION_RATIO,
    method=BACKGROUND_EXPANSION_METHOD,
):
    """
    画像の四辺を反射パディングで拡張して、切り抜き前に背景余白を作る。
    端ピクセルの単純引き伸ばし(Replicate)より、線状アーティファクトを抑制しやすい。
    """
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        shutil.copy2(image_path, output_path)
        return

    should_use_openai, reason = should_expand_with_openai(image_path)
    if should_use_openai:
        try:
            tqdm.write(
                f"OpenAI API呼び出し対象: {os.path.basename(image_path)} ({reason})"
            )
            expand_top_with_openai(image_path, output_path)
            tqdm.write(f"OpenAI生成拡張が完了: {os.path.basename(image_path)}")
            return
        except Exception as e:
            tqdm.write(
                f"OpenAI生成拡張に失敗したためローカル拡張にフォールバック: "
                f"{os.path.basename(image_path)} ({e})"
            )

    height, width = image.shape[:2]
    pad_y = max(1, int(height * expansion_ratio))
    pad_x = max(1, int(width * expansion_ratio))

    if method == "reflect":
        expanded = expand_background_with_reflect_padding(image, pad_x, pad_y)
    else:
        expanded = expand_background_with_inpaint(image, pad_x, pad_y)

    cv2.imwrite(output_path, expanded)


def prompt_output_width(default_width=DEFAULT_OUTPUT_WIDTH):
    """出力画像の横幅をCLIで選択する"""
    if not sys.stdin.isatty():
        return default_width

    selected_index = OUTPUT_WIDTH_OPTIONS.index(default_width)
    print("出力画像の横幅を選択してください。")
    print("矢印キーで選択、Enterで決定します。")

    def render_options():
        print("\r\033[K", end="")
        for index, width in enumerate(OUTPUT_WIDTH_OPTIONS):
            label = f"{width}px"
            if index == selected_index:
                label = f"[{label}]"
            print(label, end="  ")
        sys.stdout.flush()

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setraw(sys.stdin.fileno())
        render_options()

        while True:
            key = sys.stdin.read(1)
            if key in ("\r", "\n"):
                print()
                return OUTPUT_WIDTH_OPTIONS[selected_index]

            if key == "\x1b":
                sequence = sys.stdin.read(2)
                if sequence in ("[C", "[B"):
                    selected_index = min(selected_index + 1, len(OUTPUT_WIDTH_OPTIONS) - 1)
                elif sequence in ("[D", "[A"):
                    selected_index = max(selected_index - 1, 0)
                render_options()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def get_unique_output_path(path):
    """同名ファイルがある場合に連番を付けて保存先を作る"""
    if not os.path.exists(path):
        return path

    root, extension = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{root}_{counter}{extension}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def resize_image_to_width(image, width):
    """縦横比を保持して指定横幅にリサイズする"""
    height, current_width = image.shape[:2]
    if current_width == width:
        return image

    resized_height = max(1, int(height * (width / current_width)))
    interpolation = cv2.INTER_AREA if width < current_width else cv2.INTER_CUBIC
    return cv2.resize(image, (width, resized_height), interpolation=interpolation)


def convert_outputs_to_webp(output_dir, output_width, quality=WEBP_QUALITY):
    """切り抜き済み画像を指定横幅のWebPに変換してwebpディレクトリに保存する"""
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(output_dir, ext)))

    webp_dir = os.path.join(output_dir, "webp")
    os.makedirs(webp_dir, exist_ok=True)

    converted_files = []
    for image_path in tqdm(image_files, desc="WebP変換", unit="枚"):
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            tqdm.write(f"WebP変換をスキップしました: {image_path}")
            continue

        resized = resize_image_to_width(image, output_width)
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        webp_path = get_unique_output_path(os.path.join(webp_dir, f"{base_name}.webp"))

        success = cv2.imwrite(
            webp_path,
            resized,
            [cv2.IMWRITE_WEBP_QUALITY, quality],
        )
        if not success:
            tqdm.write(f"WebP変換に失敗しました: {image_path}")
            continue

        converted_files.append(webp_path)

    return converted_files


def process_face_crop(
    input_dir,
    output_dir,
    cropper_settings=None,
    output_width=DEFAULT_OUTPUT_WIDTH,
):
    """顔の切り抜き後、指定横幅のWebPに変換する"""
    
    # デフォルトの切り抜き設定
    if cropper_settings is None:
        cropper_settings = {
            'allow_skew': True,
            'face_factor': 0.8,
        }
    
    # 出力ディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)
    
    print("顔の切り抜きを実行...")
    
    input_images, skipped_files = collect_valid_images(input_dir)
    if not input_images:
        print(f"処理対象画像が見つかりません: {input_dir}")
        return False

    if skipped_files:
        print(f"読み込み対象外ファイルをスキップ: {', '.join(skipped_files)}")

    print(f"処理対象画像: {len(input_images)} 個")
    openai_targets = collect_openai_expand_targets(input_images)
    openai_target_names = ", ".join(
        os.path.basename(image_path) for image_path, _ in openai_targets[:5]
    )
    if len(openai_targets) > 5:
        openai_target_names += f", ほか{len(openai_targets) - 5}個"
    target_suffix = f" ({openai_target_names})" if openai_target_names else ""
    print(f"OpenAI API呼び出し対象: {len(openai_targets)} 個{target_suffix}")

    # 顔の切り抜き実行
    with tempfile.TemporaryDirectory() as temp_input_dir:
        for image_path in tqdm(input_images, desc="背景拡張", unit="枚"):
            destination = os.path.join(temp_input_dir, os.path.basename(image_path))
            expand_background_for_crop(image_path, destination)

        try:
            print("顔検出・切り抜き中...")
            cropper = Cropper(**cropper_settings)
            cropper.process_dir(temp_input_dir, output_dir)
            print(f"顔の切り抜き完了: {output_dir}")
        except Exception as e:
            print(f"顔の切り抜きエラー: {e}")
            print(f"使用した設定: {cropper_settings}")
            # デフォルト設定で試してみる
            try:
                print("デフォルト設定で再試行...")
                cropper = Cropper()
                cropper.process_dir(temp_input_dir, output_dir)
                print(f"デフォルト設定で顔の切り抜き完了: {output_dir}")
            except Exception as e2:
                print(f"デフォルト設定でもエラー: {e2}")
                return False
    
    converted_files = convert_outputs_to_webp(output_dir, output_width)
    
    print(f"\n処理完了！")
    print(f"- 切り抜き済み画像: {output_dir}")
    print(f"- WebP画像: {os.path.join(output_dir, 'webp')}")
    print(f"- 出力形式: WebP")
    print(f"- 出力横幅: {output_width}px")
    print(f"- 処理成功: {len(converted_files)} 個")
    
    return True

if __name__ == "__main__":
    # 設定
    input_directory = './input_images'
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_directory = f'./output_faces/{timestamp}'
    
    # カスタム設定（必要に応じて調整）
    custom_settings = {
        'allow_skew': False,        # 回転を無効化して縦横比を保持
        'face_factor': 0.45,         # 顔領域を小さめに（より引きで写る）
        'output_size': DEFAULT_OUTPUT_WIDTH,
        'padding': 'Reflect'
    }
    
    print("=== 顔の切り抜き処理 ===")
    output_width = prompt_output_width()
    custom_settings['output_size'] = output_width
    process_face_crop(
        input_directory, 
        output_directory,
        custom_settings,
        output_width
    ) 
