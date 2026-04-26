import os
import glob
import shutil
import sys
import termios
import tempfile
import tty
from datetime import datetime
import cv2
import numpy as np
from face_crop_plus import Cropper
from tqdm import tqdm

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SKIP_FILE_NAMES = {".gitkeep", ".ds_store"}
BACKGROUND_EXPANSION_RATIO = 0.25
BACKGROUND_EXPANSION_METHOD = "inpaint"
DEFAULT_OUTPUT_WIDTH = 300
OUTPUT_WIDTH_OPTIONS = list(range(100, 1001, 100))
WEBP_QUALITY = 85


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
