"""
新聞模組 — 透過 Google News RSS 取得個股/產業相關新聞。
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict
import re
import html


def clean_html(text: str) -> str:
    """移除 HTML 標籤並解碼 HTML entities。"""
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def get_stock_news(stock_name: str, stock_id: str, max_items: int = 15) -> List[Dict]:
    """
    從 Google News RSS 取得個股相關新聞。
    回傳: [{title, source, url, published, snippet}, ...]
    """
    query = f"{stock_name} {stock_id} 股票"
    url = (
        f"https://news.google.com/rss/search?q={requests.utils.quote(query)}"
        f"&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )

    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []

        root = ET.fromstring(r.text)
        items = root.findall(".//item")
        news = []

        for item in items[:max_items]:
            title_el = item.find("title")
            source_el = item.find("source")
            pubdate_el = item.find("pubDate")
            link_el = item.find("link")
            desc_el = item.find("description")

            title = clean_html(title_el.text) if title_el is not None else ""
            source = source_el.text if source_el is not None else ""
            published = pubdate_el.text if pubdate_el is not None else ""
            url_link = link_el.text if link_el is not None else ""
            snippet = clean_html(desc_el.text)[:150] if desc_el is not None else ""

            # 解析日期
            try:
                dt = datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %Z")
                published_fmt = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                published_fmt = published

            news.append({
                "title": title,
                "source": source,
                "url": url_link,
                "published": published_fmt,
                "snippet": snippet,
            })

        return news

    except Exception:
        return []


def get_industry_news(
    industry_name: str,
    sample_stocks: List[Dict],
    max_per_stock: int = 3,
) -> List[Dict]:
    """
    取得產業相關新聞：從代表性個股的新聞中取樣。
    """
    all_news = []
    seen_titles = set()

    for stock in sample_stocks[:5]:
        news = get_stock_news(stock["name"], stock["id"], max_items=max_per_stock)
        for n in news:
            if n["title"] not in seen_titles:
                seen_titles.add(n["title"])
                n["related_stock"] = f'{stock["id"]} {stock["name"]}'
                all_news.append(n)

        if len(all_news) >= 15:
            break

    return all_news[:15]