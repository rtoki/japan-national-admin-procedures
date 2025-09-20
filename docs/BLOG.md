# 日本の行政手続オンライン化状況データをMCPサーバーとHTTPストリーミングAPIで公開してみた

## はじめに

日本政府が公開している行政手続のオンライン化状況データ（約7.5万件）を、より使いやすい形で提供するため、MCP（Model Context Protocol）サーバーとHTTPストリーミングAPIを実装しました。

政府が提供するCSVファイルは2行のヘッダーを持つ複雑な構造で、38項目にわたる詳細なデータが含まれています。このデータを効率的に検索・分析できるようにすることで、日本のデジタル行政の現状を把握しやすくすることを目指しました。

## 実装内容

### 技術スタック

- **Python 3.13**
- **FastMCP** - MCP (Model Context Protocol) サーバーの実装
- **FastAPI** - HTTPストリーミングAPI
- **Uvicorn** - ASGI サーバー
- **Pydantic** - データバリデーション

### データソース

- **CSVファイル**: `20250729_procedures-survey-results_outline_02.csv`
  - 約75,000件の行政手続データ
  - 38項目の詳細情報（手続名、所管府省庁、オンライン化状況など）
- **解説資料PDF**: `20250722_procedures-survey-results_outline_03.pdf`
  - 各項目の詳細な説明
  - データの定義と分類基準

### アーキテクチャ

```
┌──────────────────┐
│  CSVデータファイル  │
└────────┬─────────┘
         │
    ┌────▼─────┐
    │ データ読込 │
    └────┬─────┘
         │
    ┌────▼──────────────────┐
    │                        │
    │  ┌─────────────────┐  │
    │  │ FastMCP Server │  │
    │  └─────────────────┘  │
    │                        │
    │  ┌─────────────────┐  │
    │  │  HTTP Streaming │  │
    │  │      Server     │  │
    │  └─────────────────┘  │
    │                        │
    └────────────────────────┘
```

### 主な機能

#### 1. FastMCPサーバー (`server.py`)

MCPプロトコルに対応したツールとして以下を実装：

- `list_procedures` - 全手続のリスト取得（ページネーション対応）
- `get_procedure_by_id` - 手続IDによる詳細情報取得
- `search_by_ministry` - 府省庁による検索
- `search_procedures` - キーワード検索（手続名、法令名）
- `filter_by_online_status` - オンライン化状況でのフィルタリング
- `get_statistics` - 統計情報の取得
- `search_by_profession` - 関連する士業による検索
- `search_by_life_event` - ライフイベント（出生、結婚、引越しなど）による検索

#### 2. HTTPストリーミングサーバー (`server_http.py`)

大量のデータを効率的に配信するため、ストリーミング対応のAPIを実装：

**通常のREST API**:
- `GET /procedures` - 手続リスト
- `GET /procedures/{id}` - 詳細情報
- `GET /procedures/search` - キーワード検索
- `GET /procedures/statistics` - 統計情報

**ストリーミングAPI**:
- `GET /procedures/stream` - NDJSON形式でのストリーミング配信
- `GET /procedures/search/stream` - 検索結果のストリーミング
- `GET /procedures/ministry/{ministry}/stream` - 府省庁別ストリーミング
- `GET /procedures/statistics/stream` - 統計情報の逐次配信

## 工夫した点

### 1. CSVデータの効率的な処理

政府のCSVファイルは2行のヘッダーを持つ特殊な形式でした。これを正しく解析するため：

```python
def load_procedures_data() -> List[Dict[str, str]]:
    """CSVファイルから手続データを読み込む"""
    procedures = []
    
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        # ヘッダー行をスキップ（2行）
        next(reader)  # 列番号行
        next(reader)  # カラム名行
        
        for row in reader:
            if len(row) >= len(COLUMNS):
                procedure = {}
                for i, col_name in enumerate(COLUMNS):
                    procedure[col_name] = row[i] if i < len(row) else ""
                procedures.append(procedure)
    
    return procedures
```

