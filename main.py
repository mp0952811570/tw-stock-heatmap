"""
台灣股票產業熱度分析儀表板 — Streamlit 主程式
Tailwind-inspired 美化版
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import os

# 頁面設定
st.set_page_config(
    page_title="台灣股票產業熱度儀表板 🔥",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 注入自訂 CSS ──────────────────────────────────────────
_css_path = os.path.join(os.path.dirname(__file__), "static", "style.css")
if os.path.exists(_css_path):
    with open(_css_path) as f:
        _custom_css = f.read()
    st.markdown(f"<style>{_custom_css}</style>", unsafe_allow_html=True)

from modules.industry import (
    fetch_industry_data,
    build_industry_index,
    get_industry_categories,
    INDUSTRY_CHAIN,
)
from modules.stock_data import (
    get_stock_price,
    get_historical_returns,
    get_industry_returns,
    get_industry_heat,
    get_volume_trend,
    get_chain_segment_heat,
    get_chain_segment_returns,
)
from modules.news import get_stock_news, get_industry_news
from modules.chain_classifier import classify_industry_stocks


# ─── 快取資料 ────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_industry_data():
    stocks = fetch_industry_data()
    return build_industry_index(stocks)


# ─── 側邊欄 ───────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.title("📊 台灣股市產業儀表板")
        st.caption(f"資料更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        st.markdown("---")

        # 模式選擇
        mode = st.radio(
            "🔍 瀏覽模式",
            ["🔥 產業總覽（熱度排行）", "🏭 產業分類瀏覽", "📰 產業新聞"],
            key="view_mode",
        )

        st.markdown("---")
        st.subheader("📅 漲跌幅區間")

        # 預設區間
        period_options = ["當日", "前日", "近五日", "近十日", "1週", "1月", "3月", "6月", "1年"]
        period_keys = {"當日": "today", "前日": "prev", "近五日": "5d", "近十日": "10d",
                       "1週": "1w", "1月": "1m", "3月": "3m", "6月": "6m", "1年": "1y"}
        period = st.selectbox("選擇預設區間", period_options, index=4)  # default 1週
        period_key = period_keys[period]

        # 自訂日期範圍
        st.caption("或選擇自訂日期範圍👇")
        use_custom = st.checkbox("📆 使用自訂日期範圍")
        custom_start = None
        custom_end = None
        if use_custom:
            c1, c2 = st.columns(2)
            with c1:
                custom_start = st.date_input("起始日期", value=datetime.now() - timedelta(days=30),
                                             max_value=datetime.now())
            with c2:
                custom_end = st.date_input("結束日期", value=datetime.now(),
                                           max_value=datetime.now())

        st.markdown("---")
        st.subheader("🏭 產業類別")
        industries = get_industry_categories()
        selected_industry = st.selectbox(
            "選擇產業（用於分類瀏覽/新聞模式）",
            ["全部"] + industries,
        )

        st.markdown("---")
        # 資料來源卡片
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #232a3f, #1a1f2e);
            border: 1px solid #3a4263;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-top: 0.5rem;
        ">
            <div style="font-weight: 700; color: #f0b90b; margin-bottom: 0.5rem; font-size: 0.9rem;">📌 資料來源</div>
            <ul style="margin: 0; padding-left: 1.2rem; color: #b0b8c8; font-size: 0.8rem; line-height: 1.6;">
                <li>FinMind API（產業分類）</li>
                <li>Yahoo Finance（股價）</li>
                <li>twstock（即時行情）</li>
                <li>Google News（新聞）</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # GitHub 連結卡片
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(240,185,11,0.15), rgba(230,126,34,0.1));
            border: 1px solid rgba(240,185,11,0.3);
            border-radius: 0.5rem;
            padding: 0.8rem 1rem;
            text-align: center;
            margin-top: 0.6rem;
        ">
            <a href="https://github.com/mp0952811570/tw-stock-heatmap"
               style="color: #f0b90b; text-decoration: none; font-weight: 600; font-size: 0.85rem;">
                🐙 GitHub Repo · Streamlit Cloud
            </a>
        </div>
        """, unsafe_allow_html=True)

        return mode, period, period_key, selected_industry, use_custom, custom_start, custom_end


