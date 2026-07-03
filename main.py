"""
台灣股票產業熱度分析儀表板 — Streamlit 主程式
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import time

# 頁面設定
st.set_page_config(
    page_title="台灣股票產業熱度儀表板 🔥",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
)
from modules.news import get_stock_news, get_industry_news


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
        period = st.selectbox(
            "選擇區間",
            ["1週", "1月", "3月", "6月", "1年"],
            index=2,
        )
        period_key = {"1週": "1w", "1月": "1m", "3月": "3m", "6月": "6m", "1年": "1y"}[period]

        st.markdown("---")
        st.subheader("🏭 產業類別")
        industries = get_industry_categories()
        selected_industry = st.selectbox(
            "選擇產業（用於分類瀏覽/新聞模式）",
            ["全部"] + industries,
        )

        st.markdown("---")
        st.markdown(
            "📌 **資料來源**\n\n"
            "- FinMind API（產業分類）\n"
            "- Yahoo Finance（股價）\n"
            "- twstock（即時行情）\n"
            "- Google News（新聞）"
        )
        st.markdown("🐙 [GitHub](https://github.com) · Streamlit Cloud")

        return mode, period, period_key, selected_industry


# ─── 產業熱度排行 ───────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner="正在計算各產業熱度與漲跌幅...")
def compute_industry_heatmap(period_key: str):
    """計算所有產業的熱度與漲跌幅。"""
    stocks = fetch_industry_data()
    index = build_industry_index(stocks)

    results = []
    for cat_name, cat_data in index.items():
        stock_ids = [s["id"] for s in cat_data["stocks"]]
        market_types = [s["type"] for s in cat_data["stocks"]]

        # 僅取前 15 檔代表性個股計算（避免過慢）
        returns = get_industry_returns(stock_ids, market_types, max_stocks=15)
        heat = get_industry_heat(stock_ids, market_types, max_stocks=15)

        results.append({
            "產業": cat_name,
            "圖示": cat_data["icon"],
            "個股數": cat_data["count"],
            "區間漲跌(%)": returns.get(period_key),
            "熱度(%)": heat,
            "1週(%)": returns.get("1w"),
            "1月(%)": returns.get("1m"),
            "3月(%)": returns.get("3m"),
            "6月(%)": returns.get("6m"),
            "1年(%)": returns.get("1y"),
        })

    return pd.DataFrame(results).sort_values("熱度(%)", ascending=False)


def render_heat_overview(df, period_key, period_name):
    """渲染產業總覽頁面——熱度排行榜。"""
    st.title("🔥 台灣股市產業熱度排行榜")

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

    st.markdown("---")

    # 顏色編碼表格
    def color_heat(val):
        if val is None:
            return ""
        if val > 20:
            return "background-color: #ff4500; color: white"
        elif val > 10:
            return "background-color: #ff8c00; color: white"
        elif val > 0:
            return "background-color: #ffd700"
        elif val < -10:
            return "background-color: #4169e1; color: white"
        elif val < 0:
            return "background-color: #87cefa"
        return ""

    def color_return(val):
        if val is None:
            return ""
        if val > 5:
            return "background-color: #ff6b6b; color: white"
        elif val > 0:
            return "background-color: #ffb3b3"
        elif val < -5:
            return "background-color: #4ecdc4; color: white"
        elif val < 0:
            return "background-color: #b3e5e0"
        return ""

    display_df = df.copy()
    display_df["熱度"] = display_df["熱度(%)"].apply(
        lambda x: f"🔥 {x:+.1f}%" if x > 0 else f"❄️ {x:+.1f}%" if x is not None else "—"
    )
    display_cols = ["圖示", "產業", "個股數", "熱度", "區間漲跌(%)"]

    styled = (
        display_df[display_cols]
        .style.map(color_return, subset=["區間漲跌(%)"])
        .map(color_heat, subset=["熱度"])
        .format({"區間漲跌(%)": "{:+.2f}"})
    )
    st.dataframe(styled, use_container_width=True, height=600)


# ─── 產業分類瀏覽 ─────────────────────────────────────────
def render_industry_explorer(index, selected_industry):
    """渲染產業分類瀏覽頁面——可下鑽到個股。"""
    st.title(f"🏭 產業分類瀏覽")

    if selected_industry == "全部":
        # 顯示所有產業的卡片式總覽
        cols = st.columns(3)
        sorted_industries = sorted(index.items(), key=lambda x: x[1]["count"], reverse=True)

        for i, (cat_name, cat_data) in enumerate(sorted_industries):
            with cols[i % 3]:
                chain = cat_data["chain"]
                has_chain = bool(chain.get("上游") or chain.get("中游") or chain.get("下游"))

                st.markdown(
                    f"### {cat_data['icon']} {cat_name}\n"
                    f"*{cat_data['count']} 檔個股*"
                )
                if has_chain:
                    st.caption(
                        f"上游：{'、'.join(chain['上游'][:3]) or '—'}\n\n"
                        f"中游：{'、'.join(chain['中游'][:3]) or '—'}\n\n"
                        f"下游：{'、'.join(chain['下游'][:3]) or '—'}"
                    )
                if st.button(f"🔍 查看 {cat_name}", key=f"view_{cat_name}"):
                    st.session_state["explore_industry"] = cat_name
                    st.rerun()

    elif "explore_industry" in st.session_state and st.session_state["explore_industry"]:
        cat_name = st.session_state["explore_industry"]
        cat_data = index.get(cat_name)

        if not cat_data:
            st.warning("找不到此產業資料")
            return

        st.subheader(f"{cat_data['icon']} {cat_name} — {cat_data['count']} 檔個股")

        # 上中下游架構
        chain = cat_data["chain"]
        if chain.get("上游") or chain.get("中游") or chain.get("下游"):
            with st.expander("🔗 產業鏈結構（上中下游）", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**🔵 上游**")
                    for item in chain.get("上游", []):
                        st.markdown(f"- {item}")
                with c2:
                    st.markdown("**🟡 中游**")
                    for item in chain.get("中游", []):
                        st.markdown(f"- {item}")
                with c3:
                    st.markdown("**🟢 下游**")
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

    else:
        st.info("👈 請從側邊欄選擇一個產業，或點擊上面的產業卡片～")


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
        with st.container():
            st.markdown(f"### [{n['title']}]({n['url']})")
            st.caption(f"📌 {n['source']} · {n['published']} · 相關: {n.get('related_stock', '')}")
            if n.get("snippet"):
                st.markdown(n["snippet"])
            st.markdown("---")


# ─── 主程式入口 ───────────────────────────────────────────
def main():
    # 初始化 session state
    if "explore_industry" not in st.session_state:
        st.session_state["explore_industry"] = None

    mode, period, period_key, selected_industry = render_sidebar()
    index = load_industry_data()

    if mode == "🔥 產業總覽（熱度排行）":
        df = compute_industry_heatmap(period_key)
        render_heat_overview(df, period_key, period)

    elif mode == "🏭 產業分類瀏覽":
        render_industry_explorer(index, selected_industry)

    elif mode == "📰 產業新聞":
        render_news(index, selected_industry)


if __name__ == "__main__":
    main()