"""
股價與漲跌幅模組 — 透過 yfinance + twstock 取得歷史/即時股價。
"""

import yfinance as yf
import twstock
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
import json

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# twstock → yfinance 代碼對應 (上櫃二市場用 .TWO)
def _to_yahoo_code(stock_id: str, market_type: str = "twse") -> str:
    """將台灣股票代碼轉成 Yahoo Finance 格式。"""
    if market_type == "tpex":
        return f"{stock_id}.TWO"
    return f"{stock_id}.TW"


def get_stock_price(stock_id: str, market_type: str = "twse") -> Optional[Dict]:
    """
    取得個股最新價格與基本資訊（twstock + yfinance 雙來源）。
    回傳: {price, change, change_pct, high, low, volume, name, date}
    """
    result = {"id": stock_id, "market_type": market_type}

    # twstock (即時)
    try:
        stock = twstock.Stock(stock_id)
        if stock.price:
            result["price"] = stock.price[-1]
            result["date"] = stock.date[-1].strftime("%Y-%m-%d") if stock.date else ""
            if len(stock.price) >= 2:
                result["change"] = stock.price[-1] - stock.price[-2]
                result["change_pct"] = round(
                    (stock.price[-1] - stock.price[-2]) / stock.price[-2] * 100, 2
                )
            result["high"] = stock.high[-1] if stock.high else None
            result["low"] = stock.low[-1] if stock.low else None
            result["volume"] = stock.capacity[-1] if stock.capacity else None
    except Exception:
        pass

    # yfinance (名稱補強)
    try:
        ycode = _to_yahoo_code(stock_id, market_type)
        t = yf.Ticker(ycode)
        info = t.info
        if "name" not in result or not result.get("name"):
            result["name"] = info.get("shortName") or info.get("longName") or stock_id
    except Exception:
        pass

    return result if "price" in result else None


def get_historical_returns(stock_id: str, market_type: str = "twse") -> Dict[str, Optional[float]]:
    """
    計算多區間漲跌幅：當日 / 前日 / 近五日 / 近十日 / 1週 / 1月 / 3月 / 6月 / 1年。
    回傳: {"today": pct, "prev": pct, "5d": pct, "10d": pct, "1w": pct, "1m": pct, "3m": pct, "6m": pct, "1y": pct}
    """
    cache_path = os.path.join(CACHE_DIR, f"hist_{stock_id}.json")

    # 快取 1 小時（短區間數據更即時）
    if os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        if (datetime.now().timestamp() - mtime) < 3600:
            with open(cache_path) as f:
                return json.load(f)

    try:
        ycode = _to_yahoo_code(stock_id, market_type)
        t = yf.Ticker(ycode)
        hist = t.history(period="1y")

        if len(hist) < 2:
            fallback = {"today": None, "prev": None, "5d": None, "10d": None,
                        "1w": None, "1m": None, "3m": None, "6m": None, "1y": None}
            return fallback

        close = hist["Close"]
        now = close.iloc[-1]

        # 當日漲跌 (最新 vs 前一日收盤)
        prev_close = close.iloc[-2] if len(close) >= 2 else now
        today_pct = round((now - prev_close) / prev_close * 100, 2) if prev_close != 0 else 0

        # 前日漲跌 (前一日 vs 前二日)
        prev_pct = None
        if len(close) >= 3:
            p2 = close.iloc[-2]
            p3 = close.iloc[-3]
            prev_pct = round((p2 - p3) / p3 * 100, 2) if p3 != 0 else 0

        # 固定天數
        periods = {"5d": 5, "10d": 10, "1w": 5, "1m": 22, "3m": 66, "6m": 132, "1y": 252}
        returns = {"today": today_pct, "prev": prev_pct}
        for key, days in periods.items():
            if len(close) >= days:
                returns[key] = round((now - close.iloc[-days]) / close.iloc[-days] * 100, 2)
            else:
                returns[key] = None

        with open(cache_path, "w") as f:
            json.dump(returns, f)

        return returns
    except Exception:
        return {"today": None, "prev": None, "5d": None, "10d": None,
                "1w": None, "1m": None, "3m": None, "6m": None, "1y": None}


def get_custom_range_return(stock_id: str, market_type: str, start_date: str, end_date: str) -> Optional[float]:
    """
    計算自訂日期範圍的漲跌幅。
    start_date / end_date 格式: "YYYY-MM-DD"
    回傳: 漲跌幅百分比，或 None（資料不足）
    """
    try:
        ycode = _to_yahoo_code(stock_id, market_type)
        t = yf.Ticker(ycode)
        # 拉取足夠範圍的歷史資料
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        hist = t.history(start=start_date, end=end_date)

        if len(hist) < 2:
            return None

        first_close = hist["Close"].iloc[0]
        last_close = hist["Close"].iloc[-1]

        if first_close == 0:
            return None
        return round((last_close - first_close) / first_close * 100, 2)
    except Exception:
        return None


def get_volume_trend(stock_id: str, market_type: str = "twse") -> Optional[float]:
    """
    計算成交量趨勢 = (近5日均量 - 近20日均量) / 近20日均量 × 100%。
    正值 = 放量升溫，負值 = 縮量降溫。
    """
    try:
        ycode = _to_yahoo_code(stock_id, market_type)
        t = yf.Ticker(ycode)
        hist = t.history(period="1mo")
        if len(hist) < 22:
            return None
        vol5 = hist["Volume"].iloc[-5:].mean()
        vol20 = hist["Volume"].iloc[-22:].mean()
        if vol20 == 0:
            return 0
        return round((vol5 - vol20) / vol20 * 100, 2)
    except Exception:
        return None


def get_industry_returns(
    stock_ids: List[str],
    market_types: List[str],
    max_stocks: int = 15,
    custom_start: str = None,
    custom_end: str = None,
) -> Dict[str, Optional[float]]:
    """
    計算產業的加權平均漲跌幅（取前 N 檔代表性個股）。
    支援固定區間 + 自訂日期範圍。
    """
    sample = list(zip(stock_ids, market_types))[:max_stocks]

    return_keys = ["today", "prev", "5d", "10d", "1w", "1m", "3m", "6m", "1y"]
    all_returns = {k: [] for k in return_keys}

    for sid, mtype in sample:
        # 固定區間
        ret = get_historical_returns(sid, mtype)
        for key in return_keys:
            if ret.get(key) is not None:
                all_returns[key].append(ret[key])

    avg = {}
    for key, vals in all_returns.items():
        avg[key] = round(sum(vals) / len(vals), 2) if vals else None

    # 自訂日期範圍（獨立計算）
    if custom_start and custom_end:
        custom_vals = []
        for sid, mtype in sample:
            r = get_custom_range_return(sid, mtype, custom_start, custom_end)
            if r is not None:
                custom_vals.append(r)
        avg["custom"] = round(sum(custom_vals) / len(custom_vals), 2) if custom_vals else None
    else:
        avg["custom"] = None

    return avg


def get_industry_heat(stock_ids: List[str], market_types: List[str], max_stocks: int = 30) -> float:
    """
    計算產業熱度 = 取樣個股成交量趨勢的中位數。
    > 0 = 升溫 🔥，< 0 = 降溫 ❄️
    """
    sample = list(zip(stock_ids, market_types))[:max_stocks]
    trends = []
    for sid, mtype in sample:
        t = get_volume_trend(sid, mtype)
        if t is not None:
            trends.append(t)

    if not trends:
        return 0
    trends.sort()
    n = len(trends)
    if n % 2 == 1:
        return trends[n // 2]
    else:
        return round((trends[n // 2 - 1] + trends[n // 2]) / 2, 2)