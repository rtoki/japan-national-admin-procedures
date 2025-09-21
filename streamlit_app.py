#!/usr/bin/env python3
"""
行政手続等オンライン化状況 データ可視化・分析ダッシュボード

日本の法令に基づく行政手続等のオンライン化状況を可視化・分析する
Streamlitベースの対話的データ分析ツール
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from pathlib import Path
from typing import List, Any, Dict
import re
import warnings

warnings.filterwarnings('ignore')

# pandas 2.3.2の新機能を活用
pd.set_option('mode.copy_on_write', True)  # Copy-on-Write最適化
pd.set_option('future.infer_string', True)  # 文字列型の推論を改善
pd.set_option('display.max_colwidth', 50)  # 表示最適化

# numpy 2.3.2の最適化設定
np.set_printoptions(precision=3, suppress=True)

# ページ設定
st.set_page_config(
    page_title="行政手続等オンライン化状況ダッシュボード",
    page_icon=":material/gavel:",
    layout="wide",
    initial_sidebar_state="expanded"  # サイドバーをデフォルトで展開
)

# モバイル対応のCSSを追加
st.markdown("""
<style>
/* モバイル対応のスタイル */
@media (max-width: 768px) {
    /* タブのスクロール対応 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        overflow-x: auto;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
    }

    /* カラムの縦積み */
    [data-testid="column"]:not(:only-child) {
        width: 100% !important;
        flex: 1 1 100% !important;
    }

    /* データフレームの横スクロール対応 */
    .stDataFrame {
        overflow-x: auto;
    }

    /* メトリクスカードの調整 */
    [data-testid="metric-container"] {
        padding: 0.5rem;
    }

    /* ボタンのタッチ領域を拡大 */
    .stButton button {
        min-height: 2.5rem;
        touch-action: manipulation;
    }

    /* グラフの高さ調整 */
    .js-plotly-plot {
        height: auto !important;
        max-height: 350px !important;
    }

    /* タイトルの文字サイズ調整 */
    h1 {
        font-size: 1.5rem !important;
    }

    /* サイドバーの幅調整 */
    section[data-testid="stSidebar"] > div {
        width: 270px !important;
    }
}

/* タブレット対応 */
@media (min-width: 769px) and (max-width: 1024px) {
    [data-testid="column"] {
        flex: 1 1 50% !important;
    }
}

