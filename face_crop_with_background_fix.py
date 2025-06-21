import os
import glob
from face_crop_plus import Cropper



def process_face_crop(input_dir, output_dir, cropper_settings=None):
    """顔の切り抜き処理のみ実行"""
    
    # デフォルトの切り抜き設定
    if cropper_settings is None:
        cropper_settings = {
            'allow_skew': True,
            'face_factor': 0.8,
        }
    
    # 出力ディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)
    
    print("顔の切り抜きを実行...")
    
    # 顔の切り抜き実行
    try:
        cropper = Cropper(**cropper_settings)
        cropper.process_dir(input_dir, output_dir)
        print(f"顔の切り抜き完了: {output_dir}")
    except Exception as e:
        print(f"顔の切り抜きエラー: {e}")
        print(f"使用した設定: {cropper_settings}")
        # デフォルト設定で試してみる
        try:
            print("デフォルト設定で再試行...")
            cropper = Cropper()
            cropper.process_dir(input_dir, output_dir)
            print(f"デフォルト設定で顔の切り抜き完了: {output_dir}")
        except Exception as e2:
            print(f"デフォルト設定でもエラー: {e2}")
            return False
    
    # 処理された画像数を確認
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(output_dir, ext)))
    
    print(f"\n処理完了！")
    print(f"- 切り抜き済み画像: {output_dir}")
    print(f"- 処理成功: {len(image_files)} 個")
    
    return True

if __name__ == "__main__":
    # 設定
    input_directory = './input_images'
    output_directory = './output_faces'
    
    # カスタム設定（必要に応じて調整）
    custom_settings = {
        'allow_skew': False,        # 回転を無効化して縦横比を保持
        'face_factor': 0.45,         # 顔領域を小さめに（より引きで写る）
        'output_size': 256,         # Noneにして元の縦横比を保持
        'padding': 'Replicate'
    }
    
    print("=== 顔の切り抜き処理 ===")
    process_face_crop(
        input_directory, 
        output_directory,
        custom_settings
    ) 
