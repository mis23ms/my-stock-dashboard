# my-stock-dashboard
my-stock-dashboard (Desktop push to GitHub)

台股個人監控 Dashboard — GitHub Pages 靜態網頁版

**Live URL：**
```
https://mis23ms.github.io/my-stock-dashboard/dashboard.html
```

====
README 涵蓋了 11 個部分，下一個 AI 或你自己回來 debug / 優化時，最重要的是：

第五節 — JSON 來源對應表（哪個 tab 讀哪個檔）
第六節 — 路徑設定（update_dashboard.py 改哪裡）
第九節 — 已知限制（讓下個 AI 不用重新踩坑）
第十一節 — 安全性說明（你的要求）
=====

---

## 一、這個 Repo 是什麼

把桌機 4 支 Python 程式每天產出的 JSON，整合成一個可以在手機或電腦瀏覽器看的 Dashboard。

資料 **全部 embed 在 HTML 裡**，不需要伺服器，也不需要額外的 fetch。每天只 push 一個 `dashboard.html` 就夠。

---

## 二、Repo 檔案結構

```
my-stock-dashboard/
├── dashboard.html          ← 主 Dashboard（每日更新）
├── update_dashboard.py     ← 每日更新腳本（在桌機執行）
└── README.md               ← 本文件
```

---

## 三、Dashboard 4 個 Tab 說明

### ① 當沖
- 固定 5 檔（2330 台積電、2317 鴻海、2382 廣達、3231 緯創、2308 台達電）的今日/昨日當沖率卡片
- 分級顏色：綠色 `<20%`、橘色 `20~45%`、紅色 `>45%`
- 全部監控個股排序清單（高→低）
- **對應 JSON：** `台股當沖_個股彙整_YYYYMMDD.json`

### ② MA / 乖離率
- 條件觸發區：哪些股票收盤價低於 5日MA / 10日MA / 30日MA
- 固定 5 檔的 5日/10日/30日/60日 均線一覽表（含乖離率、均線方向）
- 2330 近 20 日 5日乖離率柱狀圖（綠=正乖離、紅=負乖離）
- **對應 JSON：** `goodinfo_stats_history_YYYYMMDD.json`

### ③ 2330 比較圖
- 圖A：2330 vs 0050 近 20 日累積報酬率比較（以起始日為 0 基準）
- 圖B：2330 & TE（左軸，元）vs TX（右軸，點）近 20 日走勢雙Y軸圖
- **對應 JSON：** `goodinfo_stats_history_compareTETX_YYYYMMDD.json`

### ④ TX / TE
- 今日收盤、POC（最大量價位）、加權中心價
- 支撐區前 3 大、壓力區前 3 大（含量）
- 6 大外資 + 元大 券商買賣均價與多空訊號（空的不顯示）
- **對應 JSON：** `TX_broker_levels_YYYYMMDD.json`、`TE_broker_levels_YYYYMMDD.json`

==加上下列了==

① 當沖全清單 — 新增「5日平均」欄

今日當沖率 > 5日平均 → 紅色（比近期高，異常熱）
今日當沖率 < 5日平均 → 綠色（比近期低，相對冷靜）
固定5檔卡片也加了「5日均」顯示

② 圖B 下方 — 5日相對報酬表

每列一天（最新在上），顯示 2330 vs TX 和 2330 vs TE 的當日相對報酬
正值（綠）= 2330 那天比較強，負值（紅）= 期貨那天比較強
最底一列是 5日合計，一眼看出這週誰領漲

---

## 四、每日更新流程

### 桌機端（每個工作日收盤後）

```
step 1. 跑 4 支桌機 Python 程式，產出最新 JSON
step 2. 執行更新腳本：
        python update_dashboard.py
step 3. 腳本自動 git push，手機打開網址即可查看
```

### `update_dashboard.py` 做的事

1. 從各資料夾 glob 找最新的 JSON（按日期排序取最後一個）
2. 讀取並處理資料（當沖率、均線乖離率、比較序列、券商資料）
3. 把資料 embed 進 HTML 模板，產出 `dashboard.html`
4. `git add dashboard.html → git commit → git push`

---

## 五、JSON 來源對應表

