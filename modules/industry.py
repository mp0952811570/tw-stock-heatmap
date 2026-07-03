"""
台灣股票產業分類模組 — 從 FinMind API 取得產業分類，整合上下游結構。
"""

import requests
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 證交所 + Yahoo 雙重產業分類映射
# FinMind 的 57 個產業類別 → 對應的上中下游結構
INDUSTRY_CHAIN = {
    "半導體業": {
        "上游": ["IC設計", "矽智財", "EDA工具"],
        "中游": ["晶圓代工", "記憶體製造"],
        "下游": ["封裝測試", "IC通路"],
        "icon": "🔷",
    },
    "電子零組件業": {
        "上游": ["原料/基板", "被動元件"],
        "中游": ["PCB製造", "連接器"],
        "下游": ["模組組裝", "終端應用"],
        "icon": "🔌",
    },
    "電腦及週邊設備業": {
        "上游": ["晶片/零組件"],
        "中游": ["組裝/代工"],
        "下游": ["品牌/通路"],
        "icon": "💻",
    },
    "通信網路業": {
        "上游": ["晶片設計", "光纖/線纜"],
        "中游": ["網通設備", "基地台"],
        "下游": ["電信服務", "終端裝置"],
        "icon": "📡",
    },
    "光電業": {
        "上游": ["材料/元件"],
        "中游": ["面板製造", "LED/光學"],
        "下游": ["顯示器/模組"],
        "icon": "💡",
    },
    "電子通路業": {
        "上游": ["原廠代理"],
        "中游": ["通路分銷"],
        "下游": ["零售/電商"],
        "icon": "🏪",
    },
    "資訊服務業": {
        "上游": ["軟體開發"],
        "中游": ["系統整合"],
        "下游": ["雲端/資安服務"],
        "icon": "🖥️",
    },
    "其他電子業": {
        "上游": ["元件/材料"],
        "中游": ["製造/組裝"],
        "下游": ["終端應用"],
        "icon": "⚡",
    },
    "電機機械": {
        "上游": ["鋼材/原料"],
        "中游": ["零組件/馬達"],
        "下游": ["自動化設備/重電"],
        "icon": "⚙️",
    },
    "生技醫療業": {
        "上游": ["原料藥/研發"],
        "中游": ["製藥/醫材製造"],
        "下游": ["醫療服務/通路"],
        "icon": "🧬",
    },
    "化學工業": {
        "上游": ["石化原料"],
        "中游": ["特用化學"],
        "下游": ["應用製品"],
        "icon": "🧪",
    },
    "塑膠工業": {
        "上游": ["石化原料"],
        "中游": ["塑膠加工"],
        "下游": ["塑膠製品"],
        "icon": "🫧",
    },
    "鋼鐵工業": {
        "上游": ["鐵礦/廢鋼"],
        "中游": ["煉鋼/軋鋼"],
        "下游": ["鋼材加工/應用"],
        "icon": "🔩",
    },
    "紡織纖維": {
        "上游": ["石化原料/天然纖維"],
        "中游": ["紡紗/織布"],
        "下游": ["成衣/品牌"],
        "icon": "🧵",
    },
    "食品工業": {
        "上游": ["農產原料"],
        "中游": ["食品加工"],
        "下游": ["通路/零售"],
        "icon": "🍱",
    },
    "汽車工業": {
        "上游": ["鋼材/零件"],
        "中游": ["整車組裝"],
        "下游": ["銷售/售後"],
        "icon": "🚗",
    },
    "航運業": {
        "上游": ["造船/租船"],
        "中游": ["貨櫃/散裝航運"],
        "下游": ["物流/倉儲"],
        "icon": "🚢",
    },
    "金融保險": {
        "上游": ["金控"],
        "中游": ["銀行/證券/保險"],
        "下游": ["金融服務/支付"],
        "icon": "🏦",
    },
    "建材營造": {
        "上游": ["水泥/鋼材"],
        "中游": ["營造工程"],
        "下游": ["不動產/建設"],
        "icon": "🏗️",
    },
    "油電燃氣業": {
        "上游": ["探勘/進口"],
        "中游": ["煉製/發電"],
        "下游": ["配銷/零售"],
        "icon": "⛽",
    },
    "綠能環保": {
        "上游": ["材料/設備"],
        "中游": ["發電/儲能"],
        "下游": ["能源服務"],
        "icon": "🌱",
    },
    "觀光餐旅": {
        "上游": ["食材/用品"],
        "中游": ["飯店/餐飲"],
        "下游": ["旅遊/訂房平台"],
        "icon": "🏨",
    },
    "貿易百貨": {
        "上游": ["供應商/品牌"],
        "中游": ["通路/物流"],
        "下游": ["零售/電商"],
        "icon": "🛒",
    },
    "文化創意業": {
        "上游": ["內容創作"],
        "中游": ["製作/發行"],
        "下游": ["平台/通路"],
        "icon": "🎨",
    },
    "運動休閒": {
        "上游": ["材料/設計"],
        "中游": ["製造"],
        "下游": ["品牌/通路"],
        "icon": "🏃",
    },
}


def fetch_industry_data(force_refresh: bool = False) -> List[Dict]:
    """
    從 FinMind API 取得完整的產業分類 + 個股對應。
    會快取到 .cache/industry_data.json（一天內有效）。
    """
    cache_path = os.path.join(CACHE_DIR, "industry_data.json")

    if not force_refresh and os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        if (datetime.now().timestamp() - mtime) < 86400:  # 24h
            with open(cache_path, "r") as f:
                return json.load(f)

    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInfo",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "token": "",
    }
    r = requests.get(url, params=params, timeout=20)
    data = r.json()

    if data.get("msg") != "success":
        # 嘗試前一天
        yesterday = datetime.now().replace(day=datetime.now().day - 1).strftime("%Y-%m-%d")
        params["date"] = yesterday
        r = requests.get(url, params=params, timeout=20)
        data = r.json()

    stocks = data.get("data", [])
    # 過濾掉 ETF、ETN、Index 等非個股
    stocks = [
        s for s in stocks
        if s.get("type") in ("twse", "tpex", "emerging")
        and s.get("industry_category") not in (
            "ETF", "ETN", "Index", "上櫃ETF", "上櫃指數股票型基金(ETF)",
            "指數投資證券(ETN)", "受益證券", "存託憑證", "所有證券",
            "大盤", "創新板股票", "創新版股票",
        )
    ]

    with open(cache_path, "w") as f:
        json.dump(stocks, f, ensure_ascii=False)

    return stocks


def build_industry_index(stocks: List[Dict]) -> Dict[str, Dict]:
    """建立產業 → 個股索引，含上下游標記。"""
    index = {}
    for s in stocks:
        cat = s["industry_category"]
        if cat not in index:
            chain_info = INDUSTRY_CHAIN.get(cat, {})
            index[cat] = {
                "name": cat,
                "icon": chain_info.get("icon", "📊"),
                "chain": {
                    "上游": chain_info.get("上游", []),
                    "中游": chain_info.get("中游", []),
                    "下游": chain_info.get("下游", []),
                },
                "stocks": [],
                "count": 0,
            }
        index[cat]["stocks"].append({
            "id": s["stock_id"],
            "name": s["stock_name"],
            "type": s["type"],
        })
        index[cat]["count"] = len(index[cat]["stocks"])

    return index


def get_industry_categories() -> List[str]:
    """回傳所有產業類別名稱列表（不含非個股分類）。"""
    stocks = fetch_industry_data()
    index = build_industry_index(stocks)
    return sorted(index.keys())