# ─── 產業熱度排行 ───────────────────────────────────────
# IMPORTANT: cache key includes _v2 so old cached DataFrames with different columns are invalidated
@st.cache_data(ttl=1800, show_spinner="正在計算各產業熱度與漲跌幅...")
def compute_industry_heatmap(period_key: str, custom_start: str = None, custom_end: str = None, _cache_version: int = 2):
    """計算所有產業的熱度與漲跌幅。支援固定區間或自訂日期範圍。"""
    stocks = fetch_industry_data()
    index = build_industry_index(stocks)

    # 決定顯示的 key
    if custom_start and custom_end:
        display_key = "custom"
    else:
        display_key = period_key

    results = []
    for cat_name, cat_data in index.items():
        stock_ids = [s["id"] for s in cat_data["stocks"]]
        market_types = [s["type"] for s in cat_data["stocks"]]

        returns = get_industry_returns(stock_ids, market_types, max_stocks=15,
                                       custom_start=custom_start, custom_end=custom_end)
        heat = get_industry_heat(stock_ids, market_types, max_stocks=15)

        results.append({
            "產業": cat_name,
            "圖示": cat_data["icon"],
            "個股數": cat_data["count"],
            "區間漲跌(%)": returns.get(display_key),
            "熱度(%)": heat,
            "today_ret": returns.get("today"),
            "prev_ret": returns.get("prev"),
            "5d_ret": returns.get("5d"),
            "10d_ret": returns.get("10d"),
            "1w_ret": returns.get("1w"),
            "1m_ret": returns.get("1m"),
            "3m_ret": returns.get("3m"),
            "6m_ret": returns.get("6m"),
            "1y_ret": returns.get("1y"),
        })

    return pd.DataFrame(results).sort_values("熱度(%)", ascending=False)


def render_heat_overview(df, period_key, period_name, use_custom=False, custom_start=None, custom_end=None):
    """渲染產業總覽頁面——熱度排行榜。"""
    # 顯示區間 title
    if use_custom and custom_start and custom_end:
        title_period = f"{custom_start} ~ {custom_end}"
        title_text = f"🔥 台灣股市產業熱度排行榜（{title_period}）"
    else:
        title_text = f"🔥 台灣股市產業熱度排行榜（{period_name}）"

    # Banner header
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #232a3f 0%, #2d3556 50%, #1a1f2e 100%);
        border: 1px solid rgba(240,185,11,0.25);
        border-radius: 0.75rem;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3), 0 0 20px rgba(240,185,11,0.08);
    ">
        <h1 style="
            margin: 0;
            font-size: 1.8rem;
            color: #f0b90b;
            -webkit-text-fill-color: #f0b90b;
        ">{title_text}</h1>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        hot_count = int(len(df[df["熱度(%)"].fillna(0) > 0]))
        st.metric("📈 升溫產業數", hot_count, delta=f"/ {len(df)}")
    with col2:
        avg_heat = df["熱度(%)"].mean()
        st.metric("🌡️ 全市場平均熱度", f"{avg_heat:+.1f}%" if pd.notna(avg_heat) else "N/A")
    with col3:
        top_industry = df.iloc[0]["產業"] if len(df) > 0 else "N/A"
        st.metric("🏆 最熱產業", top_industry)

    # 各區間快速摘要
    st.markdown("---")
    st.subheader("📊 各區間全市場平均漲跌幅")
    period_labels = {
        "today_ret": "當日", "prev_ret": "前日", "5d_ret": "近五日", "10d_ret": "近十日",
        "1w_ret": "1週", "1m_ret": "1月", "3m_ret": "3月", "6m_ret": "6月", "1y_ret": "1年",
    }
    chips = st.columns(len(period_labels))
    for chip_col, (df_key, display_name) in zip(chips, period_labels.items()):
        avg_val = df[df_key].mean()
        with chip_col:
            st.metric(
                display_name,
                f"{avg_val:+.2f}%" if pd.notna(avg_val) else "N/A",
                delta_color="normal" if (avg_val and avg_val > 0) else "inverse",
            )

    st.markdown("---")

    # 顏色編碼表格 — 台股慣例：紅漲綠跌
    def color_heat(val):
        if pd.isna(val):
            return ""
        if val > 20:
            return "background-color: #e74c3c; color: white; font-weight: 600"
        elif val > 10:
            return "background-color: #ff7878; color: white; font-weight: 500"
        elif val > 0:
            return "background-color: #ffccc9; color: #7a1f1f"
        elif val < -10:
            return "background-color: #2ecc71; color: white; font-weight: 600"
        elif val < 0:
            return "background-color: #a8f0c4; color: #14532d"
        return ""

    def color_return(val):
        if pd.isna(val):
            return ""
        if val > 5:
            return "background-color: #e74c3c; color: white; font-weight: 600"
        elif val > 0:
            return "background-color: #ffccc9; color: #7a1f1f"
        elif val < -5:
            return "background-color: #2ecc71; color: white; font-weight: 600"
        elif val < 0:
            return "background-color: #a8f0c4; color: #14532d"
        return ""

    display_df = df.copy()
    display_cols = ["圖示", "產業", "個股數", "熱度(%)", "區間漲跌(%)"]

    styled = (
        display_df[display_cols]
        .style.map(color_heat, subset=["熱度(%)"])
        .map(color_return, subset=["區間漲跌(%)"])
        .format({
            "熱度(%)": "{:+.1f}%",
            "區間漲跌(%)": "{:+.2f}%",
        })
    )
    st.dataframe(styled, use_container_width=True, height=600)


