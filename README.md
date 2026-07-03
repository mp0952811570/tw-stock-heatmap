# 台灣股票產業熱度儀表板 🔥

台灣股市產業分析儀表板，提供：
- 🔥 **產業熱度排行**：依成交量趨勢排序
- 🏭 **產業分類瀏覽**：上中下游結構 + 個股下鑽
- 📰 **產業新聞**：Google News RSS 即時新聞
- 📈 **多區間漲跌幅**：1週 / 1月 / 3月 / 6月 / 1年

## 資料來源
- **FinMind API** — 台灣股市產業分類 (57 個類別 / 3500+ 檔個股)
- **Yahoo Finance (yfinance)** — 歷史股價與成交量
- **twstock** — 即時股價行情
- **Google News RSS** — 個股/產業相關新聞

## 安裝與執行

```bash
# 1. Clone 專案
git clone https://github.com/YOUR_USERNAME/tw-stock-heatmap.git
cd tw-stock-heatmap

# 2. 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 啟動儀表板
streamlit run main.py
```

## 部署到 Streamlit Cloud (免費)

1. 將此專案 push 到 GitHub **public** repository
2. 到 [share.streamlit.io](https://share.streamlit.io) 用 GitHub 帳號登入
3. 點擊「New app」→ 選擇 repo、branch (main)、主檔案 (main.py)
4. 點擊「Deploy」— 完成！

應用程式網址將是：`https://YOUR_USERNAME-tw-stock-heatmap.streamlit.app`

## 專案結構

```
tw-stock-heatmap/
├── main.py              # Streamlit 儀表板主程式
├── modules/
│   ├── __init__.py
│   ├── industry.py      # 產業分類模組 (FinMind API)
│   ├── stock_data.py    # 股價/漲跌幅/熱度模組 (yfinance + twstock)
│   └── news.py          # 新聞模組 (Google News RSS)
├── requirements.txt     # Python 依賴
├── pyproject.toml       # 專案設定 (uv)
└── README.md            # 本文件
```

## License

MIT