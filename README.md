# Ampai Image Face Cropper

顔画像の自動切り抜きツールです。face-crop-plusライブラリを使用して、画像から顔部分を検出・切り抜きを行います。

## 特徴

- 🎯 **高精度な顔検出**: face-crop-plusライブラリによる正確な顔検出
- 🔄 **回転補正無効化**: 元の画像の向きを保持
- 📏 **縦横比保持**: 元画像の縦横比を維持
- 🎨 **引きで撮影**: face_factorを調整して余白を確保
- 🪶 **WebP軽量化**: 切り抜き後にWebP形式へ変換
- 🖼️ **横幅指定**: 100px〜1000pxから出力横幅を選択
- 📊 **進捗表示**: 背景拡張・WebP変換の進み具合をCLIに表示
- ⚡ **バッチ処理**: 複数の画像を一括処理

## 必要な環境

- Python 3.12.3以上
- face-crop-plus
- OpenCV
- NumPy

## インストール

### 1. pyenvでPythonバージョンを設定

```bash
# Python 3.12.3をインストール（未インストールの場合）
pyenv install 3.12.3

# プロジェクトディレクトリでPythonバージョンを設定
pyenv local 3.12.3
```

### 2. 依存関係をインストール

```bash
pip install -r requirements.txt
```

## クイックスタート

```bash
# 1. プロジェクトセットアップ
make setup

# 2. 依存関係インストール
make install

# 3. 実行
make run

# ヘルプ表示
make help
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

実行すると最初に出力画像の横幅を聞かれます。矢印キーで選択し、Enterで決定します。デフォルトは400pxです。

```bash
出力画像の横幅を選択してください。
矢印キーで選択、Enterで決定します。
100px  200px  300px  [400px]  500px  600px  700px  800px  900px  1000px
```

処理中は、背景拡張やWebP変換の進捗がCLIに表示されます。

### 3. 結果の確認

切り抜きされた元画像が `output_faces/` ディレクトリに保存され、WebP画像はその中の `webp/` ディレクトリに保存されます。

```
output_faces/
└── 20260425_194100/
    ├── image1.jpg
    ├── image2.png
    ├── image3.jpeg
    └── webp/
        ├── image1.webp
        ├── image2.webp
        └── image3.webp
```

## 設定

`face_crop_with_background_fix.py` 内の `custom_settings` と定数で設定を変更できます：

```python
DEFAULT_OUTPUT_WIDTH = 400
OUTPUT_WIDTH_OPTIONS = list(range(100, 1001, 100))
WEBP_QUALITY = 85

custom_settings = {
    'allow_skew': False,        # 回転を無効化
    'face_factor': 0.45,        # 顔領域のサイズ（0.1-1.0）
    'output_size': DEFAULT_OUTPUT_WIDTH,
    'padding': 'Reflect'        # パディング方式
}
```

### パラメータ説明

- **DEFAULT_OUTPUT_WIDTH**: CLIでEnterを押した場合の出力横幅
- **OUTPUT_WIDTH_OPTIONS**: CLIに表示する横幅の選択肢
- **WEBP_QUALITY**: WebP変換時の品質（大きいほど高品質・大容量）
- **allow_skew**: 画像の回転補正を行うか（False推奨）
- **face_factor**: 顔領域の大きさ（小さいほど引きで撮影）
- **output_size**: 切り抜き時の出力サイズ（実行時に選択した横幅へ自動更新）
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
