# WRC Image Face Cropper

顔画像の自動切り抜きツールです。face-crop-plusライブラリを使用して、画像から顔部分を検出・切り抜きを行います。

## 特徴

- 🎯 **高精度な顔検出**: face-crop-plusライブラリによる正確な顔検出
- 🔄 **回転補正無効化**: 元の画像の向きを保持
- 📏 **縦横比保持**: 元画像の縦横比を維持
- 🎨 **引きで撮影**: face_factorを調整して余白を確保
- ⚡ **バッチ処理**: 複数の画像を一括処理

## 必要な環境

- Python 3.10以上
- face-crop-plus
- OpenCV
- NumPy

## インストール

### 1. pyenvでPythonバージョンを設定

```bash
# Python 3.10をインストール（未インストールの場合）
pyenv install 3.10.0

# プロジェクトディレクトリでPythonバージョンを設定
pyenv local 3.10.0
```

### 2. 仮想環境を作成

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate     # Windows
```

### 3. 依存関係をインストール

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 画像の準備

`input_images/` ディレクトリに処理したい画像を配置してください。

```
input_images/
├── image1.jpg
├── image2.png
└── image3.jpeg
```

### 2. 実行

```bash
python face_crop_with_background_fix.py
```

### 3. 結果の確認

切り抜きされた顔画像が `output_faces/` ディレクトリに保存されます。

```
output_faces/
├── image1.jpg
├── image2.png
└── image3.jpeg
```

## 設定

`face_crop_with_background_fix.py` 内の `custom_settings` で設定を変更できます：

```python
custom_settings = {
    'allow_skew': False,        # 回転を無効化
    'face_factor': 0.6,         # 顔領域のサイズ（0.1-1.0）
    'output_size': 256,         # 出力画像サイズ
    'padding': 'Replicate'      # パディング方式
}
```

### パラメータ説明

- **allow_skew**: 画像の回転補正を行うか（False推奨）
- **face_factor**: 顔領域の大きさ（小さいほど引きで撮影）
- **output_size**: 出力画像のサイズ（Noneで元サイズ）
- **padding**: パディング方式

## トラブルシューティング

### エラーが発生した場合

```bash
# デバッグモードで実行
python -v face_crop_with_background_fix.py
```

### 依存関係の問題

```bash
# 依存関係を再インストール
pip install --upgrade -r requirements.txt
```

### 顔が検出されない場合

- 画像の解像度を確認
- 顔が明確に写っているか確認
- face_factorの値を調整

## ライセンス

MIT License

## 参考資料

- [face-crop-plus](https://github.com/mantasu/face-crop-plus)
- [pyenv](https://github.com/pyenv/pyenv)

## 更新履歴

- v1.0.0: 初回リリース
  - 顔画像切り抜き機能
  - バッチ処理対応
  - 設定カスタマイズ対応 
