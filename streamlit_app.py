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
from typing import Dict, List, Any, Optional
import re
import gc
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
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"  # モバイルではデフォルトで折りたたみ
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
@media (max-width: 768px) {
    [data-testid="stModal"] > div:first-child {
        max-width: 95% !important;
        margin: 1rem !important;
    }
}
</style>
""", unsafe_allow_html=True)

# データファイルのパス
DATA_DIR = Path(__file__).parent / "docs"
CSV_FILE = DATA_DIR / "20250729_procedures-survey-results_outline_02.csv"
PARQUET_FILE = DATA_DIR / "procedures_data.parquet"

# CSVのカラム定義
COLUMNS = [
    "手続ID",
    "所管府省庁", 
    "手続名",
    "法令名",
    "法令番号",
    "根拠条項号",
    "手続類型",
    "手続主体",
    "手続の受け手",
    "経由機関",
    "独立行政法人等の名称",
    "事務区分",
    "府省共通手続",
    "実施府省庁",
    "オンライン化の実施状況",
    "オンライン化の実施予定及び検討時の懸念点",
    "オンライン化実施時期",
    "申請等における本人確認手法",
    "手数料等の納付有無",
    "手数料等の納付方法",
    "手数料等のオンライン納付時の優遇措置",
    "処理期間(オンライン)",
    "処理期間(非オンライン)",
    "情報システム(申請)",
    "情報システム(事務処理)",
    "総手続件数",
    "オンライン手続件数",
    "非オンライン手続件数",
    "申請書等に記載させる情報",
    "申請時に添付させる書類",
    "添付書類等提出の撤廃/省略状況",
    "添付書類等の提出方法",
    "添付書類等への電子署名",
    "添付形式等が定められた規定",
    "手続が行われるイベント(個人)",
    "手続が行われるイベント(法人)",
    "申請に関連する士業",
    "申請を提出する機関"
]

# --- 項目定義（要約） & 表示順 ---
FIELD_DEFS: Dict[str, str] = {
    "所管府省庁": "手続の根拠法令（条文）を所管する府省庁。",
    "手続名": "手続の名称。",
    "法令名": "手続の根拠となる法令の正式名称。",
    "法令番号": "根拠法令の法令番号。",
    "根拠条項号": "根拠条・項・号の番号。",
    "手続類型": "1申請等 / 2-1申請等に基づく処分通知等 / 2-2申請等に基づかない処分通知等 / 2-3交付等(民間手続) / 3縦覧等 / 4作成・保存等。",
    "手続主体": "手続を行う主体（国、独立行政法人等、地方等、国民等、民間事業者等 等の組合せを含む）。",
    "手続の受け手": "申請等において最終的に手続を受ける者（国、独立行政法人等、地方等、国民等、民間事業者等 等）。",
    "経由機関": "法令に基づき申請等の提出時に経由が必要な機関の種別。",
    "事務区分": "地方公共団体が行う事務の区分（自治事務 / 第1号法定受託事務 / 第2号法定受託事務 / 地方の事務でない）。",
    "府省共通手続": "全府省共通(○) / 一部府省共通(●) / 非共通(×)。",
    "実施府省庁": "当該手続を実施する府省庁（府省共通手続は全回答を列挙）。",
    "オンライン化の実施状況": "1実施済 / 2未実施 / 3適用除外 / 4その他 / 5一部実施済。",
    "オンライン化の実施予定及び検討時の懸念点": "予定または検討時の懸念（制度改正、システム未整備、原本紙等）。",
    "オンライン化実施時期": "オンライン化の実施予定年度（2024〜2030以降）。",
    "申請等における本人確認手法": "押印＋印鑑証明 / 押印 / 署名 / 本人確認書類提示・提出 / その他 / 不要。",
    "手数料等の納付有無": "手数料等の有無。",
    "手数料等の納付方法": "オフライン（窓口/銀行/ATM/コンビニ等）・オンライン（ペイジー/クレカ/QR等）。",
    "手数料等のオンライン納付時の優遇措置": "オンライン納付による減免の有無。",
    "処理期間(オンライン)": "オンライン手続の標準処理期間。",
    "処理期間(非オンライン)": "非オンライン手続の標準処理期間。",
    "情報システム(申請)": "申請等に係るシステム名（受付/申請）。",
    "情報システム(事務処理)": "申請等を受けた後の事務処理システム名。",
    "総手続件数": "令和5年度等の年間総件数（有効数字2桁目安、試算含む）。",
    "オンライン手続件数": "オンラインで実施した件数（該当手続のみ）。",
    "非オンライン手続件数": "オンライン以外で実施した件数。",
    "申請書等に記載させる情報": "申請書記入の必須項目（マイナンバー、法人番号等）。",
    "申請時に添付させる書類": "申請時に提出が必須の典型書類（住民票、戸籍、登記事項等）。",
    "添付書類等提出の撤廃/省略状況": "添付書類撤廃・省略の状況（済/予定/不可/その他）。",
    "添付書類等の提出方法": "電子/原紙/一部電子等の提出方式。",
    "添付書類等への電子署名": "添付書類の電子署名の要否（不要/一部/全て）。",
    "添付形式等が定められた規定": "法令/告示/システム仕様等の規定有無。",
    "手続が行われるイベント(個人)": "個人のライフイベント（妊娠、出生、引越し、就職・転職、税金、年金、死亡・相続 等）。",
    "手続が行われるイベント(法人)": "法人のライフイベント（設立、役員変更、採用・退職、入札・契約、移転、合併・廃業 等）。",
    "申請に関連する士業": "代理申請が可能な士業（弁護士、司法書士、行政書士、税理士、社労士、公認会計士、弁理士 等）。",
    "申請を提出する機関": "提出先機関（本府省庁/出先機関/地方公共団体 等）。",
}

OPTION_ORDERS: Dict[str, List[str]] = {
    # 見やすさのための表示順（存在しない値はそのまま末尾に）
    "手続類型": [
        "申請等", "申請等に基づく処分通知等", "申請等に基づかない処分通知等",
        "交付等（民間手続）", "縦覧等", "作成・保存等"
    ],
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
    if order:
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

# Removed network utils as they are no longer needed

# 手続詳細表示用のダイアログ
@st.dialog("手続詳細情報", width="large")
def show_procedure_detail(procedure_id: str, df: pd.DataFrame):
    """手続の詳細情報をダイアログで表示"""
    # 該当する手続を検索
    procedure = df[df['手続ID'] == procedure_id]
    if procedure.empty:
        st.error(f"手続ID: {procedure_id} が見つかりません")
        return
    
    r = procedure.iloc[0].to_dict()
    
    # ヘッダー情報
    st.markdown(f"### 📋 {r.get('手続名', '—')}")
    
    # 基本情報タブ
    tab1, tab2, tab3, tab4 = st.tabs(["基本情報", "オンライン化", "申請情報", "全データ"])
    
    with tab1:
        st.write("**手続ID:**", r.get('手続ID', '—'))
        st.write("**法令名:**", r.get('法令名', '—'))
        st.write("**所管府省庁:**", r.get('所管府省庁', '—'))
        st.write("**手続類型:**", r.get('手続類型', '—'))
        st.write("**手続の受手・申請先機関:**", r.get('手続の受手・申請先機関', '—'))
        st.write("**法人番号:**", r.get('法人番号', '—'))
        st.write("**手続の主体:**", r.get('手続の主体', '—'))
        
    with tab2:
        st.write("**オンライン化の状況:**", r.get('オンライン化の状況', '—'))
        st.write("**オンライン化実施時期:**", r.get('オンライン化実施時期', '—'))
        st.write("**オンライン利用率:**", r.get('オンライン利用率', '—'))
        st.write("**府省共通手続:**", r.get('府省共通手続', '—'))
        
        st.write("**申請システム名:**", r.get('申請システム名', '—'))
        st.write("**添付書類の名称:**", r.get('添付書類の名称', '—'))
        st.write("**総手続件数:**", r.get('総手続件数', '—'))
        st.write("**オンライン手続件数:**", r.get('オンライン手続件数', '—'))
        st.write("**非オンライン手続件数:**", r.get('非オンライン手続件数', '—'))
        
        # 全データを表形式で表示
        all_data = pd.DataFrame([r]).T
        all_data.columns = ['値']
        st.dataframe(all_data, use_container_width=True)

# ---- Sankeyラベル改行ヘルパ ----
def _wrap_label(text: Any, width: int = 10, max_lines: int = 3) -> str:
    """Wrap long (JP) labels with newlines so Sankey node text doesn't overlap.
    Very simple; just insert <br> every 'width' chars for Plotly."""
    s = str(text).strip()
    if len(s) <= width:
        return s
    lines = []
    for i in range(0, len(s), width):
        if len(lines) >= max_lines:
            lines.append('...')
            break
        lines.append(s[i:i+width])
    return '<br>'.join(lines)

# ---- Multi-value splitter for JP list-like fields ----
def _split_multi_values(val: Any) -> List[str]:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return []
    s = str(val).strip()
    if s.lower() == 'nan' or s == '':
        return []
    for sep in ['、', ',', '，', ';', '；']:
        s = s.replace(sep, '、')
    return [item.strip() for item in s.split('、') if item.strip()]

# --- Top-N + その他 helper ---
def _topn_with_other(series: pd.Series, top: int = 8, other_label: str = 'その他') -> pd.DataFrame:
    """Return a DataFrame with columns [label, 件数] limited to top-N + others."""
    vcount = series.value_counts()
    dfv = pd.DataFrame({'label': vcount.index, '件数': vcount.values})
    if len(dfv) <= top:
        return dfv
    else:
        keep = top
        top_df = dfv.iloc[:keep].copy()
        other_sum = dfv.iloc[keep:]['件数'].sum()
        other_row = pd.DataFrame({'label': [other_label], '件数': [other_sum]})
        dfv = pd.concat([top_df, other_row], ignore_index=True)
    return dfv

# ---- 手続詳細ビューの描画ヘルパ ----
def _render_procedure_detail(proc_id: str, df: pd.DataFrame):
    """選択した手続IDの詳細を表示（全項目表示版）"""
    row = df[df['手続ID'] == proc_id]
    if row.empty:
        st.warning(f"手続ID {proc_id} の詳細が見つかりません")
        return
    r = row.iloc[0]
    
    # タイトル部
    st.title(f"📄 {r.get('手続名', '')}")
    st.caption(f"手続ID: {r.get('手続ID','')} | 所管府省庁: {r.get('所管府省庁','')}")
    
    # 主要指標を上部に表示
    st.markdown("### 📊 主要指標")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("手続ID", r.get('手続ID', '—'))
    with col2:
        status = _normalize_label('オンライン化の実施状況', r.get('オンライン化の実施状況', ''))
        st.metric("オンライン化状況", status if status else "—")
    with col3:
        st.metric("総手続件数", f"{int(r.get('総手続件数', 0) or 0):,}")
    with col4:
        st.metric("オンライン手続件数", f"{int(r.get('オンライン手続件数', 0) or 0):,}")
    with col5:
        rate = float(r.get('オンライン化率', 0) or 0)
        st.metric("オンライン化率", f"{rate:.1f}%")
    
    st.divider()
    
    # 2カラムレイアウトで情報を整理
    col_left, col_right = st.columns(2)
    
    with col_left:
        # 基本情報
        with st.expander("🏛️ **基本情報**", expanded=True):
            items = [
                ("所管府省庁", r.get('所管府省庁', '—')),
                ("手続名", r.get('手続名', '—')),
                ("手続類型", _normalize_label('手続類型', r.get('手続類型', '—'))),
                ("手続主体", r.get('手続主体', '—')),
                ("手続の受け手", r.get('手続の受け手', '—')),
                ("経由機関", r.get('経由機関', '—')),
                ("事務区分", r.get('事務区分', '—')),
                ("府省共通手続", r.get('府省共通手続', '—')),
            ]
            for label, value in items:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**{label}:**")
                with col2:
                    st.text(value if value else '—')
        
        # 法令情報
        with st.expander("⚖️ **法令情報**", expanded=True):
            items = [
                ("法令名", r.get('法令名', '—')),
                ("法令番号", r.get('法令番号', '—')),
                ("根拠条項号", r.get('根拠条項号', '—')),
            ]
            for label, value in items:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**{label}:**")
                with col2:
                    st.text(value if value else '—')
        
        # システム情報
        with st.expander("💻 **システム情報**", expanded=True):
            items = [
                ("申請システム", r.get('情報システム(申請)', '—')),
                ("事務処理システム", r.get('情報システム(事務処理)', '—')),
                ("処理期間(オンライン)", r.get('処理期間(オンライン)', '—')),
                ("処理期間(非オンライン)", r.get('処理期間(非オンライン)', '—')),
            ]
            for label, value in items:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**{label}:**")
                with col2:
                    st.text(value if value else '—')
    
    with col_right:
        # 申請・書類情報
        with st.expander("📝 **申請・書類情報**", expanded=True):
            items = [
                ("本人確認手法", r.get('申請等における本人確認手法', '—')),
                ("提出先機関", r.get('申請を提出する機関', '—')),
            ]
            for label, value in items:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**{label}:**")
                with col2:
                    st.text(value if value else '—')
            
            # 長いテキストの項目
            if pd.notna(r.get('申請書等に記載させる情報')):
                st.markdown("**申請書記載情報:**")
                st.info(r.get('申請書等に記載させる情報', '—'))
            
            if pd.notna(r.get('申請時に添付させる書類')):
                st.markdown("**添付書類:**")
                st.info(r.get('申請時に添付させる書類', '—'))
        
        # 手数料情報
        with st.expander("💰 **手数料情報**", expanded=True):
            items = [
                ("納付有無", r.get('手数料等の納付有無', '—')),
                ("納付方法", r.get('手数料等の納付方法', '—')),
                ("優遇措置", r.get('手数料等のオンライン納付時の優遇措置', '—')),
            ]
            for label, value in items:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**{label}:**")
                with col2:
                    st.text(value if value else '—')
        
        # ライフイベント・士業
        with st.expander("🌟 **ライフイベント・士業**", expanded=True):
            if pd.notna(r.get('手続が行われるイベント(個人)')):
                st.markdown("**個人ライフイベント:**")
                st.info(r.get('手続が行われるイベント(個人)', '—'))
            
            if pd.notna(r.get('手続が行われるイベント(法人)')):
                st.markdown("**法人ライフイベント:**")
                st.info(r.get('手続が行われるイベント(法人)', '—'))
            
            if pd.notna(r.get('申請に関連する士業')):
                st.markdown("**関連士業:**")
                st.info(r.get('申請に関連する士業', '—'))
    
    # 全項目データ（折りたたみ）
    with st.expander("📋 **全38項目の詳細データ**", expanded=False):
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
        label="📥 この手続の情報をCSVでダウンロード",
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
        st.title("⚖️ 行政手続DB")
        st.caption("約75,000件の法令・手続データ")
    else:
        st.title("⚖️ 日本の法令に基づく行政手続等オンライン化状況ダッシュボード")
        st.markdown("約75,000件の法令・行政手続データを可視化・分析")
    
    # データ読み込み（初回のみ）
    if not st.session_state.data_loaded:
        st.session_state.df = load_data()
        st.session_state.data_loaded = True
    
    df = st.session_state.df

    # サイドバー
    with st.sidebar:
        st.header("📋 フィルター設定")

        # ============ 検索機能 ============
        st.markdown("### 🔍 検索")

        # 統合検索ボックス
        search_query = st.text_input(
            "検索キーワード",
            placeholder="手続名、法令名、手続ID等を入力",
            key="unified_search",
            label_visibility="collapsed",
            help="手続名、法令名、法令番号、根拠条項、手続ID、所管府省庁などで検索できます"
        )

        st.divider()

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
            "人事院",           # 1948年（昭和23年）人事院設立
            "内閣官房",         # 1947年（昭和22年）内閣官房設立
            "総務省",           # 1960年（昭和35年）自治省、2001年総務省に
            "厚生労働省",       # 1938年（昭和13年）厚生省、2001年厚生労働省に
            "防衛省",           # 1954年（昭和29年）防衛庁、2007年防衛省に
            "国家公安委員会",   # 1954年（昭和29年）国家公安委員会設立
            "公正取引委員会",   # 1947年（昭和22年）公正取引委員会設立
            "環境省",           # 1971年（昭和46年）環境庁、2001年環境省に
            "内閣府",           # 2001年（平成13年）内閣府設立
            "金融庁",           # 1998年（平成10年）金融監督庁、2000年金融庁に
            "消費者庁",         # 2009年（平成21年）消費者庁設立
            "復興庁",           # 2012年（平成24年）復興庁設立
            "個人情報保護委員会", # 2016年（平成28年）個人情報保護委員会設立
            "カジノ管理委員会", # 2020年（令和2年）カジノ管理委員会設立
            "デジタル庁"        # 2021年（令和3年）デジタル庁設立
        ]
        # 順序付きリストを作成（存在するものだけ）
        ordered_ministries = [m for m in ministry_order if m in all_ministries]
        # リストにない府省庁を追加
        remaining = [m for m in all_ministries if m not in ordered_ministries]
        ordered_ministries.extend(sorted(remaining))
        
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
            "状況を選択",
            all_statuses,
            key="status_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('オンライン化の実施状況', '')
        )

        st.markdown("**手続類型**")
        all_types = get_unique_values(df, '手続類型')
        selected_types = st.multiselect(
            "類型を選択",
            all_types,
            key="type_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('手続類型', '')
        )

        st.markdown("**手続主体**")
        all_actors = get_unique_values(df, '手続主体') if '手続主体' in df.columns else []
        selected_actors = st.multiselect(
            "主体を選択",
            all_actors,
            key="actor_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('手続主体', '')
        )

        st.markdown("**手続の受け手**")
        all_receivers = get_unique_values(df, '手続の受け手') if '手続の受け手' in df.columns else []
        selected_receivers = st.multiselect(
            "受け手を選択",
            all_receivers,
            key="receiver_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('手続の受け手', '')
        )

        st.markdown("**事務区分**")
        all_office_types = get_unique_values(df, '事務区分') if '事務区分' in df.columns else []
        selected_office_types = st.multiselect(
            "事務区分を選択",
            all_office_types,
            key="office_type_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('事務区分', '')
        )

        st.markdown("**府省共通手続**")
        all_common = get_unique_values(df, '府省共通手続') if '府省共通手続' in df.columns else []
        selected_common = st.multiselect(
            "共通手続の種別を選択",
            all_common,
            key="common_filter",
            label_visibility="collapsed",
            help=FIELD_DEFS.get('府省共通手続', '')
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
            office_types=selected_office_types,
            is_common=selected_common,
            count_ranges=selected_count_ranges,
        )
    

    # 検索フィルタリング（サイドバーの検索ボックスから）
    if 'unified_search' in st.session_state and st.session_state.unified_search:
        # 検索対象のカラム
        search_columns = [
            '手続ID', '手続名', '法令名', '法令番号', '根拠条項号',
            '所管府省庁', '手続類型', '手続主体', '手続の受け手',
            '申請書等に記載させる情報', '申請時に添付させる書類',
            '手続が行われるイベント(個人)', '手続が行われるイベント(法人)',
            '申請に関連する士業', '情報システム(申請)', '情報システム(事務処理)'
        ]
        
        # 検索実行（OR条件）
        search_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
        for col in search_columns:
            if col in filtered_df.columns:
                search_mask |= filtered_df[col].astype(str).str.contains(st.session_state.unified_search, na=False, case=False)
        
        filtered_df = filtered_df[search_mask]


    # 詳細画面の表示（検索結果から遷移）

    # ============ 検索機能 ============
    # ============ メインコンテンツ ============

    # 概要統計
    st.header("📊 概要統計")

    # KPIカード（カラムの存在を確認しつつ安全に算出）
    col1, col2, col3, col4 = st.columns(4)
    n_total = len(filtered_df)
    with col1:
        delta_val = n_total - len(df)
        st.metric("総手続数", f"{n_total:,}", delta=(f"{delta_val:+,}" if delta_val != 0 else None))
    with col2:
        total_proc_count = filtered_df['総手続件数'].sum() if '総手続件数' in filtered_df.columns else 0
        st.metric("総手続件数", f"{int(total_proc_count):,}")
    with col3:
        online_count = filtered_df['オンライン手続件数'].sum() if 'オンライン手続件数' in filtered_df.columns else 0
        st.metric("オンライン手続件数", f"{int(online_count):,}")
    with col4:
        online_rate = (online_count / total_proc_count * 100) if total_proc_count else 0
        st.metric("オンライン化率", f"{online_rate:.1f}%")

    # グラフ
    col1, col2 = st.columns(2)

    with col1:
        # オンライン化状況の円グラフ（正規化適用）
        status_counts = normalized_counts(filtered_df, 'オンライン化の実施状況', 'オンライン化の実施状況')
        if status_counts.sum() > 0:
            status_df = status_counts.reset_index()
            status_df.columns = ['オンライン化の実施状況', '件数']
            fig_pie = px.pie(
                status_df,
                values='件数',
                names='オンライン化の実施状況',
                title="オンライン化の実施状況",
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            del fig_pie
        else:
            st.info("該当するデータがありません（円グラフ）")

    with col2:
        # 手続類型の棒グラフ（正規化適用）
        type_counts = normalized_counts(filtered_df, '手続類型', '手続類型')
        # 定義順があればhead(10)後でもOK、なければ頻度上位10
        if '手続類型' in OPTION_ORDERS:
            type_counts = type_counts.head(10)
        else:
            type_counts = type_counts.head(10)
        if type_counts.sum() > 0:
            type_df = type_counts.reset_index()
            type_df.columns = ['手続類型', '件数']
            # 降順にソート（グラフ上で上から下へ多い順に表示）
            type_df = type_df.sort_values('件数', ascending=True)
            fig_bar = px.bar(
                type_df,
                x='件数',
                y='手続類型',
                orientation='h',
                title="手続類型",
                labels={'件数': '件数', '手続類型': '手続類型'}
    ,
                text_auto=True
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            del fig_bar
        else:
            st.info("該当するデータがありません（棒グラフ）")

    # 手続一覧の表示
    st.subheader("📋 手続一覧")

    # 全ての列を表示
    # 選択可能なデータフレームを表示
    event = st.dataframe(
        filtered_df.reset_index(drop=True),
        use_container_width=True,
        height=400,
        selection_mode="single-row",
        on_select="rerun",
        key="procedure_list_table"
    )

    # 選択された行がある場合、詳細をモーダルで表示
    if event.selection and event.selection.rows:
        selected_idx = event.selection.rows[0]
        selected_proc = filtered_df.iloc[selected_idx]

        # 詳細をモーダルで表示（自動的に開く）
        show_procedure_detail(selected_proc['手続ID'], df)

    # CSVダウンロードボタン（全項目）
    csv_data = df_to_csv_bytes(filtered_df)
    st.download_button(
        label="📥 手続一覧をCSVダウンロード",
        data=csv_data,
        file_name="procedures_list.csv",
        mime="text/csv"
    )

    # 法令別分析
    st.header("⚖️ 法令別分析")

    # 法令別の手続数
    st.subheader("📚 法令別手続数（TOP20）")
    law_counts = filtered_df['法令名'].value_counts().head(20)
    if len(law_counts) > 0:
        # 降順にソート（少ない順から多い順へ、グラフ上で上から下へ多い順に表示）
        law_counts = law_counts.sort_values(ascending=True)
        fig_law = px.bar(
            x=law_counts.values,
            y=law_counts.index,
            orientation='h',
            title="法令別手続数",
            labels={'x': '手続数', 'y': '法令名'}
,
                text_auto=True
            )
        fig_law.update_layout(height=600)
        st.plotly_chart(fig_law, use_container_width=True)
        del fig_law

    # 法令別のオンライン化状況
    st.subheader("📊 主要法令のオンライン化状況")

    # 手続数が多い法令TOP10のオンライン化状況
    top_laws = filtered_df['法令名'].value_counts().head(10).index
    law_online_data = []

    for law in top_laws:
        law_df = filtered_df[filtered_df['法令名'] == law]
        total = len(law_df)
        online = len(law_df[law_df['オンライン化の実施状況'].str.contains('実施済', na=False)])
        rate = (online / total * 100) if total > 0 else 0
        law_online_data.append({
            '法令名': law[:30] + ('...' if len(law) > 30 else ''),
            '手続数': total,
            'オンライン化済': online,
            'オンライン化率': rate
        })

    law_online_df = pd.DataFrame(law_online_data)

    # 法令番号の形式別分析
    st.subheader("⚖️ 法令種別の分析")

    # 法律、政令、省令などの分類
    def classify_law_type(law_number):
        if pd.isna(law_number):
            return '不明'
        law_str = str(law_number)
        if '法律' in law_str:
            return '法律'
        elif '政令' in law_str:
            return '政令'
        elif '省令' in law_str or '規則' in law_str:
            return '省令・規則'
        elif '告示' in law_str:
            return '告示'
        elif '通達' in law_str or '通知' in law_str:
            return '通達・通知'
        else:
            return 'その他'

    # in-place 追加は避け、一時DataFrameに列を付与
    law_type_series = filtered_df['法令番号'].apply(classify_law_type) if '法令番号' in filtered_df.columns else pd.Series([], dtype='object')
    tmp_df = filtered_df.assign(法令種別=law_type_series)
    law_type_counts = tmp_df['法令種別'].value_counts()

    col1, col2 = st.columns(2)
    with col1:
        fig_law_type = px.pie(
            values=law_type_counts.values,
            names=law_type_counts.index,
            title="法令種別の分布",
            hole=0.4
        )
        st.plotly_chart(fig_law_type, use_container_width=True)
        del fig_law_type

    with col2:
        # 法令種別ごとのオンライン化率
        law_type_online = tmp_df.groupby('法令種別').agg({
            '手続ID': 'count',
            'オンライン化率': 'mean'
        }).reset_index()
        law_type_online.columns = ['法令種別', '手続数', '平均オンライン化率']
        # 平均オンライン化率で降順ソート
        law_type_online = law_type_online.sort_values('平均オンライン化率', ascending=False)

        fig_law_type_online = px.bar(
            law_type_online,
            x='法令種別',
            y='平均オンライン化率',
            title="法令種別ごとの平均オンライン化率",
            labels={'平均オンライン化率': '平均オンライン化率 (%)'},
            text_auto=True,
            category_orders={'法令種別': law_type_online['法令種別'].tolist()}  # オンライン化率が高い順に並べる
        )
        st.plotly_chart(fig_law_type_online, use_container_width=True)
        del fig_law_type_online

    st.header("🏢 府省庁別分析")

    # 府省庁別のオンライン化状況で積み上げ棒グラフ
    st.subheader("📊 府省庁別手続数（オンライン化状況別）")

    # 府省庁別・オンライン化状況別の集計
    ministry_online_df = filtered_df.groupby(['所管府省庁', 'オンライン化の実施状況']).size().reset_index(name='手続数')

    # 府省庁ごとの合計手続数を計算して、それを基準にソート（全府省庁を含む）
    ministry_totals = ministry_online_df.groupby('所管府省庁')['手続数'].sum().sort_values(ascending=False)

    # オンライン化状況のラベルを正規化
    ministry_online_df['オンライン化の実施状況'] = ministry_online_df['オンライン化の実施状況'].apply(
        lambda x: _normalize_label('オンライン化の実施状況', x)
    )

    # 積み上げ棒グラフ（手続数が多い順に並べ替え）
    fig_ministry = px.bar(
        ministry_online_df,
        x='所管府省庁',
        y='手続数',
        color='オンライン化の実施状況',
        title="府省庁別手続数（オンライン化状況別）",
        labels={'手続数': '手続数', '所管府省庁': '府省庁'},
        color_discrete_map={
            '実施済': '#2ca02c',
            '一部実施済': '#ff7f0e',
            '未実施': '#d62728',
            '適用除外': '#9467bd',
            'その他': '#8c564b'
        },
        text_auto=True,
        category_orders={'所管府省庁': ministry_totals.index.tolist()}  # 手続数が多い順に並べる
    )
    fig_ministry.update_layout(xaxis_tickangle=-45, barmode='stack')
    st.plotly_chart(fig_ministry, use_container_width=True)
    del fig_ministry

    # 府省庁別のオンライン化率
    ministry_stats = filtered_df.groupby('所管府省庁').agg({
        '手続ID': 'count',
        '総手続件数': 'sum',
        'オンライン手続件数': 'sum'
    }).reset_index()
    ministry_stats.columns = ['府省庁', '手続数', '総手続件数', 'オンライン手続件数']
    ministry_stats['オンライン化率'] = (
        ministry_stats['オンライン手続件数'] / ministry_stats['総手続件数'] * 100

    ).round(2)
    ministry_stats = ministry_stats[ministry_stats['総手続件数'] > 0]
    ministry_stats = ministry_stats.sort_values('オンライン化率', ascending=False).head(20)


    st.header("💻 申請システム分析")
    st.caption("申請システムと事務処理システムの利用状況を分析します。")

    col1, col2 = st.columns(2)

    # 申請システム（申請）の分析
    with col1:
        st.subheader("📊 申請システムの利用状況")

        # 申請システムのデータを集計
        system_df = filtered_df[filtered_df['情報システム(申請)'].notna()].copy()

        if len(system_df) > 0:
            # システム別の手続数を集計
            system_counts = system_df['情報システム(申請)'].value_counts().head(20)
            # 降順にソート（グラフ上で上から下へ多い順に表示）
            system_counts = system_counts.sort_values(ascending=True)

            # 申請システム別手続数の棒グラフ
            fig_system = px.bar(
                x=system_counts.values,
                y=system_counts.index,
                orientation='h',
                title="申請システム別手続数（TOP20）",
                labels={'x': '手続数', 'y': '申請システム'},
                text_auto=True
            )
            fig_system.update_layout(height=600)
            st.plotly_chart(fig_system, use_container_width=True)
            del fig_system

            # システム別のオンライン化率
            system_stats = system_df.groupby('情報システム(申請)').agg({
                '手続ID': 'count',
                '総手続件数': 'sum',
                'オンライン手続件数': 'sum'
            }).reset_index()
            system_stats.columns = ['申請システム', '手続数', '総手続件数', 'オンライン手続件数']
            system_stats['オンライン化率'] = (
                system_stats['オンライン手続件数'] / system_stats['総手続件数'] * 100
            ).round(2)
            system_stats = system_stats[system_stats['総手続件数'] > 0]
            system_stats = system_stats.sort_values('オンライン化率', ascending=False).head(20)
        else:
            st.info("申請システムのデータがありません")

    # 事務処理システムの分析
    with col2:
        st.subheader("🖥️ 事務処理システムの利用状況")

        # 事務処理システムのデータを集計
        process_system_df = filtered_df[filtered_df['情報システム(事務処理)'].notna()].copy()

        if len(process_system_df) > 0:
            # システム別の手続数を集計
            process_system_counts = process_system_df['情報システム(事務処理)'].value_counts().head(20)
            # 降順にソート（グラフ上で上から下へ多い順に表示）
            process_system_counts = process_system_counts.sort_values(ascending=True)

            # 事務処理システム別手続数の棒グラフ
            fig_process_system = px.bar(
                x=process_system_counts.values,
                y=process_system_counts.index,
                orientation='h',
                title="事務処理システム別手続数（TOP20）",
                labels={'x': '手続数', 'y': '事務処理システム'},
                text_auto=True
            )
            fig_process_system.update_layout(height=600)
            st.plotly_chart(fig_process_system, use_container_width=True)
            del fig_process_system
        else:
            st.info("事務処理システムのデータがありません")
    
        # 申請システムと事務処理システムの組み合わせ分析
    st.header("📝 申請文書分析")
    st.caption("添付書類や提出方式・電子署名の分布、手続類型との関係を分析します。")

    att_col = '申請時に添付させる書類'
    remove_col = '添付書類等提出の撤廃/省略状況'
    method_col = '添付書類等の提出方法'
    sign_col = '添付書類等への電子署名'

    cols_exist = [c for c in [att_col, remove_col, method_col, sign_col] if c in filtered_df.columns]
    if not cols_exist:
        st.info("添付書類に関する列が見つかりません")
    else:
        # --- 上段：サマリー（円グラフ×3） ---
        dist_cols = []
        if remove_col in filtered_df.columns:
            dist_cols.append((remove_col, '撤廃/省略状況の分布'))
        if method_col in filtered_df.columns:
            dist_cols.append((method_col, '提出方法の分布'))
        if sign_col in filtered_df.columns:
            dist_cols.append((sign_col, '電子署名の要否の分布'))

        if dist_cols:
            pie_top = 8  # 固定値に設定（スライダー削除）
            cols = st.columns(len(dist_cols))
            for idx, (cname, title_txt) in enumerate(dist_cols):
                with cols[idx]:
                    series = filtered_df[cname].dropna().astype(str)
                    series = series[series.str.strip() != '']
                    if len(series) > 0:
                        dfv = _topn_with_other(series, top=pie_top, other_label='その他')
                        dfv[cname] = dfv['label'].map(lambda s: _wrap_label(s, width=10, max_lines=2))
                        fig = px.pie(dfv, values='件数', names=cname, title=title_txt, hole=0.4)
                        fig.update_layout(
                            margin=dict(l=0, r=0, t=40, b=0),
                            height=400,
                            legend=dict(font=dict(size=11), tracegroupgap=4)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        del fig
                    else:
                        st.info(f"'{cname}' のデータがありません")

        st.divider()

        # --- 中段：添付書類トップ ---
        st.subheader("📌 添付書類の頻出（TOP20）")
        if att_col in filtered_df.columns:
            att_series = filtered_df[att_col].dropna().apply(_split_multi_values).explode().astype(str)
            att_series = att_series[att_series.str.strip() != '']
            if len(att_series) > 0:
                top_k = 20  # 固定値に設定（スライダー削除）
                att_counts = att_series.value_counts().head(top_k)
                att_df = att_counts.reset_index()
                att_df.columns = ['添付書類', '件数']
                # 降順にソート（グラフ上で上から下へ多い順に表示）
                att_df = att_df.sort_values('件数', ascending=True)
                fig_att = px.bar(
                    att_df,
                    x='件数', y='添付書類', orientation='h',
                    title=f"添付書類の頻出（TOP{top_k})",
                    labels={'件数': '件数', '添付書類': '添付書類'}
        ,
                text_auto=True
            )
                fig_att.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=520)
                st.plotly_chart(fig_att, use_container_width=True)
                del fig_att
                with st.expander("📥 集計CSVをダウンロード"):
                    st.download_button("添付書類TOPのCSV", df_to_csv_bytes(att_df), file_name="attachment_top.csv", mime="text/csv")
            else:
                st.info("添付書類の値が見つかりません")

        st.divider()

    # ライフイベント分析
    st.header("🌟 ライフイベント分析")
    st.caption("個人および法人のライフイベントごとの手続数を分析します。")

    col1, col2 = st.columns(2)

    # 個人ライフイベント
    with col1:
        st.subheader("👤 個人ライフイベント")
        if '手続が行われるイベント(個人)' in filtered_df.columns:
            # マルチバリュー対応（カンマ区切り等）
            personal_events = filtered_df['手続が行われるイベント(個人)'].dropna().apply(_split_multi_values).explode()
            personal_events = personal_events[personal_events.str.strip() != '']

            if len(personal_events) > 0:
                event_counts = personal_events.value_counts().head(15)
                # 降順にソート（最も多いものが上に）
                event_counts = event_counts.sort_values(ascending=True)

                fig_personal = px.bar(
                    x=event_counts.values,
                    y=event_counts.index,
                    orientation='h',
                    title="個人ライフイベント別手続数（TOP15）",
                    labels={'x': '手続数', 'y': 'ライフイベント'},
                    text_auto=True
                )
                fig_personal.update_layout(height=500)
                st.plotly_chart(fig_personal, use_container_width=True)
                del fig_personal
            else:
                st.info("個人ライフイベントのデータがありません")
        else:
            st.warning("個人ライフイベントの列が存在しません")

    # 法人ライフイベント
    with col2:
        st.subheader("🏢 法人ライフイベント")
        if '手続が行われるイベント(法人)' in filtered_df.columns:
            # マルチバリュー対応（カンマ区切り等）
            corporate_events = filtered_df['手続が行われるイベント(法人)'].dropna().apply(_split_multi_values).explode()
            corporate_events = corporate_events[corporate_events.str.strip() != '']

            if len(corporate_events) > 0:
                event_counts = corporate_events.value_counts().head(15)
                # 降順にソート（最も多いものが上に）
                event_counts = event_counts.sort_values(ascending=True)

                fig_corporate = px.bar(
                    x=event_counts.values,
                    y=event_counts.index,
                    orientation='h',
                    title="法人ライフイベント別手続数（TOP15）",
                    labels={'x': '手続数', 'y': 'ライフイベント'},
                    text_auto=True
                )
                fig_corporate.update_layout(height=500)
                st.plotly_chart(fig_corporate, use_container_width=True)
                del fig_corporate
            else:
                st.info("法人ライフイベントのデータがありません")
        else:
            st.warning("法人ライフイベントの列が存在しません")

    st.divider()

    # 手続主体×受け手の組み合わせ分析
    st.header("🤝 手続主体×受け手の組み合わせ分析")
    st.caption("どの主体からどの受け手への手続が多いかをマトリックス形式で分析します。")

    if '手続主体' in filtered_df.columns and '手続の受け手' in filtered_df.columns:
        # クロス集計表を作成
        cross_tab = pd.crosstab(
            filtered_df['手続主体'],
            filtered_df['手続の受け手']
        )

        if cross_tab.shape[0] > 0 and cross_tab.shape[1] > 0:
            # ヒートマップ表示
            fig_heatmap = px.imshow(
                cross_tab,
                labels=dict(x="手続の受け手", y="手続主体", color="手続数"),
                text_auto=True,
                aspect='auto',
                color_continuous_scale='Blues',
                title="手続主体×受け手の手続数分布"
            )
            fig_heatmap.update_layout(height=600)
            st.plotly_chart(fig_heatmap, use_container_width=True)
            del fig_heatmap
        else:
            st.info("分析に必要なデータが不足しています")
    else:
        st.warning("手続主体または手続の受け手のデータが存在しません")

if __name__ == "__main__":
    main()
