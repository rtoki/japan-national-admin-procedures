# 日本の行政手続等オンライン化状況ダッシュボード

約75,000件の行政手続等データを可視化・分析するインタラクティブなダッシュボードアプリケーション

![License](https://img.shields.io/badge/license-MIT-green)

## 📊 概要

このプロジェクトは、日本政府の法令に基づく行政手続等のオンライン化状況を可視化・分析するためのStreamlitベースのダッシュボードです。デジタル庁が公開している「行政手続等の悉皆調査結果等」(令和7年7月29日)のデータをもとに作成しています。
https://www.digital.go.jp/resources/procedures-survey-results

各府省庁の手続きのオンライン化率、申請システムの利用状況、法令別の分析など、多角的な視点から行政手続のデジタル化の現状を把握できます。

## ✨ 主な機能

### 基本機能
- **📊 概要統計**: 全体的な手続数、オンライン化率などのKPI表示（2x2グリッド表示）
- **🔍 統合検索**: 手続名、法令名、手続ID等での包括的な検索
- **📋 手続一覧**: ページネーション対応の手続一覧（100件/ページ）
- **💾 データエクスポート**: 検索結果や分析結果のCSVダウンロード

### 分析機能
- **🏢 府省庁別分析**: 各府省庁のオンライン化状況の比較・積み上げ棒グラフ（レジェンド下部配置）
- **🤝 手続主体×受け手分析**: ヒートマップによる手続フローの可視化（PCのみ）
- **⚖️ 法令別分析**: 法令種別の円グラフと手続数ランキング（TOP15）
- **💻 申請システム分析**: 申請・事務処理システムの利用状況（TOP15）
- **📝 申請文書分析**: 添付書類、記載情報の統計（円グラフTOP10）
- **🌟 ライフイベント分析**: 個人・法人のライフイベント別手続分布（円グラフTOP10）
- **🏛️ 申請関連分析**: 士業別・提出先機関別の分析

### UI/UX機能
- **📱 モバイル対応**: 完全レスポンシブデザイン（グラフの縦並び、フォントサイズ自動調整）
- **🎨 Material Designアイコン**: 統一されたアイコンデザイン
- **🔄 リアルタイムフィルタリング**: サイドバーでの動的なデータ絞り込み
- **📊 インタラクティブグラフ**: Plotlyによる対話的なデータ可視化
- **⚡ メモリ最適化**: カテゴリ型とParquet形式による効率的なメモリ使用（約450MB）

## 🚀 クイックスタート

### 必要要件

- Python 3.9以上（推奨: 3.11）
- pip または pip3

### インストール

1. リポジトリをクローン
```bash
git clone https://github.com/rtoki/japan-national-admin-procedures.git
cd japan-national-admin-procedures
```

2. 仮想環境を作成（推奨）
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. 依存パッケージをインストール
```bash
pip install -r requirements.txt
```

### ローカル実行

```bash
streamlit run streamlit_app.py
```

ブラウザが自動的に開き、http://localhost:8501 でアプリケーションが表示されます。

## 🌐 クラウドデプロイ

### Renderへのデプロイ

このアプリケーションはRenderに簡単にデプロイできます。

#### 自動デプロイ（推奨）

1. [Render](https://render.com)にサインアップ
2. GitHubリポジトリをRenderに接続
3. 「New +」→「Web Service」を選択
4. リポジトリを選択（`render.yaml`が自動検出される）
5. 「Apply」をクリックしてデプロイ

#### 手動設定

Render Dashboardで以下の設定を使用：
- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0`

#### 注意事項

- **無料プラン**: 512MBメモリ、15分非アクティブでスリープ
- **推奨プラン**: Starterプラン（$7/月）以上でパフォーマンス向上
- **初回起動**: データファイルの変換で30秒程度かかる場合があります

### Streamlit Community Cloudへのデプロイ

1. [Streamlit Community Cloud](https://streamlit.io/cloud)にサインアップ
2. GitHubリポジトリを接続
3. アプリをデプロイ（自動的に`streamlit_app.py`が検出される）

## 📁 プロジェクト構成

```
japan-national-admin-procedures/
├── streamlit_app.py          # メインアプリケーション
├── requirements.txt          # Python依存パッケージ
├── README.md                # このファイル
├── render.yaml              # Render自動デプロイ設定
├── runtime.txt              # Pythonバージョン指定
├── .streamlit/
│   └── config.toml         # Streamlit設定ファイル
└── docs/
    ├── 20250729_procedures-survey-results_outline_02.csv  # 元データ（CSV）
    └── procedures_data.parquet  # 高速化用Parquetファイル（自動生成）
```

## 🔧 技術スタック

### コアライブラリ
- **Streamlit 1.49.1**: Webアプリケーションフレームワーク
- **Pandas 2.3.2**: データ処理・分析
- **Plotly 6.3.0**: インタラクティブなグラフ作成
- **NumPy 2.3.3**: 数値計算
- **PyArrow 21.0.0**: Parquetファイル処理とメモリ最適化

### 主な技術的特徴
- **Parquet形式**: 高速データ読み込みとメモリ効率化
- **キャッシング**: `@st.cache_data`による計算結果の再利用
- **レスポンシブデザイン**: CSS MediaQueryによるモバイル対応
- **Material Icons**: 統一されたアイコンデザイン


## 📈 データについて

### データソース
- 元データ: `20250729_procedures-survey-results_outline_02.csv` (https://www.digital.go.jp/resources/procedures-survey-results より)
- 約75,000件の行政手続等情報（法令に基づく手続）
- 38カラムの詳細情報

### 主要カラム
- 手続ID、所管府省庁、手続名
- 法令名、法令番号、根拠条項号
- オンライン化の実施状況
- 総手続件数、オンライン手続件数
- 情報システム（申請・事務処理）
- ライフイベント情報
- 申請に関連する士業

## 🎯 使用方法

### フィルター機能
サイドバーから以下の条件でデータをフィルタリング可能：
- 統合検索（手続名、法令名、手続ID等）
- 府省庁（建制順で整理）
- オンライン化状況
- 手続類型
- 手続主体
- 手続の受け手
- 事務区分
- 府省共通手続
- 手続件数範囲（100万件以上〜0件まで8段階）

**注**: フィルターは即座に適用されます（リアルタイムフィルタリング）。

### データエクスポート
- 検索結果や分析結果をCSV形式でダウンロード可能
- 各分析タブから関連データのエクスポートが可能

## 🔄 更新履歴

### v1.0.1 (2025-09-21)
- **メモリ最適化**: 使用メモリを約450MBに削減（60-70%削減）
- **ページネーション実装**: 手続一覧を100件ずつ表示
- **モバイル対応強化**: 完全レスポンシブデザイン実装
- **グラフ改善**: 円グラフ追加、TOP表示件数の最適化
- **検索機能改善**: リアルタイムフィルタリング実装
- **deploy**: Renderデプロイ対応
- **データ読み込み**: Parquet形式によるデータ読み込み高速化

---

Made with ❤️ and Streamlit