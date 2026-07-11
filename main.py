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
        # 資料來源
        st.markdown("**📌 資料來源**")
        st.markdown(
            "- FinMind API（產業分類）\n"
            "- Yahoo Finance（股價）\n"
            "- twstock（即時行情）\n"
            "- Google News（新聞）"
        )

        st.markdown("")
        st.markdown(
            "🐙 [GitHub Repo](https://github.com/mp0952811570/tw-stock-heatmap) · Streamlit Cloud"
        )

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

    # Banner header — 用 Streamlit 原生方式
    st.markdown(f"## {title_text}")

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
@st.cache_data(ttl=1800, show_spinner="正在計算上中下游熱度（約需 10~30 秒）...")
def compute_chain_heatmap(industry_name: str, stocks_json: str, _cache_version: int = 2):
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

        # 只取前 8 檔做計算樣本（加速）
        heat = get_chain_segment_heat(seg_stocks, max_stocks=8)
        returns = get_chain_segment_returns(seg_stocks, max_stocks=8)

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
    """渲染上中下游熱度比較 — 全部用 Streamlit 原生元件，不用 HTML。"""

    segments = ["上游", "中游", "下游"]
    segment_icons = {"上游": "⬆️", "中游": "➡️", "下游": "⬇️"}

    # 找最熱的段
    heats = {seg: chain_data[seg]["heat"] for seg in segments if chain_data[seg]["heat"] is not None}
    hottest = max(heats, key=lambda k: heats[k]) if heats else None

    st.markdown("### 🔥 上中下游熱度比較")

    if hottest:
        heat_str = f"{chain_data[hottest]['heat']:+.1f}%"
        st.success(f"🏆 最熱段：{segment_icons[hottest]} {hottest}（熱度 {heat_str}）")

    # 三段卡片並列 — 用 st.columns + st.metric
    cols = st.columns(3)
    for i, seg in enumerate(segments):
        data = chain_data[seg]
        with cols[i]:
            count = data["count"]
            heat_val = data["heat"]
            ret_1w = data["return_1w"]

            # 標題
            badge = " 🏆 最熱" if seg == hottest else ""
            st.markdown(f"**{segment_icons[seg]} {seg}{badge}**")
            st.caption(f"{count} 檔個股")

            if count == 0:
                st.info("無代表性個股")
                continue

            # 熱度 — 用 metric 顯示
            heat_str = f"{heat_val:+.1f}%" if heat_val is not None else "N/A"
            st.metric("熱度", heat_str)

            # 1週漲跌 — 用 metric 顯示
            if ret_1w is not None:
                st.metric("1週漲跌", f"{ret_1w:+.2f}%",
                          delta_color="inverse" if ret_1w > 0 else "normal")
            else:
                st.metric("1週漲跌", "N/A")

    # 上中下游個股列表（expander）
    st.markdown("")
    for seg in segments:
        data = chain_data[seg]
        if data["count"] == 0:
            continue

        is_hot = (seg == hottest)
        with st.expander(
            f"{segment_icons[seg]} {seg}（{data['count']} 檔）",
            expanded=is_hot,
        ):
            if data["count"] <= 5:
                for s in data["stocks"]:
                    st.markdown(f"- `{s['id']}` {s['name']}")
            else:
                seg_df = pd.DataFrame(data["stocks"])
                seg_df.columns = ["代碼", "名稱", "市場代碼"]
                market_map = {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}
                seg_df["市場"] = seg_df["市場代碼"].apply(lambda x: market_map.get(x, "?"))
                seg_df = seg_df[["代碼", "名稱", "市場"]]
                st.dataframe(
                    seg_df,
                    use_container_width=True,
                    height=min(300, data["count"] * 35 + 40),
                )

    # 其他分類
    other_count = chain_data.get("其他", {}).get("count", 0)
    if other_count > 0:
        with st.expander(f"📋 未分類（{other_count} 檔）", expanded=False):
            other_stocks = chain_data["其他"]["stocks"]
            other_df = pd.DataFrame([
                {
                    "代碼": s["id"],
                    "名稱": s["name"],
                    "市場": {"twse": "上市", "tpex": "上櫃", "emerging": "興櫃"}.get(
                        s.get("type", ""), "?"
                    ),
                }
                for s in other_stocks
            ])
            st.dataframe(
                other_df,
                use_container_width=True,
                height=min(400, other_count * 35 + 40),
            )


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
        with st.container():
            st.markdown(f"#### [{n['title']}]({n['url']})")
            st.caption(
                f"📌 {n['source']} · {n['published']} · 相關: {n.get('related_stock', '')}"
            )
            if n.get("snippet"):
                st.markdown(n["snippet"])
            st.markdown("---")


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