# ─── 產業上中下游熱度比較 ─────────────────────────────────
@st.cache_data(ttl=1800, show_spinner="正在計算上中下游熱度...")
def compute_chain_heatmap(industry_name: str, stocks_json: str, _cache_version: int = 1):
    """計算某產業上中下游各段熱度與漲跌幅。"""
    import json as _json
    stocks = _json.loads(stocks_json)

    # 分類到上中下游
    classified = classify_industry_stocks(stocks, industry_name)

    results = {}
    for segment in ["上游", "中游", "下游"]:
        seg_stocks = classified[segment]
        if not seg_stocks:
            results[segment] = {
                "count": 0,
                "heat": None,
                "return_1w": None,
                "return_1m": None,
                "stocks": [],
                "labels": [],
            }
            continue

        heat = get_chain_segment_heat(seg_stocks, max_stocks=15)
        returns = get_chain_segment_returns(seg_stocks, max_stocks=15)

        results[segment] = {
            "count": len(seg_stocks),
            "heat": heat,
            "return_1w": returns.get("1w"),
            "return_1m": returns.get("1m"),
            "stocks": seg_stocks,
        }

    results["其他"] = {
        "count": len(classified["其他"]),
        "heat": None,
        "return_1w": None,
        "return_1m": None,
        "stocks": classified["其他"],
    }

    return results