| Dashboard 區塊 | JSON 檔案 | 產生的桌機 .py | 資料夾 |
|---|---|---|---|
| ① 當沖 | `台股當沖_個股彙整_YYYYMMDD.json` | `day_trading_auto.py` | `當沖自動報表 - V2\` |
| ② MA/乖離率 | `goodinfo_stats_history_YYYYMMDD.json` | `goodinfo_stats_history_official_v1_5_tablefix_json.py` | `5D10D等數字-台股\` |
| ③ 比較圖 | `goodinfo_stats_history_compareTETX_YYYYMMDD.json` | `goodinfo_stats_history_official_v1_5_tablefix_json.py` | `5D10D等數字-(TXTE0050)\output\` |
| ④ TX/TE | `TX_broker_levels_YYYYMMDD.json` | `app.py` | `TX_broker_levels_analyzer\output\` |
| ④ TX/TE | `TE_broker_levels_YYYYMMDD.json` | `app.py` | `TX_broker_levels_analyzer\output\` |

---

## 六、`update_dashboard.py` 路徑設定

腳本頂端的 `CONFIG` 區塊，改這裡就好：

```python
BASE = Path(r"C:\Users\mis23\OneDrive\桌面")

JSON_DIRS = {
    "daytrade":  BASE / "當沖自動報表 - V2",
    "goodinfo":  BASE / "5D10D等數字-台股",
    "compareTX": BASE / "5D10D等數字-(TXTE0050)" / "output",
    "broker":    BASE / "TX_broker_levels_analyzer" / "output",
}

GITHUB_REPO_DIR = BASE / "my-stock-dashboard"   # 本 repo 的本機路徑

GIT_AUTO_PUSH = True    # 改成 False 只產 HTML 不 push
```

---

## 七、固定監控股票

| 代號 | 名稱 | 出現位置 |
|---|---|---|
| 2330 | 台積電 | 當沖卡片、MA表、比較圖 |
| 2317 | 鴻海 | 當沖卡片、MA表 |
| 2382 | 廣達 | 當沖卡片、MA表 |
| 3231 | 緯創 | 當沖卡片、MA表 |
| 2308 | 台達電 | 當沖卡片、MA表 |
| 0050 | 元大台灣50 | 比較圖A |

當沖頁的全部清單（非固定5檔）來自 `day_trading_auto.py` 輸出，目前約 25~29 檔。

---

## 八、色彩規格

| 用途 | 色碼 |
|---|---|
| 背景 | `#F8F7F2`（暖米色）|
| 主色 / 標題 | `#004AAD`（海軍藍）|
| 上漲 / 正值 | `#006B3C`（深綠）|
| 下跌 / 負值 | `#C8102E`（深紅）|
| 警示（中間段）| `#CC5500`（橘）|
| 字體 | Noto Sans TC（中文）、JetBrains Mono（數字）|
| 最小字級 | 12px |

---

## 九、已知限制 / 未來可優化方向

| 項目 | 說明 |
|---|---|
| 乖離率趨勢圖 | 目前 2317/2382/3231/2308 的 goodinfo JSON 只有當天一個資料點，需累積多天才能畫出完整趨勢。2330 用 compareTETX 的歷史序列補足。 |
| 當沖全清單 | 固定監控 25 檔，若 `day_trading_auto.py` 清單有變動，Dashboard 會自動跟著更新 |
| TX/TE 收盤 | 從 compareTETX JSON 的最後一個資料點取得，若 compareTETX 未在當日更新則會顯示舊日期的數字 |
| 手動排程 | 目前需手動執行 `update_dashboard.py`，未來可設 Windows 工作排程器自動化 |

---

## 十、Git 操作備忘

```bash
# 第一次設定（只做一次）
git config --global user.email "mis23ms@gmail.com"
git config --global user.name "mis23ms"

# 每天更新（update_dashboard.py 會自動做這些）
git add dashboard.html
git commit -m "auto: update dashboard YYYY-MM-DD"
git push

# 查目前狀態
git status

# 查最近 push 紀錄
git log --oneline -5
```

---

## 十一、安全性說明

`update_dashboard.py` 的設計原則：

- ✅ 不刪除任何本機檔案
- ✅ 不上傳到 Google Drive（只 push GitHub）
- ✅ 不連接外部 API（JSON 資料由桌機 .py 產生，腳本只讀本機）
- ✅ subprocess 使用 list 模式，`shell=False`，無 shell injection 風險
- ✅ HTML 內嵌資料，不在瀏覽器端 fetch 任何外部資料
- ✅ 外部資源只有 Google Fonts 和 Chart.js CDN（cdnjs.cloudflare.com）

---

*最後更新：2026-04-03　by mis23ms + Claude*