/* ダイアログのモバイル対応 */
[role="dialog"] {
    max-width: 95% !important;
    max-height: 90vh !important;
    overflow-y: auto !important;
}
</style>
""", unsafe_allow_html=True)

# ファイルパス
DATA_DIR = Path("docs")
CSV_FILE = DATA_DIR / "20250729_procedures-survey-results_outline_02.csv"
PARQUET_FILE = DATA_DIR / "procedures_data.parquet"

# カラム定義（CSV読み込み用）
COLUMNS = [
    "手続ID", "手続名", "手続名（カナ）", "手続名（英語）", "法令名",
    "法令名（カナ）", "法令番号", "根拠条項", "根拠条項号",
    "手続類型", "手続の概要", "手続の受け手", "手続主体",
    "手続が行われるイベント(個人)", "手続が行われるイベント(法人)",
    "所管府省庁", "組織", "担当課室", "電話番号", "FAX番号", "Mail",
    "手続URL", "オンライン化の実施状況", "申請時に添付させる書類",
    "添付書類等提出の撤廃/省略状況", "添付書類等の提出方法",
    "添付書類等への電子署名", "情報システム(申請)", "情報システム(事務処理)",
    "事務区分", "府省共通手続", "申請に関連する士業", "オンライン手続URL",
    "総手続件数", "オンライン手続件数", "非オンライン手続件数", "調査年",
]

# フィールド説明の辞書（ユーザー補助用）
FIELD_DEFS = {
    '手続ID': '行政手続の一意識別子',
    '法令名': '手続の根拠となる法律・政令・省令等の名称',
    '法令番号': '法令の公布番号（例：平成○年法律第○号）',
    '根拠条項号': '手続の根拠となる条文番号',
    '手続類型': '申請・届出、報告・通知、交付等の手続の種類',
    '手続の受け手': '手続を受理する側（国、地方公共団体、民間等）',
    '手続主体': '手続を行う側（国民、事業者、行政機関等）',
    'オンライン化の実施状況': 'オンライン手続の対応状況',
    '事務区分': '自治事務、法定受託事務等の区分',
    '府省共通手続': '複数府省で共通の手続かどうか',
    '手続が行われるイベント(個人)': '出生、結婚、引越し等のライフイベント',
    '手続が行われるイベント(法人)': '設立、合併、廃業等の法人ライフイベント',
    '申請に関連する士業': '手続に関与する可能性のある専門職（弁護士、税理士等）'
}

# PDF解説資料に基づくカテゴリの説明
PROCEDURE_TYPE_DESCRIPTIONS: Dict[str, str] = {
    "申請・届出": "法令に基づき行政機関へ申請や届出、通知を行う手続。",
    "審査・決定": "申請に基づいて行政機関が決定・許認可などの処分を通知する手続。",
    "報告・通知": "申請に基づかない行政からの通知や改善命令等の処分。",
    "納付": "手数料や税などを納付する行為全般。",
    "交付等": "行政機関が証明書・許可証などを交付する行為。",
    "相談": "相談対応や助言を受け付ける手続。",
    "照会・閲覧": "書面や電磁的記録を閲覧・縦覧・謄写する手続。",
    "記帳・記載・書類作成": "法令に基づき書類を作成・記帳・保存する行為。",
    "交付等（民間手続）": "民間事業者等が法令に基づき交付・通知・提供を行う手続。",
    "その他": "上記類型に収まらない手続。",
}

ACTOR_DESCRIPTIONS: Dict[str, str] = {
    "国": "国の行政機関が手続主体となるケース。",
    "独立行政法人等": "独立行政法人や特殊法人などが主体。",
    "地方等": "地方公共団体およびその機関が主体。",
    "国又は独立行政法人等": "国と独立行政法人等の双方が状況に応じて主体となる手続。",
    "独立行政法人等又は地方等": "独立行政法人等または地方公共団体が主体となる手続。",
    "国又は地方等": "国または地方公共団体が主体。",
    "国、独立行政法人等又は地方等": "国・独立行政法人等・地方公共団体のいずれかが主体となりうる手続。",
    "国民等": "事業者以外の個人。日本国籍以外の個人も含む。",
    "民間事業者等": "事業者、個人事業主など営利主体。",
    "国民等、民間事業者等": "個人利用者と民間事業者の双方が主体。",
}

RECEIVER_DESCRIPTIONS: Dict[str, str] = ACTOR_DESCRIPTIONS.copy()

PERSONAL_EVENT_ORDER = [
    "妊娠", "出生・こども", "引越し", "就職・転職", "結婚・離婚",
    "自動車の購入・保有", "住宅の購入・保有", "介護", "医療・健康",
    "税金", "年金の受給", "死亡・相続", "その他イベント（個人）",
    "その他（個人にも法人にもあてはまらない）"
]

CORPORATE_EVENT_ORDER = [
    "法人の設立", "法人の情報変更・役員変更", "職員の採用・退職", "入札・契約",
    "事務所の新設・移転", "新しい事業の開始", "法人の合併・分割", "法人の承継・廃業",
    "定期的な報告等", "作業ごとの報告等", "その他イベント（法人）"
]

PROFESSION_ORDER = [
    "弁護士", "司法書士", "行政書士", "税理士", "社会保険労務士", "公認会計士",
    "弁理士", "土地家屋調査士", "海事代理士", "中小企業診断士", "医療系職種",
    "その他", "士業が介在しない"
]

# カテゴリカル列に対する表示順序（全体的に頻度順になるが、オンライン化状況等は定義順が望ましい）
OPTION_ORDERS = {
    "手続類型": ["申請・届出", "審査・決定", "報告・通知", "納付", "交付等", "相談", "照会・閲覧", "記帳・記載・書類作成", "その他", "交付等（民間手続）"],
    "オンライン化の実施状況": ["実施済", "一部実施済", "未実施", "適用除外", "その他"],
    "手続主体": ["国", "独立行政法人等", "地方等", "国又は独立行政法人等", "独立行政法人等又は地方等", "国又は地方等", "国、独立行政法人等又は地方等", "国民等", "民間事業者等", "国民等、民間事業者等"],
    "手続の受け手": ["国", "独立行政法人等", "地方等", "国又は独立行政法人等", "独立行政法人等又は地方等", "国又は地方等", "国、独立行政法人等又は地方等", "国民等", "民間事業者等", "国民等、民間事業者等"],
    "事務区分": ["自治事務", "第1号法定受託事務", "第2号法定受託事務", "地方の事務でない"],
    "府省共通手続": ["○（全府省）", "●（一部の府省）", "×（府省共通手続でない)"]
}

# ---- 正規化ユーティリティ ----
def _normalize_label(key: str, val: Any) -> str:
    s = str(val).strip()
    if s.lower() == 'nan' or s == '':
        return s
    # 統一：半角括弧→全角括弧
    s = s.replace('(', '（').replace(')', '）')
    # 先頭の分類コード（例: 1 / 2-1 / 2-3 等）を除去
    if key in ("オンライン化の実施状況", "手続類型"):
        s = re.sub(r"^\s*\d+(?:-\d+)?\s*", "", s)
    # よくある表記ゆれの吸収
    if key == "手続類型":
        # 「交付等（民間手続）」の表記ゆれ
        s = s.replace("交付等(民間手続)", "交付等（民間手続）")
    return s

def normalized_counts(df: pd.DataFrame, column: str, key: str) -> pd.Series:
    if column not in df.columns or len(df) == 0:
        return pd.Series(dtype=int)
    series = df[column].dropna().map(lambda v: _normalize_label(key, v))
    vc = series.value_counts()
    order = OPTION_ORDERS.get(key)
    if order and key != "手続類型":  # 手続類型は全て表示するため順序を適用しない
        ordered = vc.reindex([v for v in order if v in vc.index]).dropna()
        # もし順序適用で空になったら、素のカウントにフォールバック
        if len(ordered) > 0:
            return ordered
    return vc

def order_series_by_option(series: pd.Series, key: str) -> pd.Series:
    order = OPTION_ORDERS.get(key)
    if not order:
        return series
    # dict for order index
    idx = {v: i for i, v in enumerate(order)}
    return series.sort_index(key=lambda s: s.map(lambda x: idx.get(x, len(idx))))


def split_multi_value(value: Any) -> List[str]:
    """全角・半角の区切りを考慮して多値を分割"""
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return []
    parts = re.split(r"[、,;\n・／/]+", text)
    return [p.strip() for p in parts if p and p.strip()]


def multi_value_counts(
    df: pd.DataFrame,
    column: str,
    order: List[str] | None = None
) -> pd.Series:
    """多値カラムを分解して頻度集計"""
    if column not in df.columns or df.empty:
        return pd.Series(dtype=int)

    values: List[str] = []
    series = df[column].dropna()
    for val in series:
        values.extend(split_multi_value(val))

    if not values:
        return pd.Series(dtype=int)

    counts = pd.Series(values).value_counts()
    if order:
        ordered = counts.reindex([v for v in order if v in counts.index]).dropna()
        if len(ordered) > 0:
            return ordered.astype(int)
    return counts.astype(int)

@st.cache_data(ttl=3600, show_spinner="データを読み込んでいます...")
def load_data() -> pd.DataFrame:
    """Parquetファイルからデータを高速読み込み（CSVファイルがない場合は変換）"""

    # Parquetファイルが存在しない場合はCSVから変換
    if not PARQUET_FILE.exists() and CSV_FILE.exists():
        st.info("初回起動：CSVファイルをParquet形式に変換しています...")

        # CSVファイルを読み込み
        df = pd.read_csv(
            CSV_FILE,
            encoding='utf-8-sig',
            skiprows=2,
            names=COLUMNS,
            dtype=str,
            na_values=['', 'NaN', 'nan'],
            low_memory=False
        )

        # カテゴリ型に変換
        categorical_cols = ['所管府省庁', '手続類型', '手続主体', '手続の受け手',
                          'オンライン化の実施状況', '事務区分', '府省共通手続']
        for col in categorical_cols:
            if col in df.columns:
                df[col] = df[col].astype('category')

        # 数値型に変換
        numeric_columns = ["総手続件数", "オンライン手続件数", "非オンライン手続件数"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('int32')

        # オンライン化率を計算
        if '総手続件数' in df.columns and 'オンライン手続件数' in df.columns:
            df['オンライン化率'] = np.where(
                df['総手続件数'] > 0,
                (df['オンライン手続件数'] / df['総手続件数'] * 100).round(2),
                0
            ).astype('float32')

        # Parquetファイルとして保存
        df.to_parquet(PARQUET_FILE, engine='pyarrow', compression='zstd')  # zstd圧縮で効率化（pyarrow 21.0.0）
        st.success("変換完了！次回からは高速に読み込めます。")

    # Parquetファイルから読み込み（超高速）
    df = pd.read_parquet(PARQUET_FILE, engine='pyarrow')

    # カテゴリ型が維持されているか確認
    categorical_cols = ['所管府省庁', '手続類型', '手続主体', '手続の受け手',
                      'オンライン化の実施状況', '事務区分', '府省共通手続']
    for col in categorical_cols:
        if col in df.columns and df[col].dtype != 'category':
            df[col] = df[col].astype('category')

    # オンライン化率がない場合は計算
    if 'オンライン化率' not in df.columns:
        if '総手続件数' in df.columns and 'オンライン手続件数' in df.columns:
            df['オンライン化率'] = np.where(
                df['総手続件数'] > 0,
                (df['オンライン手続件数'] / df['総手続件数'] * 100).round(2),
                0
            ).astype('float32')

    return df

# セッション状態の初期化
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
    st.session_state.df = None

@st.cache_data
def get_unique_values(df, column):
    """カラムのユニーク値を取得（キャッシュ）"""
    if df[column].dtype.name == 'category':
        # カテゴリ型の場合は高速処理
        return sorted([str(v) for v in df[column].cat.categories if pd.notna(v)])
    else:
        unique_vals = df[column].dropna().unique()
        # 全て文字列に変換してからソート
        return sorted([str(v) for v in unique_vals])

@st.cache_data
def filter_dataframe(df, ministries, statuses, types, recipients, actors=None, receivers=None, office_types=None, is_common=None, count_ranges=None):
    """データフレームをフィルタリング（キャッシュ）"""
    mask = pd.Series([True] * len(df), index=df.index)
    if ministries:
        mask &= df['所管府省庁'].isin(ministries)
    if statuses:
        mask &= df['オンライン化の実施状況'].isin(statuses)
    if types:
        mask &= df['手続類型'].isin(types)
    if recipients:
        mask &= df['手続の受け手'].isin(recipients)
    if actors:
        mask &= df['手続主体'].isin(actors)
    if receivers:
        mask &= df['手続の受け手'].isin(receivers)
    if office_types:
        mask &= df['事務区分'].isin(office_types)
    if is_common:
        mask &= df['府省共通手続'].isin(is_common)

    # 手続件数範囲フィルター
    if count_ranges:
        count_mask = pd.Series([False] * len(df), index=df.index)
        for range_str in count_ranges:
            if range_str == "100万件以上":
                count_mask |= df['総手続件数'] >= 1000000
            elif range_str == "10万件以上100万件未満":
                count_mask |= (df['総手続件数'] >= 100000) & (df['総手続件数'] < 1000000)
            elif range_str == "1万件以上10万件未満":
                count_mask |= (df['総手続件数'] >= 10000) & (df['総手続件数'] < 100000)
            elif range_str == "1000件以上1万件未満":
                count_mask |= (df['総手続件数'] >= 1000) & (df['総手続件数'] < 10000)
            elif range_str == "100件以上1000件未満":
                count_mask |= (df['総手続件数'] >= 100) & (df['総手続件数'] < 1000)
            elif range_str == "10件以上100件未満":
                count_mask |= (df['総手続件数'] >= 10) & (df['総手続件数'] < 100)
            elif range_str == "1件以上10件未満":
                count_mask |= (df['総手続件数'] >= 1) & (df['総手続件数'] < 10)
            elif range_str == "0件もしくは不明":
                count_mask |= (df['総手続件数'] == 0) | df['総手続件数'].isna()
        mask &= count_mask

    return df[mask]



# CSVエクスポート用キャッシュヘルパー（メモリ最適化）
@st.cache_data(ttl=300, max_entries=5)  # 5分キャッシュ、最大5エントリ
def df_to_csv_bytes(df: pd.DataFrame, columns: List[str] | None = None) -> bytes:
    if columns:
        df = df[columns]
    # 小さいデータの場合は直接変換
    if len(df) < 5000:
        return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    # 大きいデータの場合はメモリ効率的に処理
    from io import StringIO
    output = StringIO()
    df.to_csv(output, index=False)
    result = output.getvalue().encode('utf-8-sig')
    output.close()
    return result

# 手続詳細表示用のダイアログ
@st.dialog("手続詳細情報", width="large")
def show_procedure_detail(procedure_id: str, df: pd.DataFrame):
    """手続の詳細情報をダイアログで表示"""
    # 該当する手続を検索
    procedure = df[df['手続ID'] == procedure_id]
    if procedure.empty:
        st.error(f"手続ID: {procedure_id} が見つかりません")
        return

    # 詳細情報を表示
    _render_procedure_detail(procedure_id, df)

def _render_procedure_detail(proc_id: str, df: pd.DataFrame):
    """手続の詳細情報を描画（再利用可能な形で切り出し）"""
    procedure = df[df['手続ID'] == proc_id]
    if procedure.empty:
        st.error(f"手続ID: {proc_id} が見つかりません")
        return

    r = procedure.iloc[0].to_dict()

    # タイトル
    st.subheader(f":material/description: {r.get('手続名', '名称不明')}")

    # --- インサイト（要点サマリ） ---
    try:
        ministry = str(r.get('所管府省庁', ''))
        law_name = str(r.get('法令名', ''))
        status_val = str(r.get('オンライン化の実施状況', ''))

        # 府省別の実施状況（実施済・一部実施済）
        ministry_df = df[df['所管府省庁'] == ministry] if ministry else pd.DataFrame()
        m_total = len(ministry_df)
        m_full = int(ministry_df['オンライン化の実施状況'].astype(str).str.contains('実施済').sum()) if m_total else 0
        # 「一部実施済」を含めた率
        m_partial = int(ministry_df['オンライン化の実施状況'].astype(str).str.contains('一部').sum()) if m_total else 0
        m_full_rate = (m_full / m_total) if m_total else 0.0
        m_full_partial_rate = ((m_full + m_partial) / m_total) if m_total else 0.0

        # 同法令の他手続
        same_law_df = df[(df['法令名'] == law_name)] if law_name else pd.DataFrame()
        n_same_law = len(same_law_df)

        # 同法令内のオンライン化率
        law_online = same_law_df['オンライン化の実施状況'].astype(str).str.contains('実施済').sum() if n_same_law else 0
        law_online_rate = (law_online / n_same_law * 100) if n_same_law else 0

        # 添付書類の推定点数
        att_list = split_multi_value(r.get('申請時に添付させる書類'))
        att_count = len(att_list)
        sign_text = str(r.get('添付書類等への電子署名', '') or '')
        has_online_url = bool(r.get('オンライン手続URL'))

        # デジタル化成熟度スコア（0-100）
        maturity_score = 0
        maturity_details = []

        # オンライン化状況（40点）
        if '実施済' in status_val and '一部' not in status_val:
            maturity_score += 40
            maturity_details.append(("オンライン化", 40))
        elif '一部実施済' in status_val:
            maturity_score += 20
            maturity_details.append(("オンライン化", 20))
        else:
            maturity_details.append(("オンライン化", 0))

        # 添付書類撤廃状況（20点）
        doc_removal = str(r.get('添付書類等提出の撤廃/省略状況', ''))
        if '撤廃' in doc_removal or '全廃' in doc_removal:
            maturity_score += 20
            maturity_details.append(("書類撤廃", 20))
        elif '一部' in doc_removal or '省略' in doc_removal:
            maturity_score += 10
            maturity_details.append(("書類撤廃", 10))
        else:
            maturity_details.append(("書類撤廃", 0))

        # 手数料オンライン納付（20点）
        fee_method = str(r.get('手数料等の納付方法', ''))
        if 'オンライン' in fee_method or 'ペイジー' in fee_method or 'クレジット' in fee_method:
            maturity_score += 20
            maturity_details.append(("キャッシュレス", 20))
        elif '収入印紙' in fee_method or '現金' in fee_method:
            maturity_details.append(("キャッシュレス", 0))
        else:
            maturity_details.append(("キャッシュレス", 10))
            maturity_score += 10

        # システム統合（20点）
        has_system = bool(r.get('情報システム(申請)')) or bool(r.get('情報システム(事務処理)'))
        if has_system:
            maturity_score += 20
            maturity_details.append(("システム化", 20))
        else:
            maturity_details.append(("システム化", 0))

        with st.expander(":material/insights: デジタル化インサイト", expanded=True):
            # 主要指標
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                # デジタル成熟度を表示
                st.metric("DX成熟度", f"{maturity_score}点", delta=None)
            with col2:
                delta = None
                if n_same_law > 1:
                    delta = f"法令内{law_online_rate:.0f}%"
                st.metric("同法令の手続数", f"{n_same_law:,}", delta=delta)
            with col3:
                st.metric("府省実施率", f"{m_full_rate*100:.1f}%")
            with col4:
                st.metric("添付書類数", f"{att_count}")

            # DX成熟度の内訳
            st.markdown("**デジタル成熟度の内訳（100点満点）**")
            detail_cols = st.columns(4)
            for i, (label, score) in enumerate(maturity_details):
                with detail_cols[i % 4]:
                    if score == 0:
                        st.error(f"{label}: {score}点")
                    elif score < 20:
                        st.warning(f"{label}: {score}点")
                    else:
                        st.success(f"{label}: {score}点")

            # 改善提案
            improvements: list[str] = []
            priority_improvements: list[str] = []  # 優先度高

            # 優先度高の改善項目
            if '未実施' in status_val:
                if law_online_rate > 50:
                    priority_improvements.append(f"🔴 同法令の他手続は{law_online_rate:.0f}%がオンライン化済。本手続も早急な対応が必要")
                elif m_full_partial_rate > 0.5:
                    priority_improvements.append(f"🔴 府省内{m_full_partial_rate*100:.0f}%が実施/一部実施済。本手続のオンライン化が急務")

            if maturity_score < 40:
                priority_improvements.append("🔴 デジタル成熟度が低い。包括的なDX推進計画の策定を推奨")

            # 通常の改善項目
            if '実施済' in status_val and not has_online_url:
                improvements.append("オンライン手続URLが未記載。アクセシビリティ向上のためリンク整備を推奨")

            if att_count >= 5:
                improvements.append(f"添付書類が{att_count}点と多い。データ連携による自動取得やワンスオンリー原則の適用を検討")
            elif att_count >= 3:
                improvements.append(f"添付書類{att_count}点。優先度の低い書類から段階的な削減を検討")

            if '必' in sign_text or '要' in sign_text:
                improvements.append("電子署名が必要。マイナンバーカード活用や署名省略の可否を検討")

            if not any([r.get('電話番号'), r.get('Mail')]):
                improvements.append("問合せ先未記載。チャットボットやFAQ充実化も含めたサポート体制構築を推奨")

            # 手数料関連
            if r.get('手数料等の納付有無') == '有':
                if 'オンライン' not in fee_method and 'ペイジー' not in fee_method:
                    improvements.append("手数料のキャッシュレス決済未対応。ペイジーやクレジットカード決済の導入を検討")

            # 経由機関
            intermediary = str(r.get('経由機関', ''))
            if intermediary and intermediary != '—' and intermediary != 'nan':
                improvements.append(f"経由機関（{intermediary}）あり。直接申請やAPI連携による業務効率化を検討")

            if priority_improvements:
                st.error("**優先改善事項**")
                for item in priority_improvements:
                    st.markdown(item)

            if improvements:
                st.info("**改善提案**")
                for item in improvements:
                    st.markdown(f"• {item}")
    except Exception as e:
        st.error(f"インサイト生成エラー: {e}")
        pass

    # 基本情報
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**手続ID**")
            st.info(r.get('手続ID', '—'))

            if pd.notna(r.get('手続名（カナ）')):
                st.markdown("**手続名（カナ）**")
                st.info(r.get('手続名（カナ）', '—'))

            st.markdown("**手続類型**")
            st.info(r.get('手続類型', '—'))

            st.markdown("**オンライン化の実施状況**")
            status = r.get('オンライン化の実施状況', '—')
            if '実施済' in str(status):
                st.success(status)
            elif '一部実施済' in str(status):
                st.warning(status)
            elif '未実施' in str(status):
                st.error(status)
            else:
                st.info(status)

        with col2:
            st.markdown("**所管府省庁**")
            st.info(r.get('所管府省庁', '—'))

            if pd.notna(r.get('組織')):
                st.markdown("**組織**")
                st.info(r.get('組織', '—'))

            if pd.notna(r.get('担当課室')):
                st.markdown("**担当課室**")
                st.info(r.get('担当課室', '—'))

            if pd.notna(r.get('調査年')):
                st.markdown("**調査年**")
                st.info(str(r.get('調査年')))

            # 手続件数情報
            total = r.get('総手続件数', 0)
            online = r.get('オンライン手続件数', 0)
            if pd.notna(total) and total != 0:
                st.markdown("**手続件数情報**")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("総手続件数", f"{int(total):,}")
                with col_b:
                    if pd.notna(online):
                        rate = (online / total * 100) if total > 0 else 0
                        st.metric("オンライン化率", f"{rate:.1f}%")

    # 法令情報
    with st.expander(":material/gavel: **法令情報**", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**法令名**")
            st.info(r.get('法令名', '—'))

            if pd.notna(r.get('法令番号')):
                st.markdown("**法令番号**")
                st.info(r.get('法令番号', '—'))

        with cols[1]:
            if pd.notna(r.get('根拠条項')):
                st.markdown("**根拠条項**")
                st.info(r.get('根拠条項', '—'))

            if pd.notna(r.get('根拠条項号')):
                st.markdown("**根拠条項号**")
                st.info(r.get('根拠条項号', '—'))

    # 手続の概要（あれば）
    if pd.notna(r.get('手続の概要')) and str(r.get('手続の概要')).strip():
        with st.expander("📝 **手続の概要**", expanded=True):
            st.write(r.get('手続の概要', '—'))

    # 手続の関係者
    with st.expander("👥 **手続の関係者**", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**手続主体**")
            st.info(r.get('手続主体', '—'))

            st.markdown("**手続の受け手**")
            st.info(r.get('手続の受け手', '—'))

        with col2:
            if pd.notna(r.get('事務区分')):
                st.markdown("**事務区分**")
                st.info(r.get('事務区分', '—'))

            if pd.notna(r.get('府省共通手続')):
                st.markdown("**府省共通手続**")
                st.info(r.get('府省共通手続', '—'))

    # 手数料・経由機関情報
    with st.expander(":material/payments: **手数料・経由機関**", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**手数料情報**")
            fee_required = r.get('手数料等の納付有無', '—')
            if fee_required == '有':
                st.warning(f"手数料: {fee_required}")
            else:
                st.success(f"手数料: {fee_required if fee_required != '—' else '不明'}")

            if pd.notna(r.get('手数料等の納付方法')):
                st.markdown("**納付方法**")
                method = str(r.get('手数料等の納付方法'))
                if 'オンライン' in method or 'ペイジー' in method or 'クレジット' in method:
                    st.success(method)
                else:
                    st.info(method)

            if pd.notna(r.get('手数料等のオンライン納付時の優遇措置')):
                st.markdown("**オンライン納付優遇**")
                st.info(r.get('手数料等のオンライン納付時の優遇措置'))

        with col2:
            st.markdown("**経由機関情報**")
            intermediary = r.get('経由機関', '—')
            if intermediary != '—' and pd.notna(intermediary):
                st.warning(f"経由機関: あり")
                st.info(str(intermediary))
            else:
                st.success("経由機関: なし（直接申請）")

            if pd.notna(r.get('独立行政法人等')):
                st.markdown("**独立行政法人等**")
                st.info(r.get('独立行政法人等'))

    # 連絡先情報
    if any([pd.notna(r.get('電話番号')), pd.notna(r.get('FAX番号')), pd.notna(r.get('Mail'))]):
        with st.expander(":material/support_agent: **連絡先**", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                if pd.notna(r.get('電話番号')):
                    st.markdown("**電話番号**")
                    st.info(str(r.get('電話番号')))
            with col2:
                if pd.notna(r.get('FAX番号')):
                    st.markdown("**FAX番号**")
                    st.info(str(r.get('FAX番号')))
            with col3:
                if pd.notna(r.get('Mail')):
                    st.markdown("**Mail**")
                    st.info(str(r.get('Mail')))

    # システム情報
    with st.expander("💻 **システム情報**", expanded=False):
        cols = st.columns(2)
        with cols[0]:
            if pd.notna(r.get('情報システム(申請)')):
                st.markdown("**申請システム**")
                st.info(r.get('情報システム(申請)', '—'))

        with cols[1]:
            if pd.notna(r.get('情報システム(事務処理)')):
                st.markdown("**事務処理システム**")
                st.info(r.get('情報システム(事務処理)', '—'))

        if pd.notna(r.get('オンライン手続URL')):
            st.markdown("**オンライン手続URL**")
            url = r.get('オンライン手続URL')
            st.markdown(f"[{url}]({url})")

        if pd.notna(r.get('手続URL')):
            st.markdown("**手続情報URL**")
            url = r.get('手続URL')
            st.markdown(f"[{url}]({url})")

    # 添付書類情報
    with st.expander("📎 **添付書類情報**", expanded=False):
        if pd.notna(r.get('申請時に添付させる書類')):
            st.markdown("**必要な添付書類**")
            docs = split_multi_value(r.get('申請時に添付させる書類'))
            if docs:
                st.caption(f"該当書類: {len(docs)}件")
                for d in docs:
                    st.markdown(f"- {d}")
            else:
                st.info(str(r.get('申請時に添付させる書類', '—')))

        cols = st.columns(2)
        with cols[0]:
            if pd.notna(r.get('添付書類等提出の撤廃/省略状況')):
                st.markdown("**撤廃/省略状況**")
                st.info(r.get('添付書類等提出の撤廃/省略状況', '—'))

            if pd.notna(r.get('添付書類等の提出方法')):
                st.markdown("**提出方法**")
                st.info(r.get('添付書類等の提出方法', '—'))

        with cols[1]:
            if pd.notna(r.get('添付書類等への電子署名')):
                st.markdown("**電子署名**")
                st.info(r.get('添付書類等への電子署名', '—'))

    # ライフイベント・士業情報
    with st.expander(":material/target: **ライフイベント・関連士業**", expanded=False):
        # 個人と法人のライフイベントを取得
        personal_life_events = split_multi_value(r.get('手続が行われるイベント(個人)'))
        corporate_life_events = split_multi_value(r.get('手続が行われるイベント(法人)'))

        # 「手続が行われるイベント」カラムも確認（個人/法人の区別がない場合）
        general_events = split_multi_value(r.get('手続が行われるイベント', ''))
        if general_events:
            # イベントを個人と法人に振り分け
            for event in general_events:
                event_lower = event.lower()
                # 個人に関連するキーワード
                if any(keyword in event_lower for keyword in ['出生', '誕生', '結婚', '離婚', '死亡', '転居', '引越', '就学', '就職', '退職', '介護', '妊娠', '出産', '育児', '子育て']):
                    if event not in personal_life_events:
                        personal_life_events.append(event)
                # 法人に関連するキーワード
                elif any(keyword in event_lower for keyword in ['設立', '創業', '開業', '廃業', '清算', '合併', '分割', '事業', '許可', '認可', '登記']):
                    if event not in corporate_life_events:
                        corporate_life_events.append(event)
                # どちらとも判定できない場合は両方に追加
                else:
                    if '法人' in event or '企業' in event or '会社' in event:
                        if event not in corporate_life_events:
                            corporate_life_events.append(event)
                    else:
                        if event not in personal_life_events:
                            personal_life_events.append(event)

        professions = split_multi_value(r.get('申請に関連する士業'))

        col_personal, col_corporate, col_pro = st.columns(3)

        with col_personal:
            st.markdown("**:material/person: 個人ライフイベント**")
            if personal_life_events:
                st.metric("該当イベント数", len(personal_life_events))
                for ev in personal_life_events:
                    st.markdown(f"- {ev}")
            else:
                st.info("該当なし")

        with col_corporate:
            st.markdown("**:material/business: 法人ライフイベント**")
            if corporate_life_events:
                st.metric("該当イベント数", len(corporate_life_events))
                for ev in corporate_life_events:
                    st.markdown(f"- {ev}")
            else:
                st.info("該当なし")

        with col_pro:
            st.markdown("**:material/work: 関連士業**")
            if professions:
                st.metric("関係士業数", len(professions))
                for name in professions:
                    st.markdown(f"- {name}")
            else:
                st.info("該当なし")

    # クイックアクション（一覧へ遷移）
    try:
        with st.expander(":material/rocket_launch: **クイックアクション**", expanded=False):
            law_name = r.get('法令名')
            ministry = r.get('所管府省庁')
            proc_type = r.get('手続類型')
            c1, c2, c3 = st.columns(3)
            with c1:
                if pd.notna(law_name) and st.button("同法令で一覧表示"):
                    st.session_state['search_query'] = str(law_name)
                    mask = df['法令名'].astype(str) == str(law_name)
                    st.session_state['search_results'] = df[mask]
                    st.session_state['show_detail'] = False
                    st.rerun()
            with c2:
                if pd.notna(ministry) and st.button("この府省で一覧表示"):
                    st.session_state['ministry_filter'] = [str(ministry)]
                    # 検索は解除
                    st.session_state.pop('search_results', None)
                    st.session_state.pop('search_query', None)
                    st.session_state['show_detail'] = False
                    st.rerun()
            with c3:
                if pd.notna(proc_type) and st.button("この類型で一覧表示"):
                    st.session_state['type_filter'] = [str(proc_type)]
                    st.session_state.pop('search_results', None)
                    st.session_state.pop('search_query', None)
                    st.session_state['show_detail'] = False
                    st.rerun()
    except Exception:
        pass

    # 比較分析（強化版）
    try:
        with st.expander(":material/analytics: **比較分析・ベンチマーク**", expanded=False):
            # タブで分析を切り替え
            tab1, tab2, tab3 = st.tabs(["同法令比較", "府省比較", "類似手続比較"])

            with tab1:
                law_name = r.get('法令名')
                if pd.notna(law_name):
                    same_law_df = df[df['法令名'] == law_name]

                    if len(same_law_df) > 1:
                        col1, col2 = st.columns(2)

                        with col1:
                            # オンライン化状況分布
                            counts = normalized_counts(same_law_df, 'オンライン化の実施状況', 'オンライン化の実施状況')
                            if counts.sum() > 0:
                                sdf = counts.reset_index()
                                sdf.columns = ['状況', '件数']
                                fig = px.pie(sdf, values='件数', names='状況',
                                           title=f"同法令 {len(same_law_df)}手続のオンライン化状況",
                                           hole=0.4,
                                           color_discrete_map={
                                               '実施済': '#28a745',
                                               '一部実施済': '#ffc107',
                                               '未実施': '#dc3545'
                                           })
                                fig.update_layout(height=300)
                                st.plotly_chart(fig, use_container_width=True, key="plot_1")

                        with col2:
                            # 手続件数分布
                            same_law_df_sorted = same_law_df.nlargest(10, '総手続件数')[['手続名', '総手続件数']]
                            if len(same_law_df_sorted) > 0:
                                fig2 = px.bar(same_law_df_sorted, x='総手続件数', y='手続名',
                                            orientation='h',
                                            title="同法令内の手続件数TOP10")
                                fig2.update_layout(height=300, showlegend=False)
                                st.plotly_chart(fig2, use_container_width=True, key="plot_2")

                        # 現在の手続の位置づけ
                        current_count = r.get('総手続件数', 0)
                        rank = (same_law_df['総手続件数'] > current_count).sum() + 1
                        st.info(f"この手続は同法令内で件数{rank}位/{len(same_law_df)}手続中")
                    else:
                        st.info("同法令の他の手続がありません")
                else:
                    st.info("法令情報がありません")

            with tab2:
                ministry = r.get('所管府省庁')
                if pd.notna(ministry):
                    ministry_df = df[df['所管府省庁'] == ministry]

                    col1, col2 = st.columns(2)

                    with col1:
                        # 手続類型分布
                        tcounts = normalized_counts(ministry_df, '手続類型', '手続類型').head(10)
                        if tcounts.sum() > 0:
                            tdf = tcounts.reset_index()
                            tdf.columns = ['手続類型', '件数']
                            tdf = tdf.sort_values('件数', ascending=False)
                            fig = px.bar(tdf, x='件数', y='手続類型',
                                       orientation='h',
                                       title=f"{ministry}の手続類型TOP10")
                            fig.update_layout(height=300, showlegend=False)
                            st.plotly_chart(fig, use_container_width=True, key="plot_3")

                    with col2:
                        # オンライン化進捗
                        years = ministry_df['調査年'].dropna().unique()
                        if len(years) > 0:
                            yearly_stats = []
                            for year in sorted(years):
                                year_df = ministry_df[ministry_df['調査年'] == year]
                                online = year_df['オンライン化の実施状況'].astype(str).str.contains('実施済').sum()
                                total = len(year_df)
                                if total > 0:
                                    yearly_stats.append({
                                        '年': int(year),
                                        'オンライン化率': online / total * 100
                                    })

                            if yearly_stats:
                                stats_df = pd.DataFrame(yearly_stats)
                                fig = px.line(stats_df, x='年', y='オンライン化率',
                                            title="府省のオンライン化率推移",
                                            markers=True)
                                fig.update_layout(height=300)
                                st.plotly_chart(fig, use_container_width=True, key="plot_4")
                else:
                    st.info("府省情報がありません")

            with tab3:
                # 類似手続の検索（同じ手続類型・手続主体）
                proc_type = r.get('手続類型')
                proc_subject = r.get('手続主体')

                if pd.notna(proc_type) and pd.notna(proc_subject):
                    similar_df = df[
                        (df['手続類型'] == proc_type) &
                        (df['手続主体'] == proc_subject) &
                        (df['手続ID'] != proc_id)
                    ].head(20)

                    if len(similar_df) > 0:
                        # オンライン化状況の比較
                        status_comparison = similar_df.groupby('オンライン化の実施状況').size()

                        col1, col2 = st.columns(2)

                        with col1:
                            if len(status_comparison) > 0:
                                fig = px.pie(values=status_comparison.values,
                                           names=status_comparison.index,
                                           title=f"類似手続（{proc_type}/{proc_subject}）のオンライン化状況",
                                           hole=0.4)
                                fig.update_layout(height=300)
                                st.plotly_chart(fig, use_container_width=True, key="plot_5")

                        with col2:
                            # 府省別分布
                            ministry_dist = similar_df['所管府省庁'].value_counts().head(10)
                            if len(ministry_dist) > 0:
                                fig = px.bar(x=ministry_dist.values, y=ministry_dist.index,
                                           orientation='h',
                                           title="類似手続の府省分布")
                                fig.update_layout(height=300, showlegend=False)
                                st.plotly_chart(fig, use_container_width=True, key="plot_6")

                        # ベンチマーク情報
                        online_rate = similar_df['オンライン化の実施状況'].astype(str).str.contains('実施済').sum() / len(similar_df) * 100
                        st.info(f"類似手続{len(similar_df)}件のうち{online_rate:.1f}%がオンライン化済")

                        if '未実施' in status_val and online_rate > 50:
                            st.warning("類似手続の過半数がオンライン化済。早急な対応を推奨")
                    else:
                        st.info("類似手続が見つかりません")
                else:
                    st.info("手続類型・主体の情報が不足しています")
    except Exception as e:
        st.error(f"比較分析エラー: {e}")
        pass
    # 関連手続（ナビゲーション）
    try:
        law_name = r.get('法令名')
        ministry = r.get('所管府省庁')
        proc_type = r.get('手続類型')
        related = pd.DataFrame()
        if pd.notna(law_name):
            related = df[(df['法令名'] == law_name) & (df['手続ID'] != proc_id)].copy()
        # フォールバック: 同一府省かつ同類型
        if related.empty and pd.notna(ministry) and pd.notna(proc_type):
            related = df[(df['所管府省庁'] == ministry) & (df['手続類型'] == proc_type) & (df['手続ID'] != proc_id)].copy()

        if not related.empty:
            st.markdown(":material/link: **関連する他の手続**")
            # 未実施優先でソートしつつ、直近の重要情報を表示
            def _status_rank(s: str) -> int:
                s = str(s)
                if '未実施' in s:
                    return 0
                if '一部' in s:
                    return 1
                if '実施済' in s:
                    return 2
                return 3

            related['__rank'] = related['オンライン化の実施状況'].apply(_status_rank)
            related = related.sort_values(['__rank', '手続名']).head(5)

            for _, row in related.iterrows():
                rid = str(row['手続ID'])
                cols = st.columns([5, 3, 2])
                with cols[0]:
                    st.markdown(f"**{row.get('手続名', '名称不明')}**  ")
                    st.caption(f"手続ID: {rid}")
                with cols[1]:
                    st.caption(f"オンライン化状況: {row.get('オンライン化の実施状況', '—')}")
                with cols[2]:
                    if st.button("詳細を見る", key=f"rel_{rid}"):
                        st.session_state['selected_procedure_id'] = rid
                        st.session_state['show_detail'] = True
                        st.rerun()
    except Exception:
        pass

    # 全項目データ（折りたたみ）
    with st.expander(":material/list_alt: **全38項目の詳細データ**", expanded=False):
        # 重要な項目を先頭に配置
        important_cols = ['手続ID', '手続名', '法令名', '所管府省庁', 'オンライン化の実施状況']
        other_cols = [c for c in COLUMNS if c not in important_cols]
        ordered_cols = important_cols + other_cols

        data_dict = {}
        for col in ordered_cols:
            if col in r:
                value = r[col]
                if pd.notna(value) and str(value).strip():
                    data_dict[col] = str(value)
                else:
                    data_dict[col] = '—'

        display_df = pd.DataFrame.from_dict(data_dict, orient='index', columns=['値'])
        display_df.index.name = '項目名'
        st.dataframe(display_df, use_container_width=True, height=400)

    # CSVエクスポート
    st.divider()
    csv_data = df_to_csv_bytes(pd.DataFrame([r]))
    st.download_button(
        label=":material/download: この手続の情報をCSVでダウンロード",
        data=csv_data,
        file_name=f"procedure_{proc_id}.csv",
        mime="text/csv"
    )

def main():
    """メインアプリケーション"""

    # モバイル判定用のセッション状態初期化
    if 'screen_width' not in st.session_state:
        st.session_state.screen_width = None

    # JavaScriptで画面幅を取得
    st.components.v1.html(
        """
        <script>
        const streamlitDoc = window.parent.document;
        const width = window.innerWidth;
        streamlitDoc.dispatchEvent(new CustomEvent('streamlit:setComponentValue', {
            detail: {value: width, dataType: 'json'},
        }));
        </script>
        """,
        height=0
    )

    # モバイル判定（768px以下）
    screen_width = st.session_state.get('screen_width', 1200)
    is_mobile = screen_width <= 768 if screen_width is not None else False

    # タイトル（モバイルでは省略）
    if is_mobile:
        st.title(":material/gavel: 行政手続DB")
        st.caption("約75,000件の法令・手続データ")
    else:
        st.title(":material/gavel: 日本の法令に基づく行政手続等オンライン化状況ダッシュボード")
        st.markdown("約75,000件の法令・行政手続データを可視化・分析")

    # データ読み込み（初回のみ）
    if not st.session_state.data_loaded:
        st.session_state.df = load_data()
        st.session_state.data_loaded = True

    df = st.session_state.df

    # サイドバー
    with st.sidebar:
        st.header(":material/search: 統合検索")

        # 統合検索ボックス
        search_query = st.text_input(
            "検索キーワード",
            placeholder="法令名、手続名、府省庁名など...",
            help="全項目を横断して検索します"
        )

        # 検索実行
        if search_query:
            # 検索処理（全カラムを対象）
            mask = pd.Series([False] * len(df), index=df.index)
            for col in df.columns:
                if col in df.columns:
                    try:
                        mask |= df[col].astype(str).str.contains(search_query, na=False, regex=False, case=False)
                    except:
                        # 数値型など文字列変換できないカラムはスキップ
                        continue

            # 検索結果をセッション状態に保存
            st.session_state['search_results'] = df[mask]
            st.session_state['search_query'] = search_query

            # 検索結果のカウント表示
            result_count = mask.sum()
            if result_count > 0:
                st.success(f":material/search: {result_count:,}件の検索結果")
            else:
                st.warning("検索結果が見つかりませんでした")
        else:
            # 検索クエリが空の場合はリセット
            if 'search_results' in st.session_state:
                del st.session_state['search_results']
            if 'search_query' in st.session_state:
                del st.session_state['search_query']

        st.divider()

        st.header(":material/filter_alt: フィルター設定")

        # --- 即時適用フィルター ---
        st.markdown("**府省庁**")
        all_ministries = get_unique_values(df, '所管府省庁')
        # 建制順（歴史的な省庁設立順）に並べ替え
        # 明治期からの伝統的省庁 → 戦後設立 → 平成再編 → 近年設立の順
        ministry_order = [
            "宮内庁",           # 1869年（明治2年）宮内省として設立
            "法務省",           # 1871年（明治4年）司法省として設立
            "外務省",           # 1869年（明治2年）外務省設立
            "財務省",           # 1869年（明治2年）大蔵省として設立、2001年財務省に
            "文部科学省",       # 1871年（明治4年）文部省として設立、2001年文部科学省に
            "農林水産省",       # 1881年（明治14年）農商務省として設立
            "経済産業省",       # 1881年（明治14年）農商務省、1949年通商産業省、2001年経済産業省に
            "国土交通省",       # 1874年（明治7年）内務省、2001年国土交通省に
            "会計検査院",       # 1880年（明治13年）会計検査院設立
            "厚生労働省",       # 1938年（昭和13年）厚生省、2001年厚生労働省に
            "防衛省",           # 1954年（昭和29年）防衛庁、2007年防衛省に
            "総務省",           # 2001年（平成13年）郵政省・自治省・総務庁統合
            "環境省",           # 1971年（昭和46年）環境庁、2001年環境省に
            "内閣官房",         # 戦後の内閣制度
            "内閣府",           # 2001年（平成13年）中央省庁再編で設立
            "警察庁",           # 1954年（昭和29年）設立
            "金融庁",           # 1998年（平成10年）金融監督庁、2000年金融庁
            "消費者庁",         # 2009年（平成21年）設立
            "復興庁",           # 2012年（平成24年）設立
            "デジタル庁",       # 2021年（令和3年）設立
            "こども家庭庁"      # 2023年（令和5年）設立
        ]
        # 順序リストにない省庁を追加
        for m in all_ministries:
            if m not in ministry_order:
                ministry_order.append(m)

        # 実際に存在する省庁のみでリストを作成
        ordered_ministries = [m for m in ministry_order if m in all_ministries]
        selected_ministries = st.multiselect(
            "府省庁を選択",
            ordered_ministries,
            key="ministry_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('所管府省庁', '')
        )

        st.markdown("**オンライン化状況**")
        all_statuses = get_unique_values(df, 'オンライン化の実施状況')
        selected_statuses = st.multiselect(
            "オンライン化状況を選択",
            all_statuses,
            key="status_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('オンライン化の実施状況', '')
        )

        st.markdown("**手続類型**")
        all_types = get_unique_values(df, '手続類型')
        selected_types = st.multiselect(
            "手続類型を選択",
            all_types,
            key="type_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('手続類型', '')
        )

        st.markdown("**手続主体**")
        all_actors = get_unique_values(df, '手続主体')
        selected_actors = st.multiselect(
            "手続主体を選択",
            all_actors,
            key="actor_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('手続主体', '')
        )

        st.markdown("**手続の受け手**")
        all_receivers = get_unique_values(df, '手続の受け手')
        selected_receivers = st.multiselect(
            "手続の受け手を選択",
            all_receivers,
            key="receiver_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('手続の受け手', '')
        )

        st.markdown("**手続件数範囲**")
        count_ranges = [
            "100万件以上",
            "10万件以上100万件未満",
            "1万件以上10万件未満",
            "1000件以上1万件未満",
            "100件以上1000件未満",
            "10件以上100件未満",
            "1件以上10件未満",
            "0件もしくは不明"
        ]
        selected_count_ranges = st.multiselect(
            "手続件数範囲を選択",
            count_ranges,
            key="count_range_filter",
            label_visibility="collapsed",
            help="総手続件数による絞り込み"
        )

        # 即時フィルタリング実行
        filtered_df = filter_dataframe(
            df,
            selected_ministries,
            selected_statuses,
            selected_types,
            selected_receivers,
            actors=selected_actors,
            receivers=selected_receivers,
            office_types=[],  # 詳細フィルター削除
            is_common=[],  # 詳細フィルター削除
            count_ranges=selected_count_ranges,
        )

    # 検索結果の表示
    if 'search_results' in st.session_state and st.session_state.get('search_query'):
        st.info(f":material/search: 検索キーワード: **{st.session_state['search_query']}** の結果を表示中")

        search_df = st.session_state['search_results']

        # 検索結果とフィルターの組み合わせ
        if len(filtered_df) < len(df):  # フィルターが適用されている場合
            # 検索結果とフィルター結果の両方に含まれるデータのみ表示
            common_indices = search_df.index.intersection(filtered_df.index)
            display_df = df.loc[common_indices]
            st.caption(f"検索結果: {len(search_df):,}件 × フィルター結果: {len(filtered_df):,}件 = **{len(display_df):,}件**")
        else:
            display_df = search_df
            st.caption(f"検索結果: **{len(display_df):,}件**")

        # 検索結果をfiltered_dfとして使用
        filtered_df = display_df

        # 検索結果のクリアボタン
        if st.button(":material/refresh: 検索をクリア"):
            del st.session_state['search_results']
            del st.session_state['search_query']
            st.rerun()

        st.divider()

        # 詳細画面の表示（検索結果から遷移）
        if st.session_state.get('show_detail', False) and st.session_state.get('selected_procedure_id'):
            # 戻るボタン
            if st.button("← 検索結果に戻る"):
                st.session_state['show_detail'] = False
                st.session_state['selected_procedure_id'] = None
                st.rerun()

            # 詳細表示
            _render_procedure_detail(st.session_state['selected_procedure_id'], df)
            return

    # メインタブで全体を分ける
    st.header(":material/dashboard: 行政手続オンライン化状況ダッシュボード")
    main_tab1, main_tab2 = st.tabs(["📊 手続種類数ベース分析", "📈 手続件数ベース分析"])

    with main_tab1:
        # ============ 手続種類数ベースの全分析 ============
        st.subheader(":material/analytics: 手続種類数ベース概要")
        with st.container():
            col1, col2, col3, col4, col5 = st.columns(5)
            n_total = len(filtered_df)

            with col1:
                delta_val = n_total - len(df)
                st.metric(
                    ":material/analytics: 総手続種類数",
                    f"{n_total:,}",
                    delta=(f"{delta_val:+,}" if delta_val != 0 else None),
                    delta_color="normal"
                )

            with col2:
                # オンライン化済み手続種類数
                online_types = len(filtered_df[
                    filtered_df['オンライン化の実施状況'].str.contains('実施済', na=False) &
                    ~filtered_df['オンライン化の実施状況'].str.contains('一部', na=False)
                ]) if 'オンライン化の実施状況' in filtered_df.columns else 0
                st.metric(
                    ":material/computer: 完全オンライン化",
                    f"{online_types:,}種類",
                    delta=f"{online_types/n_total*100:.1f}%" if n_total > 0 else "0%"
                )

            with col3:
                # 一部オンライン化手続種類数
                partial_types = len(filtered_df[
                    filtered_df['オンライン化の実施状況'].str.contains('一部', na=False)
                ]) if 'オンライン化の実施状況' in filtered_df.columns else 0
                st.metric(
                    ":material/sync: 一部オンライン化",
                    f"{partial_types:,}種類",
                    delta=f"{partial_types/n_total*100:.1f}%" if n_total > 0 else "0%"
                )

            with col4:
                # 未実施手続種類数
                offline_types = len(filtered_df[
                    filtered_df['オンライン化の実施状況'].str.contains('未実施', na=False)
                ]) if 'オンライン化の実施状況' in filtered_df.columns else 0
                st.metric(
                    ":material/cancel: 未実施",
                    f"{offline_types:,}種類",
                    delta=f"{offline_types/n_total*100:.1f}%" if n_total > 0 else "0%",
                    delta_color="inverse"
                )

            with col5:
                # オンライン化率（種類ベース）
                online_rate_types = ((online_types + partial_types * 0.5) / n_total * 100) if n_total > 0 else 0
                delta_text = None
                if online_rate_types >= 80:
                    delta_text = "優良"
                elif online_rate_types >= 60:
                    delta_text = "良好"
                elif online_rate_types >= 40:
                    delta_text = "要改善"
                else:
                    delta_text = "要対策"
                st.metric(
                    ":material/target: オンライン化率",
                    f"{online_rate_types:.1f}%",
                    delta=delta_text,
                    delta_color="normal" if online_rate_types >= 60 else "inverse"
                )

        # 手続種類数ベースのデジタル化状況インジケーター
        st.divider()
        progress_col1, progress_col2, progress_col3 = st.columns(3)
        n_total = len(filtered_df)

        with progress_col1:
            st.markdown("**:material/trending_up: デジタル化実施状況（種類）**")
            online_procs = len(filtered_df[filtered_df['オンライン化の実施状況'].str.contains('実施済', na=False)]) if 'オンライン化の実施状況' in filtered_df.columns else 0
            partial_procs = len(filtered_df[filtered_df['オンライン化の実施状況'].str.contains('一部', na=False)]) if 'オンライン化の実施状況' in filtered_df.columns else 0
            progress_value = ((online_procs + partial_procs * 0.5) / n_total) if n_total > 0 else 0
            st.progress(progress_value, text=f"実施状況 {progress_value*100:.1f}%")

        with progress_col2:
            st.markdown("**:material/payments: キャッシュレス対応（種類）**")
            cashless_procs = len(filtered_df[filtered_df['手数料等の納付方法'].str.contains('オンライン|ペイジー|クレジット', na=False, regex=True)]) if '手数料等の納付方法' in filtered_df.columns else 0
            fee_required = len(filtered_df[filtered_df['手数料等の納付有無'] == '有']) if '手数料等の納付有無' in filtered_df.columns else 0
            cashless_rate = (cashless_procs / fee_required) if fee_required > 0 else 0
            st.progress(cashless_rate, text=f"対応状況 {cashless_rate*100:.1f}%")

        with progress_col3:
            st.markdown("**:material/description: 書類撤廃状況（種類）**")
            doc_removed = len(filtered_df[filtered_df['添付書類等提出の撤廃/省略状況'].str.contains('撤廃|全廃', na=False, regex=True)]) if '添付書類等提出の撤廃/省略状況' in filtered_df.columns else 0
            doc_removal_rate = (doc_removed / n_total) if n_total > 0 else 0
            st.progress(doc_removal_rate, text=f"撤廃状況 {doc_removal_rate*100:.1f}%")

        st.divider()

        # 手続種類数ベースのメインビジュアライゼーション
        with st.container():
            col1, col2, col3 = st.columns([2, 2, 1.5])

            with col1:
                # オンライン化状況の円グラフ（種類数）
                st.subheader(":material/donut_large: オンライン化実施状況（種類）")
                status_counts = normalized_counts(filtered_df, 'オンライン化の実施状況', 'オンライン化の実施状況')
                if status_counts.sum() > 0:
                    status_df = status_counts.reset_index()
                    status_df.columns = ['状況', '手続種類数']

                    color_map = {
                        '実施済': '#10b981',
                        '一部実施済': '#f59e0b',
                        '未実施': '#ef4444',
                        '実施していない': '#ef4444',
                        '該当なし': '#94a3b8'
                    }

                    fig_pie = px.pie(
                        status_df,
                        values='手続種類数',
                        names='状況',
                        hole=0.6,
                        color='状況',
                        color_discrete_map=color_map
                    )
                    fig_pie.update_traces(
                        textposition='inside',
                        textinfo='percent+label',
                        hovertemplate='%{label}<br>種類数: %{value:,}<br>割合: %{percent}<extra></extra>'
                    )
                    fig_pie.update_layout(height=350, showlegend=True)
                    st.plotly_chart(fig_pie, use_container_width=True, key="plot_7")
                else:
                    st.info("データがありません")

            with col2:
                # 手続類型TOP10（種類数）
                st.subheader(":material/bar_chart: 手続類型TOP10（種類）")
                type_counts = normalized_counts(filtered_df, '手続類型', '手続類型').head(10)
                if type_counts.sum() > 0:
                    type_df = type_counts.reset_index()
                    type_df.columns = ['手続類型', '手続種類数']
                    type_df = type_df.sort_values('手続種類数', ascending=True)

                    fig_bar = px.bar(
                        type_df,
                        x='手続種類数',
                        y='手続類型',
                        orientation='h',
                        color='手続種類数',
                        color_continuous_scale='teal',
                        text='手続種類数'
                    )
                    fig_bar.update_traces(
                        texttemplate='%{text:,}',
                        textposition='outside'
                    )
                    fig_bar.update_layout(
                        height=350,
                        showlegend=False,
                        xaxis_title="手続種類数",
                        yaxis_title="",
                        coloraxis_showscale=False
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, key="plot_8")
                else:
                    st.info("データがありません")

            with col3:
                # 統計サマリー（種類数）
                st.subheader(":material/insights: 統計サマリー")
                st.markdown("**:material/account_balance: 主要府省庁（種類）**")
                ministry_counts = filtered_df['所管府省庁'].value_counts().head(3)
                for idx, (ministry, count) in enumerate(ministry_counts.items(), 1):
                    percentage = (count / n_total * 100) if n_total > 0 else 0
                    st.caption(f"{idx}. {ministry[:10]}... ({count}種類, {percentage:.1f}%)")
        # ============ 手続件数ベースの全分析 ============
        st.subheader(":material/description: 手続件数ベース概要")
        with st.container():
            col1, col2, col3, col4, col5 = st.columns(5)
            total_proc_count = filtered_df['総手続件数'].sum() if '総手続件数' in filtered_df.columns else 0

            with col1:
                st.metric(
                    ":material/description: 総手続件数",
                    f"{int(total_proc_count/1000000):.1f}M" if total_proc_count > 1000000 else f"{int(total_proc_count/1000):.0f}K",
                    help=f"総手続件数: {int(total_proc_count):,}件"
                )

            with col2:
                # オンライン手続件数
                online_count = filtered_df['オンライン手続件数'].sum() if 'オンライン手続件数' in filtered_df.columns else 0
                st.metric(
                    ":material/computer: オンライン件数",
                    f"{int(online_count/1000000):.1f}M" if online_count > 1000000 else f"{int(online_count/1000):.0f}K",
                    help=f"オンライン手続件数: {int(online_count):,}件"
                )

            with col3:
                # オフライン手続件数
                offline_count = total_proc_count - online_count
                st.metric(
                    ":material/cancel: オフライン件数",
                    f"{int(offline_count/1000000):.1f}M" if offline_count > 1000000 else f"{int(offline_count/1000):.0f}K",
                    help=f"オフライン手続件数: {int(offline_count):,}件"
                )

            with col4:
                # オンライン化率（件数ベース）
                online_rate = (online_count / total_proc_count * 100) if total_proc_count else 0
                delta_text = None
                if online_rate >= 80:
                    delta_text = "優良"
                elif online_rate >= 60:
                    delta_text = "良好"
                elif online_rate >= 40:
                    delta_text = "要改善"
                else:
                    delta_text = "要対策"
                st.metric(
                    ":material/target: オンライン化率",
                    f"{online_rate:.1f}%",
                    delta=delta_text,
                    delta_color="normal" if online_rate >= 60 else "inverse"
                )

            with col5:
                # 平均処理件数
                avg_count = total_proc_count / len(filtered_df) if len(filtered_df) > 0 else 0
                st.metric(
                    ":material/equalizer: 平均処理件数",
                    f"{int(avg_count):,}件",
                    help="1手続あたりの平均処理件数"
                )

        # 項目別スナップショット - 手続種類数ベース
        st.divider()
        progress_col1, progress_col2, progress_col3 = st.columns(3)
        n_total = len(filtered_df)

        with progress_col1:
            st.markdown("**:material/trending_up: デジタル化実施状況（種類）**")
            online_procs = len(filtered_df[filtered_df['オンライン化の実施状況'].str.contains('実施済', na=False)]) if 'オンライン化の実施状況' in filtered_df.columns else 0
            partial_procs = len(filtered_df[filtered_df['オンライン化の実施状況'].str.contains('一部', na=False)]) if 'オンライン化の実施状況' in filtered_df.columns else 0
            progress_value = ((online_procs + partial_procs * 0.5) / n_total) if n_total > 0 else 0
            st.progress(progress_value, text=f"実施状況 {progress_value*100:.1f}%")

        with progress_col2:
            st.markdown("**:material/payments: キャッシュレス対応（種類）**")
            cashless_procs = len(filtered_df[filtered_df['手数料等の納付方法'].str.contains('オンライン|ペイジー|クレジット', na=False, regex=True)]) if '手数料等の納付方法' in filtered_df.columns else 0
            fee_required = len(filtered_df[filtered_df['手数料等の納付有無'] == '有']) if '手数料等の納付有無' in filtered_df.columns else 0
            cashless_rate = (cashless_procs / fee_required) if fee_required > 0 else 0
            st.progress(cashless_rate, text=f"対応状況 {cashless_rate*100:.1f}%")

        with progress_col3:
            st.markdown("**:material/description: 書類撤廃状況（種類）**")
            doc_removed = len(filtered_df[filtered_df['添付書類等提出の撤廃/省略状況'].str.contains('撤廃|全廃', na=False, regex=True)]) if '添付書類等提出の撤廃/省略状況' in filtered_df.columns else 0
            doc_removal_rate = (doc_removed / n_total) if n_total > 0 else 0
            st.progress(doc_removal_rate, text=f"撤廃状況 {doc_removal_rate*100:.1f}%")

        st.divider()

        # タブの作成
        tab_type_c, tab_actor_c, tab_life_c = st.tabs([
            "手続類型（件数）",
            "主体・受け手（件数）",
            "ライフイベント・士業（件数）"
        ])

        total_proc_count = filtered_df['総手続件数'].sum() if '総手続件数' in filtered_df.columns else 0

        with tab_type_c:
                st.caption("手続類型別の総手続件数を表示します。")

                # 手続類型別の総手続件数を計算
                type_count_data = []
                for ptype in filtered_df['手続類型'].dropna().unique():
                    type_df = filtered_df[filtered_df['手続類型'] == ptype]
                    count = type_df['総手続件数'].sum() if '総手続件数' in type_df.columns else 0
                    if count > 0:
                        type_count_data.append({
                            '手続類型': ptype,
                            '総手続件数': int(count),
                            '割合(%)': (count / total_proc_count * 100) if total_proc_count > 0 else 0,
                            '説明': PROCEDURE_TYPE_DESCRIPTIONS.get(ptype, '—')
                        })

                if type_count_data:
                    type_df = pd.DataFrame(type_count_data)
                    type_df = type_df.sort_values('総手続件数', ascending=False)
                    st.dataframe(
                        type_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            '手続類型': st.column_config.TextColumn('手続類型', width="medium"),
                            '総手続件数': st.column_config.NumberColumn('総手続件数', format="%d"),
                            '割合(%)': st.column_config.NumberColumn('割合(%)', format="%.1f"),
                            '説明': st.column_config.TextColumn('説明', width="large"),
                        }
                    )
                else:
                    st.info("該当データがありません。")

        with tab_actor_c:
            st.caption("手続主体・受け手別の総手続件数を表示します。")

            col_actor, col_receiver = st.columns(2)

            # 手続主体別の件数集計
            actor_count_data = []
            for actor in filtered_df['手続主体'].dropna().unique():
                actor_df = filtered_df[filtered_df['手続主体'] == actor]
                count = actor_df['総手続件数'].sum() if '総手続件数' in actor_df.columns else 0
                if count > 0:
                    actor_count_data.append({
                        '手続主体': actor,
                        '総手続件数': int(count),
                        '割合(%)': (count / total_proc_count * 100) if total_proc_count > 0 else 0,
                        '説明': ACTOR_DESCRIPTIONS.get(actor, '—')
                    })

            # 手続の受け手別の件数集計
            receiver_count_data = []
            for receiver in filtered_df['手続の受け手'].dropna().unique():
                receiver_df = filtered_df[filtered_df['手続の受け手'] == receiver]
                count = receiver_df['総手続件数'].sum() if '総手続件数' in receiver_df.columns else 0
                if count > 0:
                    receiver_count_data.append({
                        '手続の受け手': receiver,
                        '総手続件数': int(count),
                        '割合(%)': (count / total_proc_count * 100) if total_proc_count > 0 else 0,
                        '説明': RECEIVER_DESCRIPTIONS.get(receiver, '—')
                    })

            with col_actor:
                st.markdown("**手続主体（件数）**")
                if actor_count_data:
                    actor_df = pd.DataFrame(actor_count_data)
                    actor_df = actor_df.sort_values('総手続件数', ascending=False)
                    st.dataframe(
                        actor_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            '手続主体': st.column_config.TextColumn('主体', width="medium"),
                            '総手続件数': st.column_config.NumberColumn('件数', format="%d"),
                            '割合(%)': st.column_config.NumberColumn('割合(%)', format="%.1f"),
                            '説明': st.column_config.TextColumn('説明', width="large"),
                        }
                    )
                else:
                    st.info("主体データがありません")

            with col_receiver:
                st.markdown("**手続の受け手（件数）**")
                if receiver_count_data:
                    receiver_df = pd.DataFrame(receiver_count_data)
                    receiver_df = receiver_df.sort_values('総手続件数', ascending=False)
                    st.dataframe(
                        receiver_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            '手続の受け手': st.column_config.TextColumn('受け手', width="medium"),
                            '総手続件数': st.column_config.NumberColumn('件数', format="%d"),
                            '割合(%)': st.column_config.NumberColumn('割合(%)', format="%.1f"),
                            '説明': st.column_config.TextColumn('説明', width="large"),
                        }
                    )
                else:
                    st.info("受け手データがありません")

            with tab_life_c:
                st.caption("個人・法人のライフイベント別の総手続件数を表示します。")

                col_personal, col_corporate = st.columns(2)

                # 個人ライフイベント別の件数集計
                personal_count_data = []
                for _, row in filtered_df.iterrows():
                    events = split_multi_value(row.get('手続が行われるイベント(個人)'))
                    count = row.get('総手続件数', 0) if '総手続件数' in row else 0
                    for event in events:
                        personal_count_data.append({'イベント': event, '総手続件数': count})

                # 法人ライフイベント別の件数集計
                corporate_count_data = []
                for _, row in filtered_df.iterrows():
                    events = split_multi_value(row.get('手続が行われるイベント(法人)'))
                    count = row.get('総手続件数', 0) if '総手続件数' in row else 0
                    for event in events:
                        corporate_count_data.append({'イベント': event, '総手続件数': count})

                with col_personal:
                    st.markdown("**個人ライフイベント（件数）**")
                    if personal_count_data:
                        personal_df = pd.DataFrame(personal_count_data)
                        personal_summary = personal_df.groupby('イベント').agg({'総手続件数': 'sum'}).reset_index()
                        personal_summary = personal_summary.sort_values('総手続件数', ascending=False).head(15)
                        personal_total = personal_summary['総手続件数'].sum()
                        personal_summary['割合(%)'] = personal_summary['総手続件数'].apply(
                            lambda x: (x / personal_total * 100) if personal_total > 0 else 0
                        )
                        st.dataframe(
                            personal_summary,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'イベント': st.column_config.TextColumn('イベント', width="medium"),
                                '総手続件数': st.column_config.NumberColumn('件数', format="%d"),
                                '割合(%)': st.column_config.NumberColumn('割合(%)', format="%.1f"),
                            }
                        )
                    else:
                        st.info("該当データがありません")

                with col_corporate:
                    st.markdown("**法人ライフイベント（件数）**")
                    if corporate_count_data:
                        corporate_df = pd.DataFrame(corporate_count_data)
                        corporate_summary = corporate_df.groupby('イベント').agg({'総手続件数': 'sum'}).reset_index()
                        corporate_summary = corporate_summary.sort_values('総手続件数', ascending=False).head(15)
                        corporate_total = corporate_summary['総手続件数'].sum()
                        corporate_summary['割合(%)'] = corporate_summary['総手続件数'].apply(
                            lambda x: (x / corporate_total * 100) if corporate_total > 0 else 0
                        )
                        st.dataframe(
                            corporate_summary,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'イベント': st.column_config.TextColumn('イベント', width="medium"),
                                '総手続件数': st.column_config.NumberColumn('件数', format="%d"),
                                '割合(%)': st.column_config.NumberColumn('割合(%)', format="%.1f"),
                            }
                        )
                    else:
                        st.info("該当データがありません")

                st.divider()

                # 士業別の件数集計
                profession_count_data = []
                for _, row in filtered_df.iterrows():
                    professions = split_multi_value(row.get('申請に関連する士業'))
                    count = row.get('総手続件数', 0) if '総手続件数' in row else 0
                    for profession in professions:
                        profession_count_data.append({'士業': profession, '総手続件数': count})

                if profession_count_data:
                    profession_df = pd.DataFrame(profession_count_data)
                    profession_summary = profession_df.groupby('士業').agg({'総手続件数': 'sum'}).reset_index()
                    profession_summary = profession_summary.sort_values('総手続件数', ascending=False).head(15)
                    profession_total = profession_summary['総手続件数'].sum()
                    profession_summary['割合(%)'] = profession_summary['総手続件数'].apply(
                        lambda x: (x / profession_total * 100) if profession_total > 0 else 0
                    )
                    st.dataframe(
                        profession_summary,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            '士業': st.column_config.TextColumn('士業', width="medium"),
                            '総手続件数': st.column_config.NumberColumn('件数', format="%d"),
                            '割合(%)': st.column_config.NumberColumn('割合(%)', format="%.1f"),
                        }
                    )
                else:
                    st.info("士業データがありません")

    # Temporary placeholder for 府省庁別分析 - will be moved to correct location
    if 'オンライン化の実施状況' in filtered_df.columns:
        # 府省庁別の手続数とオンライン化状況を集計
        ministry_stats = []
        ministries = filtered_df['所管府省庁'].value_counts().head(15).index

        for ministry in ministries:
            ministry_df = filtered_df[filtered_df['所管府省庁'] == ministry]

            # オンライン化状況別に集計（正規化された値で比較）
            status_counts = ministry_df['オンライン化の実施状況'].value_counts()

            # 実施済、一部実施済、未実施のパターンで集計
            online_full = 0
            online_partial = 0
            offline = 0

            for status, count in status_counts.items():
                status_normalized = str(status).strip()
                if '実施済' in status_normalized and '一部' not in status_normalized:
                    online_full += count
                elif '一部実施済' in status_normalized or '一部' in status_normalized:
                    online_partial += count
                elif '未実施' in status_normalized or '実施していない' in status_normalized:
                    offline += count

            # オンライン化率を計算
            online_rate = ((online_full + online_partial * 0.5) / len(ministry_df) * 100) if len(ministry_df) > 0 else 0

            ministry_stats.append({
                '府省庁': ministry,
                '実施済': online_full,
                '一部実施済': online_partial,
                '未実施': offline,
                '合計': len(ministry_df),
                'オンライン化率': online_rate
            })

        if ministry_stats:
            # データフレーム作成（合計数でソート - 大きい順）
            stats_df = pd.DataFrame(ministry_stats)
            stats_df = stats_df.sort_values('合計', ascending=True)  # グラフ表示用に昇順（下から上へ多い順）

            # 手続種類数と総手続件数を計算
            for _, row in stats_df.iterrows():
                ministry_df = filtered_df[filtered_df['所管府省庁'] == row['府省庁']]

                # 総手続件数を計算
                online_df = ministry_df[ministry_df['オンライン化の実施状況'].str.contains('実施済', na=False) & ~ministry_df['オンライン化の実施状況'].str.contains('一部', na=False)]
                partial_df = ministry_df[ministry_df['オンライン化の実施状況'].str.contains('一部', na=False)]
                offline_df = ministry_df[ministry_df['オンライン化の実施状況'].str.contains('未実施', na=False)]

                online_count = online_df['総手続件数'].sum() if '総手続件数' in online_df.columns else 0
                partial_count = partial_df['総手続件数'].sum() if '総手続件数' in partial_df.columns else 0
                offline_count = offline_df['総手続件数'].sum() if '総手続件数' in offline_df.columns else 0
                total_count = ministry_df['総手続件数'].sum() if '総手続件数' in ministry_df.columns else 0

                stats_df.loc[stats_df['府省庁'] == row['府省庁'], '実施済_件数'] = int(online_count)
                stats_df.loc[stats_df['府省庁'] == row['府省庁'], '一部実施済_件数'] = int(partial_count)
                stats_df.loc[stats_df['府省庁'] == row['府省庁'], '未実施_件数'] = int(offline_count)
                stats_df.loc[stats_df['府省庁'] == row['府省庁'], '合計_件数'] = int(total_count)

            # タブで手続種類数と手続件数を分ける
            tab1, tab2 = st.tabs(["📊 手続種類数", "📈 総手続件数"])

            with tab1:
                # 手続種類数のTOP15を取得
                top15_types = stats_df.nlargest(15, '合計')
                top15_types = top15_types.sort_values('合計', ascending=True)  # グラフ表示用

                # 2列レイアウト
                col1, col2 = st.columns([3, 1])

                with col1:
                    # 積み上げ棒グラフ（手続種類数）
                    fig = go.Figure()

                    fig.add_trace(go.Bar(
                        name='実施済',
                        y=top15_types['府省庁'],
                        x=top15_types['実施済'],
                        orientation='h',
                        marker_color='#10b981',
                        text=top15_types['実施済'],
                        textposition='inside',
                        texttemplate='%{text}',
                        hovertemplate='実施済: %{x}件<extra></extra>'
                    ))

                    fig.add_trace(go.Bar(
                        name='一部実施済',
                        y=top15_types['府省庁'],
                        x=top15_types['一部実施済'],
                        orientation='h',
                        marker_color='#f59e0b',
                        text=top15_types['一部実施済'],
                        textposition='inside',
                        texttemplate='%{text}',
                        hovertemplate='一部実施済: %{x}件<extra></extra>'
                    ))

                    fig.add_trace(go.Bar(
                        name='未実施',
                        y=top15_types['府省庁'],
                        x=top15_types['未実施'],
                        orientation='h',
                        marker_color='#ef4444',
                        text=top15_types['未実施'],
                        textposition='inside',
                        texttemplate='%{text}',
                        hovertemplate='未実施: %{x}件<extra></extra>'
                    ))

                    fig.update_layout(
                        barmode='stack',
                        title='府省庁別オンライン化状況 - 手続種類数（TOP15）',
                        xaxis_title='手続種類数',
                        yaxis_title='',
                        height=500,
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    st.plotly_chart(fig, use_container_width=True, key="plot_14")

                with col2:
                    # オンライン化率
                    st.markdown("**:material/percent: オンライン化率**")
                    for _, row in top15_types.nlargest(5, 'オンライン化率').iterrows():
                        rate = row['オンライン化率']
                        if rate >= 80:
                            icon = "🟢"
                        elif rate >= 50:
                            icon = "🟡"
                        else:
                            icon = "🔴"
                        st.caption(f"{icon} {row['府省庁'][:10]}: {rate:.1f}%")

            with tab2:
                # 総手続件数のTOP15を取得
                if '合計_件数' in stats_df.columns:
                    top15_counts = stats_df.nlargest(15, '合計_件数')
                    top15_counts = top15_counts.sort_values('合計_件数', ascending=True)  # グラフ表示用

                    # 2列レイアウト
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        # 積み上げ棒グラフ（総手続件数）
                        fig = go.Figure()

                        fig.add_trace(go.Bar(
                            name='実施済',
                            y=top15_counts['府省庁'],
                            x=top15_counts['実施済_件数'],
                            orientation='h',
                            marker_color='#10b981',
                            text=top15_counts['実施済_件数'].apply(lambda x: f"{x:,}"),
                            textposition='inside',
                            texttemplate='%{text}',
                            hovertemplate='実施済: %{x:,}件<extra></extra>'
                        ))

                        fig.add_trace(go.Bar(
                            name='一部実施済',
                            y=top15_counts['府省庁'],
                            x=top15_counts['一部実施済_件数'],
                            orientation='h',
                            marker_color='#f59e0b',
                            text=top15_counts['一部実施済_件数'].apply(lambda x: f"{x:,}"),
                            textposition='inside',
                            texttemplate='%{text}',
                            hovertemplate='一部実施済: %{x:,}件<extra></extra>'
                        ))

                        fig.add_trace(go.Bar(
                            name='未実施',
                            y=top15_counts['府省庁'],
                            x=top15_counts['未実施_件数'],
                            orientation='h',
                            marker_color='#ef4444',
                            text=top15_counts['未実施_件数'].apply(lambda x: f"{x:,}"),
                            textposition='inside',
                            texttemplate='%{text}',
                            hovertemplate='未実施: %{x:,}件<extra></extra>'
                        ))

                        fig.update_layout(
                            barmode='stack',
                            title='府省庁別オンライン化状況 - 総手続件数（TOP15）',
                            xaxis_title='総手続件数',
                            yaxis_title='',
                            height=500,
                            showlegend=True,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1
                            )
                        )
                        st.plotly_chart(fig, use_container_width=True, key="plot_15")

                    with col2:
                        # 手続件数規模
                        st.markdown("**:material/bar_chart: 手続規模**")
                        for _, row in top15_counts.nlargest(5, '合計_件数').iterrows():
                            total = row['合計_件数']
                            if total >= 10000000:  # 1000万以上
                                icon = "🔥"
                            elif total >= 1000000:  # 100万以上
                                icon = "⭐"
                            else:
                                icon = "📊"
                            st.caption(f"{icon} {row['府省庁'][:10]}: {total:,}件")

    else:
        st.warning("オンライン化の実施状況のデータがありません")

    # ============ ALL ANALYSIS SECTIONS NOW PROPERLY IN TABS ============


if __name__ == "__main__":
    main()