def render_chain_heatmap(chain_data: dict, industry_icon: str, industry_name: str):
    """渲染上中下游熱度比較 visual block。"""

    # 準備三段資料
    segments = ["上游", "中游", "下游"]
    segment_icons = {"上游": "⬆️", "中游": "➡️", "下游": "⬇️"}
    segment_colors = {"上游": "#e67e22", "中游": "#f0b90b", "下游": "#2ecc71"}

    # 找最熱的段
    heats = {seg: chain_data[seg]["heat"] for seg in segments if chain_data[seg]["heat"] is not None}
    hottest = max(heats, key=lambda k: heats[k]) if heats else None

    st.markdown("### 🔥 上中下游熱度比較")

    if hottest:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(240,185,11,0.15), rgba(230,126,34,0.08));
            border: 1px solid rgba(240,185,11,0.25);
            border-radius: 0.5rem;
            padding: 0.8rem 1.2rem;
            margin-bottom: 1rem;
        ">
            <span style="color: #f0b90b; font-weight: 700; font-size: 1rem;">
                🏆 最熱段：
            </span>
            <span style="color: #f5f5f5; font-weight: 600; font-size: 1rem;">
                {segment_icons[hottest]} {hottest}
            </span>
            <span style="color: #b0b8c8; font-size: 0.9rem;">
                （熱度 {chain_data[hottest]['heat']:+.1f}%）
            </span>
        </div>
        """, unsafe_allow_html=True)

    # 三段卡片並列
    cols = st.columns(3)
    for i, seg in enumerate(segments):
        data = chain_data[seg]
        with cols[i]:
            heat_val = data["heat"]
            ret_1w = data["return_1w"]
            count = data["count"]

            # 判定熱度顏色
            if heat_val is None:
                heat_color = "#b0b8c8"
                heat_bar_width = "0%"
                heat_text = "N/A"
            elif heat_val > 10:
                heat_color = "#e74c3c"
                heat_bar_width = min(100, int(heat_val * 2))
                heat_text = f"{heat_val:+.1f}%"
            elif heat_val > 0:
                heat_color = "#f0b90b"
                heat_bar_width = min(100, int(heat_val * 3))
                heat_text = f"{heat_val:+.1f}%"
            else:
                heat_color = "#2ecc71"
                heat_bar_width = min(100, int(abs(heat_val) * 3))
                heat_text = f"{heat_val:+.1f}%"

            is_hottest = (seg == hottest)
            border_color = segment_colors[seg] if is_hottest else "#3a4263"
            glow = "box-shadow: 0 0 16px rgba(240,185,11,0.15);" if is_hottest else ""

            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #232a3f, #1a1f2e);
                border: 2px solid {border_color};
                border-radius: 0.5rem;
                padding: 1rem;
                margin: 0.3rem 0;
                {glow}
            ">
                <div style="font-size: 1.1rem; font-weight: 700; color: #f5f5f5; margin-bottom: 0.3rem;">
                    {segment_icons[seg]} {seg}
                    {f'<span style="color:#f0b90b;font-size:0.75rem;margin-left:0.3rem;">🏆 最熱</span>' if is_hottest else ''}
                </div>
                <div style="color: #b0b8c8; font-size: 0.8rem; margin-bottom: 0.6rem;">
                    {count} 檔個股
                </div>

                <!-- 熱度 bar -->
                <div style="margin-bottom: 0.5rem;">
                    <div style="color: #b0b8c8; font-size: 0.75rem; margin-bottom: 0.2rem;">熱度</div>
                    <div style="background: #1a1f2e; border-radius: 0.25rem; height: 0.6rem; overflow: hidden;">
                        <div style="
                            background: {heat_color};
                            height: 100%;
                            width: {heat_bar_width};
                            border-radius: 0.25rem;
                            transition: width 0.5s ease;
                        "></div>
                    </div>
                    <div style="color: {heat_color}; font-size: 0.9rem; font-weight: 700; margin-top: 0.2rem;">
                        {heat_text}
                    </div>
                </div>

                <!-- 1週漲跌 -->
                <div style="margin-top: 0.5rem;">
                    <div style="color: #b0b8c8; font-size: 0.75rem;">1週漲跌</div>
                    <div style="
                        color: {'#e74c3c' if ret_1w and ret_1w > 0 else '#2ecc71' if ret_1w else '#b0b8c8'};
                        font-size: 0.95rem;
                        font-weight: 700;
                    ">
                        {f'{ret_1w:+.2f}%' if ret_1w is not None else 'N/A'}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 上中下游個股列表（expander）
    st.markdown("")
    for seg in segments:
        data = chain_data[seg]
        if data["count"] == 0:
            continue

        with st.expander(f"{segment_icons[seg]} {seg}（{data['count']} 檔）", expanded=(seg == hottest)):
            if data["count"] <= 5:
                # 少量個股用 markdown 列表
                for s in data["stocks"]:
                    st.markdown(f"- `{s['id']}` {s['name']}")
            else:
                # 多量用 dataframe
                seg_df = pd.DataFrame(data["stocks"])
                seg_df.columns = ["代碼", "名稱", "市場代碼"]
                market_map = {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}
                seg_df["市場"] = seg_df["市場代碼"].apply(lambda x: market_map.get(x, "?"))
                seg_df = seg_df[["代碼", "名稱", "市場"]]
                st.dataframe(seg_df, use_container_width=True, height=min(300, data["count"] * 35 + 40))

    # 其他分類（如果有）
    other_count = chain_data.get("其他", {}).get("count", 0)
    if other_count > 0:
        with st.expander(f"📋 未分類（{other_count} 檔）", expanded=False):
            other_stocks = chain_data["其他"]["stocks"]
            other_df = pd.DataFrame([
                {"代碼": s["id"], "名稱": s["name"],
                 "市場": {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}.get(s.get("type",""), "?")}
                for s in other_stocks
            ])
            st.dataframe(other_df, use_container_width=True, height=min(400, other_count * 35 + 40))


# ─── 產業分類瀏覽 ─────────────────────────────────────────
def render_industry_explorer(index, selected_industry):
    """渲染產業分類瀏覽頁面——可下鑽到個股。"""
    # 決定要顯示哪個產業：優先用 session_state（卡片按鈕），否則用下拉選單
    cat_name = st.session_state.get("explore_industry") or (
        selected_industry if selected_industry != "全部" else None
    )

    if cat_name is None:
        # 顯示所有產業的卡片式總覽
        st.title("🏭 產業分類瀏覽")
        cols = st.columns(3)
        sorted_industries = sorted(index.items(), key=lambda x: x[1]["count"], reverse=True)

        for i, (name, cat_data) in enumerate(sorted_industries):
            with cols[i % 3]:
                chain = cat_data["chain"]
                has_chain = bool(chain.get("上游") or chain.get("中游") or chain.get("下游"))

                st.markdown(
                    f"### {cat_data['icon']} {name}\n"
                    f"*{cat_data['count']} 檔個股*"
                )
                if has_chain:
                    st.caption(
                        f"上游：{'、'.join(chain['上游'][:3]) or '—'}\n\n"
                        f"中游：{'、'.join(chain['中游'][:3]) or '—'}\n\n"
                        f"下游：{'、'.join(chain['下游'][:3]) or '—'}"
                    )
                if st.button(f"🔍 查看 {name}", key=f"view_{name}"):
                    st.session_state["explore_industry"] = name
                    st.rerun()

    else:
        cat_data = index.get(cat_name)

        if not cat_data:
            st.warning("找不到此產業資料")
            return

        st.markdown(f"### {cat_data['icon']} {cat_name} — {cat_data['count']} 檔個股")

        # ── 上中下游熱度比較（新功能）──
        import json
        stocks_json = json.dumps(cat_data["stocks"], ensure_ascii=False)
        chain_data = compute_chain_heatmap(cat_name, stocks_json)
        render_chain_heatmap(chain_data, cat_data["icon"], cat_name)

        st.markdown("")

        # ── 原有：產業鏈結構說明 ──
        chain = cat_data["chain"]
        if chain.get("上游") or chain.get("中游") or chain.get("下游"):
            with st.expander("🔗 產業鏈說明（參考架構）", expanded=False):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**⬆️ 上游**")
                    for item in chain.get("上游", []):
                        st.markdown(f"- {item}")
                with c2:
                    st.markdown("**➡️ 中游**")
                    for item in chain.get("中游", []):
                        st.markdown(f"- {item}")
                with c3:
                    st.markdown("**⬇️ 下游**")
                    for item in chain.get("下游", []):
                        st.markdown(f"- {item}")

        # 個股列表 + 漲跌幅
        st.markdown("### 📋 個股列表與漲跌幅")

        # 取前 30 檔代表性個股
        sample_stocks = cat_data["stocks"][:30]

        @st.cache_data(ttl=600, show_spinner="載入個股數據中...")
        def load_stock_details(stock_list_json):
            import json
            stocks = json.loads(stock_list_json)
            stock_data = []
            for s in stocks:
                try:
                    returns = get_historical_returns(s["id"], s["type"])
                    price_info = get_stock_price(s["id"], s["type"])
                    stock_data.append({
                        "代碼": s["id"],
                        "名稱": s["name"],
                        "市場": "上市" if s["type"] == "twse" else "上櫃" if s["type"] == "tpex" else "興櫃",
                        "現價": price_info.get("price") if price_info else None,
                        "漲跌(%)": price_info.get("change_pct") if price_info else None,
                        "1週(%)": returns.get("1w"),
                        "1月(%)": returns.get("1m"),
                        "3月(%)": returns.get("3m"),
                    })
                except Exception:
                    stock_data.append({
                        "代碼": s["id"], "名稱": s["name"],
                        "市場": "上市" if s["type"] == "twse" else "上櫃" if s["type"] == "tpex" else "興櫃",
                        "現價": None, "漲跌(%)": None,
                        "1週(%)": None, "1月(%)": None, "3月(%)": None,
                    })
            return pd.DataFrame(stock_data)

        import json
        df = load_stock_details(json.dumps(sample_stocks, ensure_ascii=False))
        st.dataframe(
            df.style.format({
                "現價": "{:.1f}",
                "漲跌(%)": "{:+.2f}",
                "1週(%)": "{:+.2f}",
                "1月(%)": "{:+.2f}",
                "3月(%)": "{:+.2f}",
            }),
            use_container_width=True,
            height=500,
        )

        if st.button("🔙 回到產業總覽"):
            st.session_state["explore_industry"] = None
            st.rerun()


# ─── 產業新聞 ─────────────────────────────────────────────
def render_news(index, selected_industry):
    """渲染新聞頁面。"""
    st.title("📰 產業相關新聞")

    if selected_industry == "全部":
        st.info("👈 請從側邊欄選擇一個產業來查看相關新聞～")
        return

    cat_data = index.get(selected_industry)
    if not cat_data:
        st.warning("找不到產業資料")
        return

    st.subheader(f"{cat_data['icon']} {selected_industry} — 最新新聞")

    with st.spinner("正在取得新聞..."):
        sample = cat_data["stocks"][:5]
        news = get_industry_news(selected_industry, sample, max_per_stock=3)

    if not news:
        st.warning("暫無相關新聞")
        return

    for n in news:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #232a3f, #1a1f2e);
            border: 1px solid #3a4263;
            border-left: 4px solid #f0b90b;
            border-radius: 0.5rem;
            padding: 1.2rem 1.5rem;
            margin: 0.8rem 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.25);
            transition: all 0.3s ease;
        " onmouseover="this.style.borderColor='#f0b90b'; this.style.transform='translateX(4px)';"
          onmouseout="this.style.borderColor='#3a4263'; this.style.transform='translateX(0)';">
            <a href="{n['url']}" target="_blank" style="
                color: #fcd535;
                text-decoration: none;
                font-size: 1.05rem;
                font-weight: 700;
            ">{n['title']}</a>
            <div style="
                color: #b0b8c8;
                font-size: 0.8rem;
                margin-top: 0.4rem;
            ">📌 {n['source']} · {n['published']} · 相關: {n.get('related_stock', '')}</div>
            <div style="
                color: #d5d8e0;
                font-size: 0.85rem;
                margin-top: 0.5rem;
                line-height: 1.5;
            ">{n.get('snippet', '')}</div>
        </div>
        """, unsafe_allow_html=True)


# ─── 主程式入口 ───────────────────────────────────────────
def main():
    # 初始化 session state
    if "explore_industry" not in st.session_state:
        st.session_state["explore_industry"] = None

    mode, period, period_key, selected_industry, use_custom, custom_start, custom_end = render_sidebar()
    index = load_industry_data()

    # 格式化自訂日期
    custom_start_str = custom_start.strftime("%Y-%m-%d") if custom_start else None
    custom_end_str = custom_end.strftime("%Y-%m-%d") if custom_end else None

    if mode == "🔥 產業總覽（熱度排行）":
        df = compute_industry_heatmap(period_key, custom_start_str, custom_end_str)
        render_heat_overview(df, period_key, period, use_custom, custom_start_str, custom_end_str)

    elif mode == "🏭 產業分類瀏覽":
        render_industry_explorer(index, selected_industry)

    elif mode == "📰 產業新聞":
        render_news(index, selected_industry)


if __name__ == "__main__":
    main()