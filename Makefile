# Ampai Image Face Cropper - Makefile

.PHONY: help install setup clean run test lint format

# デフォルトターゲット
help:
	@echo "Ampai Image Face Cropper - Available commands:"
	@echo "  setup    - プロジェクトの初期セットアップ"
	@echo "  install  - 依存関係をインストール"
	@echo "  run      - 顔切り抜き処理を実行"
	@echo "  clean    - 出力ファイルを削除"
	@echo "  lint     - コード品質チェック"
	@echo "  format   - コードフォーマット"
	@echo "  test     - テストを実行"

# プロジェクトの初期セットアップ
setup:
	@echo "🚀 プロジェクトをセットアップ中..."
	pyenv install 3.10.0 --skip-existing
	pyenv local 3.10.0
	python -m venv venv
	@echo "✅ セットアップ完了！次に 'make install' を実行してください"

# 依存関係のインストール
install:
	@echo "📦 依存関係をインストール中..."
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "✅ インストール完了！"

# 顔切り抜き処理を実行
run:
	@echo "🎯 顔切り抜き処理を開始..."
	python face_crop_with_background_fix.py
	@echo "✅ 処理完了！"

# 出力ファイルの削除
clean:
	@echo "🧹 出力ファイルを削除中..."
	rm -rf output_faces/*
	rm -rf temp_faces/*
	rm -rf final_faces/*
	rm -rf __pycache__/
	rm -rf *.pyc
	rm -rf .pytest_cache/
	@echo "✅ クリーンアップ完了！"

# コード品質チェック（flake8）
lint:
	@echo "🔍 コード品質をチェック中..."
	pip install flake8
	flake8 --max-line-length=88 --ignore=E203,W503 *.py
	@echo "✅ リントチェック完了！"

# コードフォーマット（black）
format:
	@echo "✨ コードをフォーマット中..."
	pip install black
	black --line-length=88 *.py
	@echo "✅ フォーマット完了！"

# テスト実行
test:
	@echo "🧪 テストを実行中..."
	pip install pytest
	pytest -v
	@echo "✅ テスト完了！"

# 開発環境の状態確認
status:
	@echo "📊 開発環境の状態:"
	@echo "Python version: $(shell python --version)"
	@echo "Pip version: $(shell pip --version)"
	@echo "Virtual env: $(VIRTUAL_ENV)"
	@echo "Requirements satisfied: $(shell pip check > /dev/null 2>&1 && echo "✅" || echo "❌")"

# パッケージのビルド
build:
	@echo "📦 パッケージをビルド中..."
	pip install build
	python -m build
	@echo "✅ ビルド完了！" 