### 2. HTTPストリーミングの実装

75,000件のデータを一度に送信すると、クライアント側のメモリ負荷が高くなります。そこで、チャンク単位でのストリーミング配信を実装：

```python
async def stream_procedures(
    procedures: List[Dict[str, str]], 
    chunk_size: int = 100
) -> AsyncIterator[str]:
    """手続データをストリーミングで返すジェネレータ"""
    for i in range(0, len(procedures), chunk_size):
        chunk = procedures[i:i + chunk_size]
        yield json.dumps(chunk, ensure_ascii=False) + "\n"
        await asyncio.sleep(0.01)  # バックプレッシャー対策
```

### 3. PDFからの項目説明の活用

解説資料PDFから各項目の詳細な説明を抽出し、コード内のドキュメンテーションとして活用しました。これにより、データの意味を正確に理解できるAPIを提供できました。

### 4. 統計情報の自動集計

データから以下の統計を自動集計：
- 府省庁別の手続数
- オンライン化状況別の分布
- オンライン化率の計算
- 手続類型別の集計

## デモ

### サーバーの起動

```bash
# 依存関係のインストール
pip install -r requirements.txt

# HTTPストリーミングサーバーの起動
python server_http.py
```

### APIの使用例

```bash
# 手続リストの取得
curl http://localhost:8000/procedures?limit=5

# ストリーミングでの取得
curl http://localhost:8000/procedures/stream?chunk_size=100

# キーワード検索
curl http://localhost:8000/procedures/search?keyword=届出

# 統計情報の取得
curl http://localhost:8000/procedures/statistics
```

### 統計情報の例

```json
{
  "total_procedures": 75071,
  "online_rate": 42.3,
  "by_ministry": {
    "内閣官房": 124,
    "総務省": 3456,
    "厚生労働省": 8901,
    ...
  },
  "by_online_status": {
    "1 実施済": 31234,
    "2 未実施": 42567,
    ...
  }
}
```

## 課題と今後の展望

### 現在の課題

1. **データの更新**: 現在は静的なCSVファイルを使用。定期的な更新の仕組みが必要
2. **検索性能**: 全文検索やファセット検索の実装
3. **可視化**: データのビジュアライゼーション機能

### 今後の展望

1. **ElasticsearchやSolrの導入**: より高度な検索機能の実装
2. **GraphQL APIの追加**: クライアント側で必要なデータのみを取得
3. **WebSocketによるリアルタイム配信**: データ更新時の即時通知
4. **ダッシュボード機能**: オンライン化の進捗を可視化

## まとめ

政府が公開している行政手続データを、開発者が使いやすい形で提供するAPIを実装しました。FastMCPによるMCPサーバーと、FastAPIによるHTTPストリーミングの2つの方式で提供することで、様々なユースケースに対応できるようになりました。

特に、75,000件という大量のデータを効率的に配信するストリーミング機能により、クライアント側の負荷を抑えながら全データにアクセスできるようになったことは大きな成果です。

このプロジェクトが、日本のデジタル行政の現状を理解し、改善していくための一助となれば幸いです。

## 参考資料

- [MCP (Model Context Protocol) 公式ドキュメント](https://modelcontextprotocol.io/)
- [FastMCP ライブラリ](https://github.com/jlowin/fastmcp)
- [FastAPI 公式ドキュメント](https://fastapi.tiangolo.com/)
- [NDJSON (Newline Delimited JSON) 仕様](http://ndjson.org/)
- [e-Gov 行政手続オンライン化状況](https://www.digital.go.jp/)

## リポジトリ

実装したコードは以下で公開しています：
- GitHub: [admin-procedures-mcp-server](https://github.com/yourusername/admin-procedures-mcp-server)

## ライセンス

このプロジェクトのデータは日本政府が公開している情報を使用しています。
コード部分はMITライセンスで公開しています。