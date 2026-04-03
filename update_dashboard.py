"""
update_dashboard.py  —  每日更新台股監控 Dashboard
=======================================================
功能：
  1. 從桌機各資料夾找最新的 JSON 檔
  2. 處理資料、嵌入 HTML
  3. 存到 GitHub repo 資料夾
  4. git commit + push（可開關）

用法：
  python update_dashboard.py

安全性：
  - 不刪除任何檔案
  - 不上傳到 Google Drive（只 push 到你的 GitHub repo）
  - 不執行任何 shell 指令（git 用 subprocess list 模式，不用 shell=True）
  - 不連接任何外部站（只打 GitHub）

作者：Claude + mis23  |  2026-04
"""

import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from glob import glob

# ═══════════════════════════════════════════════════════════════════
#  ① CONFIG  —  改這裡就好，不用動其他地方
# ═══════════════════════════════════════════════════════════════════

BASE = Path(r"C:\Users\mis23\OneDrive\桌面")

# 各 JSON 的資料夾（保持跟你原本 .py 輸出的路徑一致）
JSON_DIRS = {
    "daytrade":  BASE / "當沖自動報表 - V2",
    "goodinfo":  BASE / "5D10D等數字-台股",
    "compareTX": BASE / "5D10D等數字-(TXTE0050)" / "output",
    "broker":    BASE / "TX_broker_levels_analyzer" / "output",
}

# 各 JSON 的檔名 glob pattern（* 代表日期部分，例如 20260402）
JSON_PATTERNS = {
    "daytrade":  "台股當沖_個股彙整_*.json",
    "goodinfo":  "goodinfo_stats_history_[0-9]*.json",   # 排除 compareTETX
    "compareTX": "goodinfo_stats_history_compareTETX_*.json",
    "TX":        "TX_broker_levels_*.json",
    "TE":        "TE_broker_levels_*.json",
}

# GitHub repo 本機路徑（dashboard.html 要放在這裡）
GITHUB_REPO_DIR = BASE / "my-stock-dashboard"   # ← 改成你的 repo 資料夾

# 輸出的 HTML 檔名
OUTPUT_HTML = GITHUB_REPO_DIR / "dashboard.html"

# Git 設定
GIT_AUTO_PUSH = True          # 改成 False 就只產生 HTML，不 push
GIT_COMMIT_PREFIX = "auto: update dashboard"

# 固定 5 檔股票
FIXED_5 = ["2330", "2317", "2382", "3231", "2308"]
NAMES_5  = {"2330": "台積電", "2317": "鴻海", "2382": "廣達", "3231": "緯創", "2308": "台達電"}

# ═══════════════════════════════════════════════════════════════════
#  ② 工具函式
# ═══════════════════════════════════════════════════════════════════

def find_latest(folder: Path, pattern: str) -> Path | None:
    """在 folder 裡找符合 pattern 的最新檔案（按檔名排序取最後一個）"""
    matches = sorted(folder.glob(pattern))
    if not matches:
        print(f"  ⚠️  找不到檔案：{folder / pattern}")
        return None
    latest = matches[-1]
    print(f"  ✅ {latest.name}")
    return latest


def load_json(path: Path) -> dict | list | None:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ❌ 讀取失敗 {path.name}：{e}")
        return None


# ═══════════════════════════════════════════════════════════════════
#  ③ 資料處理
# ═══════════════════════════════════════════════════════════════════

def process_daytrade(raw: dict) -> dict:
    history = sorted(raw.get("history", []), key=lambda x: x["date"])
    today   = history[-1] if history else {}
    yest    = history[-2] if len(history) >= 2 else {}

    def get_ratio(day, code):
        for s in day.get("stocks", []):
            if s["code"] == code:
                r = s.get("ratio")
                return round(r * 100, 1) if r is not None else None
        return None

    cards = [
        {"code": c, "name": NAMES_5[c],
         "today": get_ratio(today, c),
         "yesterday": get_ratio(yest, c)}
        for c in FIXED_5
    ]

    all_stocks = sorted(
        [{"code": s["code"], "name": s["name"],
          "ratio": round(s["ratio"] * 100, 1) if s.get("ratio") else 0,
          "found": s.get("found", True)}
         for s in today.get("stocks", []) if s.get("found", True)],
        key=lambda x: x["ratio"], reverse=True
    )

    return {
        "today_date":     today.get("date", ""),
        "yesterday_date": yest.get("date", ""),
        "cards":          cards,
        "all_stocks":     all_stocks,
    }


def process_goodinfo(raw: dict) -> dict:
    rows = raw.get("rows", [])

    # 取每檔 + 每區間的最新一筆
    latest = {}
    for r in rows:
        key = (r["證券代號"], r["區間"])
        if key not in latest or r["抓取日期"] > latest[key]["抓取日期"]:
            latest[key] = r

    # 條件觸發
    all_codes = list({r["證券代號"] for r in rows})
    conditions = {"5日": [], "10日": [], "20日": []}
    interval_map = {"5日": "5日", "10日": "10日", "20日": "30日"}
    for code in all_codes:
        for label, interval in interval_map.items():
            r = latest.get((code, interval))
            if r and r.get("收盤價") and r.get("均線落點(元)"):
                if r["收盤價"] < r["均線落點(元)"]:
                    conditions[label].append({
                        "code": r["證券代號"], "name": r["證券名稱"],
                        "close": r["收盤價"],  "ma":   r["均線落點(元)"],
                        "deviation": r["均線乖離率(%)"],
                    })

    # 固定 5 檔均線
    fixed5_ma = []
    for code in FIXED_5:
        row = {"code": code, "name": NAMES_5[code]}
        for iv in ["5日", "10日", "30日", "60日"]:
            r = latest.get((code, iv))
            if r:
                row[iv] = {
                    "close":     r["收盤價"],
                    "ma":        r["均線落點(元)"],
                    "deviation": r["均線乖離率(%)"],
                    "direction": r["均線方向"],
                }
        fixed5_ma.append(row)

    return {
        "batch_date": raw.get("batch_date", ""),
        "conditions": conditions,
        "fixed5_ma":  fixed5_ma,
    }


def process_compare(raw: dict) -> dict:
    series = raw.get("compare_series", [])
    last20 = series[-20:]

    def normalize(lst, field):
        base = lst[0].get(field) if lst else None
        if not base:
            return [None] * len(lst)
        return [round((x.get(field, 0) / base - 1) * 100, 2) if x.get(field) else None
                for x in lst]

    return {
        "dates":              [x["日期"] for x in last20],
        "c2330":              [x.get("2330收盤") for x in last20],
        "c0050":              [x.get("0050收盤") for x in last20],
        "cTX":                [x.get("TX收盤")   for x in last20],
        "cTE":                [x.get("TE收盤")   for x in last20],
        "ret2330":            normalize(last20, "2330收盤"),
        "ret0050":            normalize(last20, "0050收盤"),
        "retTX":              normalize(last20, "TX收盤"),
        "retTE":              normalize(last20, "TE收盤"),
        "deviation_2330_5d":  [x.get("2330_距5MA(%)") for x in last20],
        "close_2330":         last20[-1].get("2330收盤") if last20 else None,
        "close_0050":         last20[-1].get("0050收盤") if last20 else None,
    }


def process_broker(raw: dict) -> dict:
    summary = raw["daily_summaries"][0]

    brokers = []
    for b in summary.get("broker_summary", []):
        if b["buy_presence_count"] == 0 and b["sell_presence_count"] == 0:
            continue
        buy_avg  = b.get("buy_weighted_avg_price_proxy")
        sell_avg = b.get("sell_weighted_avg_price_proxy")
        if isinstance(buy_avg,  float) and math.isnan(buy_avg):  buy_avg  = None
        if isinstance(sell_avg, float) and math.isnan(sell_avg): sell_avg = None
        signal = "neutral"
        if buy_avg and sell_avg:
            signal = "bullish" if buy_avg > sell_avg else "bearish"
        brokers.append({
            "canonical_broker":             b["canonical_broker"],
            "buy_weighted_avg_price_proxy":  round(buy_avg,  0) if buy_avg  else None,
            "sell_weighted_avg_price_proxy": round(sell_avg, 0) if sell_avg else None,
            "signal": signal,
        })

    return {
        "contract_code":  raw.get("contract_code", ""),
        "contract_name":  raw.get("contract_name", ""),
        "trade_date":     summary.get("trade_date", ""),
        "poc":            summary.get("point_of_control_price"),
        "weighted_center": round(summary.get("weighted_center_price", 0), 0),
        "supports":       summary.get("supports",    []),
        "resistances":    summary.get("resistances", []),
        "brokers":        brokers,
        "close_today":    None,   # 補在 main() 裡
    }


# ═══════════════════════════════════════════════════════════════════
#  ④ HTML 模板
# ═══════════════════════════════════════════════════════════════════

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股監控 Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--bg:#F8F7F2;--navy:#004AAD;--navy-light:#1a5fc4;--text:#1a1a1a;--text-mid:#444;--text-light:#777;--border:#d4d0c4;--card-bg:#fff;--red:#C8102E;--red-bg:#fff0f2;--green:#006B3C;--green-bg:#f0fff6;--orange:#CC5500;--orange-bg:#fff5ee;--yellow-bg:#fffae8;--shadow:0 2px 8px rgba(0,74,173,.08)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Noto Sans TC',sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;min-height:100vh}
.header{background:var(--navy);color:#fff;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(0,0,0,.2)}
.header h1{font-size:18px;font-weight:700;letter-spacing:.05em}
.header .meta{font-size:12px;opacity:.75}
.tabs{display:flex;background:#fff;border-bottom:2px solid var(--border);overflow-x:auto;position:sticky;top:52px;z-index:90;box-shadow:0 2px 6px rgba(0,0,0,.06)}
.tab-btn{padding:14px 22px;background:none;border:none;border-bottom:3px solid transparent;font-family:inherit;font-size:14px;font-weight:500;color:var(--text-mid);cursor:pointer;white-space:nowrap;transition:all .2s}
.tab-btn:hover{color:var(--navy);background:rgba(0,74,173,.04)}
.tab-btn.active{color:var(--navy);border-bottom-color:var(--navy);font-weight:700}
.content{padding:20px;max-width:1100px;margin:0 auto}
.tab-panel{display:none}.tab-panel.active{display:block}
.section-title{font-size:16px;font-weight:700;color:var(--navy);border-left:4px solid var(--navy);padding-left:10px;margin:24px 0 14px}
.section-title:first-child{margin-top:4px}
.cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:24px}
.dt-card{background:var(--card-bg);border-radius:10px;padding:14px 16px;box-shadow:var(--shadow);border:1px solid var(--border);position:relative;overflow:hidden}
.dt-card::before{content:'';position:absolute;top:0;left:0;right:0;height:4px}
.dt-card.low::before{background:var(--green)}.dt-card.mid::before{background:var(--orange)}.dt-card.high::before{background:var(--red)}
.dt-card .stock-code{font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--text-mid);margin-bottom:2px}
.dt-card .stock-name{font-size:14px;font-weight:700;color:var(--text);margin-bottom:10px}
.dt-card .ratio-today{font-size:26px;font-weight:700;font-family:'JetBrains Mono',monospace}
.dt-card.low .ratio-today{color:var(--green)}.dt-card.mid .ratio-today{color:var(--orange)}.dt-card.high .ratio-today{color:var(--red)}
.dt-card .ratio-label{font-size:11px;color:var(--text-light);margin-top:2px}
.dt-card .ratio-yesterday{margin-top:8px;padding-top:8px;border-top:1px dashed var(--border);font-size:13px;color:var(--text-mid)}
.dt-card .ratio-yesterday span{font-family:'JetBrains Mono',monospace;font-weight:600}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;font-family:'JetBrains Mono',monospace}
.badge.low{background:var(--green-bg);color:var(--green)}.badge.mid{background:var(--orange-bg);color:var(--orange)}.badge.high{background:var(--red-bg);color:var(--red)}
.data-table{width:100%;border-collapse:collapse;background:var(--card-bg);border-radius:10px;overflow:hidden;box-shadow:var(--shadow);margin-bottom:24px;font-size:13px}
.data-table th{background:var(--navy);color:#fff;padding:10px 12px;text-align:left;font-weight:600;font-size:13px}
.data-table td{padding:9px 12px;border-bottom:1px solid var(--border)}
.data-table tr:last-child td{border-bottom:none}
.data-table tr:hover td{background:rgba(0,74,173,.03)}
.mono{font-family:'JetBrains Mono',monospace}.red{color:var(--red)}.green{color:var(--green)}.orange{color:var(--orange)}
.conditions-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-bottom:24px}
.condition-box{background:var(--card-bg);border-radius:10px;border:1px solid var(--border);box-shadow:var(--shadow);overflow:hidden}
.condition-box-header{background:var(--navy);color:#fff;padding:10px 14px;font-size:14px;font-weight:700;display:flex;align-items:center;justify-content:space-between}
.condition-box-header .count{background:rgba(255,255,255,.2);border-radius:20px;padding:2px 10px;font-size:13px}
.condition-box-body{padding:12px}
.condition-chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{background:var(--yellow-bg);border:1px solid #e8d98a;border-radius:6px;padding:4px 10px;font-size:13px;display:flex;align-items:center;gap:4px}
.chip .chip-code{font-family:'JetBrains Mono',monospace;font-weight:600;font-size:12px;color:var(--navy)}
.chip .chip-dev{font-size:12px}.chip .chip-dev.neg{color:var(--red)}
.chart-container{background:var(--card-bg);border-radius:10px;padding:18px;box-shadow:var(--shadow);border:1px solid var(--border);margin-bottom:24px}
.chart-title{font-size:13px;color:var(--text-mid);margin-bottom:14px}
.chart-wrap{position:relative;height:260px}
.signal-pill{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700}
.signal-pill.bullish{background:var(--green-bg);color:var(--green)}.signal-pill.bearish{background:var(--red-bg);color:var(--red)}.signal-pill.neutral{background:#f0f0f0;color:var(--text-mid)}
.poc-row{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.poc-card{flex:1;min-width:140px;background:var(--navy);color:#fff;border-radius:10px;padding:14px 18px;box-shadow:var(--shadow);text-align:center}
.poc-card.close-card{background:#1a1a2e}.poc-card.center-card{background:var(--navy-light)}
.poc-card .poc-label{font-size:12px;opacity:.75;margin-bottom:4px}
.poc-card .poc-value{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700}
.poc-card .poc-sub{font-size:11px;opacity:.7;margin-top:4px}
.price-levels-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:24px}
.price-box{background:var(--card-bg);border-radius:10px;padding:14px;box-shadow:var(--shadow);border:1px solid var(--border)}
.price-box-title{font-size:13px;font-weight:700;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}.dot.red{background:var(--red)}.dot.green{background:var(--green)}
.price-row{display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px dashed var(--border);font-size:13px}
.price-row:last-child{border-bottom:none}
.price-val{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:15px}
.price-val.red{color:var(--red)}.price-val.green{color:var(--green)}
.price-vol{font-size:12px;color:var(--text-light)}
@media(max-width:600px){.content{padding:14px}.cards-grid{grid-template-columns:1fr 1fr}.price-levels-grid{grid-template-columns:1fr}.poc-row{flex-direction:column}.tab-btn{padding:12px 14px;font-size:13px}}
.all-stocks-table td{padding:7px 10px;font-size:13px}.all-stocks-table th{padding:9px 10px}
</style>
</head>
<body>
<div class="header">
  <h1>📊 台股監控 Dashboard</h1>
  <div class="meta" id="header-date">載入中...</div>
</div>
<div class="tabs">
  <button class="tab-btn active" onclick="switchTab('dt',this)">① 當沖</button>
  <button class="tab-btn" onclick="switchTab('ma',this)">② MA / 乖離率</button>
  <button class="tab-btn" onclick="switchTab('compare',this)">③ 2330 比較圖</button>
  <button class="tab-btn" onclick="switchTab('txte',this)">④ TX / TE</button>
</div>
<div class="content">
<div id="tab-dt" class="tab-panel active">
  <div class="section-title">固定 5 檔 當沖率</div>
  <div class="cards-grid" id="dt-cards"></div>
  <div class="section-title">今日全部個股當沖率</div>
  <table class="data-table all-stocks-table">
    <thead><tr><th>代號</th><th>名稱</th><th>當沖率</th><th>分級</th></tr></thead>
    <tbody id="dt-all-body"></tbody>
  </table>
</div>
<div id="tab-ma" class="tab-panel">
  <div class="section-title">收盤價低於均線 — 條件觸發</div>
  <div class="conditions-grid" id="ma-conditions"></div>
  <div class="section-title">固定 5 檔 均線一覽</div>
  <div style="overflow-x:auto">
  <table class="data-table">
    <thead><tr><th>股票</th><th>收盤</th><th>5日MA</th><th>5日乖離</th><th>10日MA</th><th>10日乖離</th><th>30日MA</th><th>30日乖離</th><th>60日MA</th><th>60日乖離</th></tr></thead>
    <tbody id="ma-table-body"></tbody>
  </table>
  </div>
  <div class="section-title">2330 台積電 — 5日乖離率趨勢</div>
  <div class="chart-container">
    <div class="chart-wrap"><canvas id="chart-deviation"></canvas></div>
  </div>
</div>
<div id="tab-compare" class="tab-panel">
  <div class="section-title">圖A：2330 vs 0050 — 近 20 日累積報酬 (%)</div>
  <div class="chart-container">
    <div class="chart-wrap" style="height:280px"><canvas id="chart-a"></canvas></div>
  </div>
  <div class="section-title">圖B：2330 & TE vs TX — 近 20 日（雙 Y 軸）</div>
  <div class="chart-container">
    <div class="chart-title">左軸：2330 / TE（元）　右軸：TX（點）</div>
    <div class="chart-wrap" style="height:300px"><canvas id="chart-b"></canvas></div>
  </div>
</div>
<div id="tab-txte" class="tab-panel">
  <div class="section-title">TX 臺股期貨</div>
  <div class="poc-row" id="tx-poc"></div>
  <div class="price-levels-grid" id="tx-levels"></div>
  <table class="data-table">
    <thead><tr><th>券商</th><th>買方均價</th><th>賣方均價</th><th>多空訊號</th></tr></thead>
    <tbody id="tx-broker-body"></tbody>
  </table>
  <div class="section-title">TE 電子期貨</div>
  <div class="poc-row" id="te-poc"></div>
  <div class="price-levels-grid" id="te-levels"></div>
  <table class="data-table">
    <thead><tr><th>券商</th><th>買方均價</th><th>賣方均價</th><th>多空訊號</th></tr></thead>
    <tbody id="te-broker-body"></tbody>
  </table>
</div>
</div>
<script>
const DATA=__DATA_PLACEHOLDER__;
function switchTab(id,btn){
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');btn.classList.add('active');
  if(id==='compare'&&!window._cR){renderCompare();window._cR=true;}
  if(id==='ma'&&!window._mR){renderMAChart();window._mR=true;}
}
function tier(r){if(r===null||r===undefined)return'mid';if(r<20)return'low';if(r<=45)return'mid';return'high';}
function tierLabel(r){if(r===null)return'—';if(r<20)return'<20%';if(r<=45)return'20~45%';return'>45%';}
function renderDT(){
  const d=DATA.dt;
  document.getElementById('header-date').textContent=`資料日期：${d.today_date}`;
  const grid=document.getElementById('dt-cards');
  d.cards.forEach(c=>{
    const t=tier(c.today);const div=document.createElement('div');div.className=`dt-card ${t}`;
    div.innerHTML=`<div class="stock-code">${c.code}</div><div class="stock-name">${c.name}</div>
      <div class="ratio-today mono">${c.today!==null?c.today+'%':'—'}</div><div class="ratio-label">今日當沖率</div>
      <div class="ratio-yesterday">昨日：<span>${c.yesterday!==null?c.yesterday+'%':'—'}</span></div>`;
    grid.appendChild(div);
  });
  const tbody=document.getElementById('dt-all-body');
  d.all_stocks.forEach(s=>{
    const t=tier(s.ratio);const tr=document.createElement('tr');
    tr.innerHTML=`<td class="mono" style="color:var(--navy);font-weight:600">${s.code}</td><td>${s.name}</td>
      <td class="mono" style="font-weight:700">${s.ratio}%</td><td><span class="badge ${t}">${tierLabel(s.ratio)}</span></td>`;
    tbody.appendChild(tr);
  });
}
function renderMA(){
  const d=DATA.ma;
  const labels={'5日':'收盤 < 5日MA','10日':'收盤 < 10日MA','20日':'收盤 < 30日MA'};
  const container=document.getElementById('ma-conditions');
  ['5日','10日','20日'].forEach(k=>{
    const items=d.conditions[k]||[];const box=document.createElement('div');box.className='condition-box';
    const chips=items.map(item=>{
      const dc=item.deviation<0?'neg':'';
      return`<div class="chip"><span class="chip-code">${item.code}</span>${item.name}<span class="chip-dev ${dc}">${item.deviation}%</span></div>`;
    }).join('');
    box.innerHTML=`<div class="condition-box-header">${labels[k]}<span class="count">${items.length}檔</span></div>
      <div class="condition-box-body"><div class="condition-chips">${chips||'<span style="color:var(--text-light);font-size:13px">無觸發</span>'}</div></div>`;
    container.appendChild(box);
  });
  const tbody=document.getElementById('ma-table-body');
  d.fixed5_ma.forEach(row=>{
    const r5=row['5日']||{},r10=row['10日']||{},r30=row['30日']||{},r60=row['60日']||{};
    function devCell(o){if(!o||o.deviation===undefined)return'<td>—</td>';const cl=o.deviation<0?'red':'green';return`<td class="mono ${cl}" style="font-weight:600">${o.deviation>0?'+':''}${o.deviation}% ${o.direction||''}</td>`;}
    function maCell(o){if(!o||!o.ma)return'<td>—</td>';return`<td class="mono">${o.ma}</td>`;}
    const close=r5.close||r10.close||'—';const ba=r5.deviation<0||r10.deviation<0||r30.deviation<0;
    const tr=document.createElement('tr');
    tr.innerHTML=`<td><span style="font-weight:700;color:var(--navy)">${row.code}</span> ${row.name}</td>
      <td class="mono" style="font-weight:700${ba?';color:var(--red)':''}">${close}</td>
      ${maCell(r5)}${devCell(r5)}${maCell(r10)}${devCell(r10)}${maCell(r30)}${devCell(r30)}${maCell(r60)}${devCell(r60)}`;
    tbody.appendChild(tr);
  });
}
function renderMAChart(){
  const c=DATA.compare;const dates=c.dates.map(d=>d.slice(5));const devs=c.deviation_2330_5d;
  const ctx=document.getElementById('chart-deviation').getContext('2d');
  new Chart(ctx,{type:'bar',data:{labels:dates,datasets:[{label:'5日乖離率(%)',data:devs,
    backgroundColor:devs.map(v=>v===null?'transparent':v>=0?'rgba(0,107,60,.75)':'rgba(200,16,46,.75)'),borderRadius:3}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},
      tooltip:{callbacks:{label:c=>c.parsed.y!==null?c.parsed.y+'%':'無資料'}}},
      scales:{x:{ticks:{font:{size:11},maxRotation:45}},y:{grid:{color:'rgba(0,0,0,.05)'},ticks:{font:{size:11},callback:v=>v+'%'}}}}});
}
function renderCompare(){
  const c=DATA.compare;const dates=c.dates.map(d=>d.slice(5));
  const ctxA=document.getElementById('chart-a').getContext('2d');
  new Chart(ctxA,{type:'line',data:{labels:dates,datasets:[
    {label:'2330 台積電',data:c.ret2330,borderColor:'#004AAD',backgroundColor:'rgba(0,74,173,.08)',fill:true,tension:0.3,pointRadius:3,borderWidth:2},
    {label:'0050 元大台灣50',data:c.ret0050,borderColor:'#CC5500',backgroundColor:'transparent',tension:0.3,pointRadius:3,borderWidth:2,borderDash:[5,3]}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'top',labels:{font:{size:13}}},
      tooltip:{callbacks:{label:c=>c.dataset.label+': '+(c.parsed.y!==null?c.parsed.y.toFixed(2)+'%':'—')}}},
      scales:{x:{ticks:{font:{size:11},maxRotation:45}},y:{grid:{color:'rgba(0,0,0,.05)'},ticks:{font:{size:11},callback:v=>v.toFixed(1)+'%'}}}}});
  const ctxB=document.getElementById('chart-b').getContext('2d');
  new Chart(ctxB,{type:'line',data:{labels:dates,datasets:[
    {label:'2330 台積電',data:c.c2330,borderColor:'#004AAD',backgroundColor:'transparent',tension:0.3,pointRadius:3,borderWidth:2,yAxisID:'y'},
    {label:'TE 電子期貨',data:c.cTE,borderColor:'#006B3C',backgroundColor:'transparent',tension:0.3,pointRadius:3,borderWidth:2,borderDash:[5,3],yAxisID:'y'},
    {label:'TX 臺股期貨',data:c.cTX,borderColor:'#C8102E',backgroundColor:'transparent',tension:0.3,pointRadius:3,borderWidth:2,yAxisID:'y1'}]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{position:'top',labels:{font:{size:13}}}},
      scales:{x:{ticks:{font:{size:11},maxRotation:45}},
        y:{type:'linear',position:'left',title:{display:true,text:'2330 / TE（元）',font:{size:12},color:'#004AAD'},ticks:{font:{size:11},color:'#004AAD'},grid:{color:'rgba(0,74,173,.06)'}},
        y1:{type:'linear',position:'right',title:{display:true,text:'TX（點）',font:{size:12},color:'#C8102E'},ticks:{font:{size:11},color:'#C8102E'},grid:{drawOnChartArea:false}}}}});
}
function renderTXTE(){
  [['tx',DATA.tx],['te',DATA.te]].forEach(([prefix,d])=>{
    document.getElementById(`${prefix}-poc`).innerHTML=`
      <div class="poc-card close-card"><div class="poc-label">今日收盤</div>
        <div class="poc-value">${d.close_today!==null&&d.close_today!==undefined?Number(d.close_today).toLocaleString():'—'}</div>
        <div class="poc-sub">${d.contract_name} ${d.trade_date}</div></div>
      <div class="poc-card"><div class="poc-label">最大量價位 (POC)</div>
        <div class="poc-value">${Number(d.poc).toLocaleString()}</div><div class="poc-sub">成交量最集中</div></div>
      <div class="poc-card center-card"><div class="poc-label">加權中心價</div>
        <div class="poc-value">${Number(d.weighted_center).toLocaleString()}</div><div class="poc-sub">全日量加權</div></div>`;
    document.getElementById(`${prefix}-levels`).innerHTML=`
      <div class="price-box"><div class="price-box-title"><span class="dot red"></span> 壓力區（前 3 大）</div>
        ${d.resistances.map((r,i)=>`<div class="price-row"><span><span style="color:var(--text-light);font-size:12px">R${i+1}</span>&nbsp;${r.zone}</span>
          <div style="text-align:right"><div class="price-val red">${Number(r.mid_price).toLocaleString()}</div><div class="price-vol">量 ${Number(r.window_volume).toLocaleString()}</div></div></div>`).join('')}</div>
      <div class="price-box"><div class="price-box-title"><span class="dot green"></span> 支撐區（前 3 大）</div>
        ${d.supports.map((s,i)=>`<div class="price-row"><span><span style="color:var(--text-light);font-size:12px">S${i+1}</span>&nbsp;${s.zone}</span>
          <div style="text-align:right"><div class="price-val green">${Number(s.mid_price).toLocaleString()}</div><div class="price-vol">量 ${Number(s.window_volume).toLocaleString()}</div></div></div>`).join('')}</div>`;
    const tbody=document.getElementById(`${prefix}-broker-body`);tbody.innerHTML='';
    d.brokers.forEach(b=>{
      const sig=b.signal==='bullish'?'偏多 ▲':b.signal==='bearish'?'偏空 ▼':'中性';
      const tr=document.createElement('tr');
      tr.innerHTML=`<td style="font-weight:600">${b.canonical_broker}</td>
        <td class="mono">${b.buy_weighted_avg_price_proxy?Number(b.buy_weighted_avg_price_proxy).toLocaleString():'—'}</td>
        <td class="mono">${b.sell_weighted_avg_price_proxy?Number(b.sell_weighted_avg_price_proxy).toLocaleString():'—'}</td>
        <td><span class="signal-pill ${b.signal}">${sig}</span></td>`;
      tbody.appendChild(tr);
    });
  });
}
renderDT();renderMA();renderTXTE();
</script>
</body>
</html>"""


def build_html(data: dict) -> str:
    data_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_str)


# ═══════════════════════════════════════════════════════════════════
#  ⑤ Git push
# ═══════════════════════════════════════════════════════════════════

def git_push(repo_dir: Path, date_str: str) -> bool:
    """
    安全的 git push：
    - 用 list 模式呼叫 subprocess，不用 shell=True
    - 不刪除任何檔案
    - 只操作指定 repo 資料夾
    """
    commit_msg = f"{GIT_COMMIT_PREFIX} {date_str}"
    commands = [
        ["git", "-C", str(repo_dir), "add", "dashboard.html"],
        ["git", "-C", str(repo_dir), "commit", "-m", commit_msg],
        ["git", "-C", str(repo_dir), "push"],
    ]
    for cmd in commands:
        print(f"  $ {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,     # ← 安全：不用 shell=True
        )
        if result.stdout.strip():
            print(f"    {result.stdout.strip()}")
        if result.returncode != 0:
            if "nothing to commit" in result.stderr or "nothing to commit" in result.stdout:
                print("  ℹ️  Nothing to commit，跳過 push")
                return True
            print(f"  ❌ git 錯誤：{result.stderr.strip()}")
            return False
    return True


# ═══════════════════════════════════════════════════════════════════
#  ⑥ MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("  台股 Dashboard 每日更新腳本")
    print(f"  執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # ── Step 1: 找最新 JSON ──
    print("\n[1] 尋找最新 JSON 檔案...")
    f_dt  = find_latest(JSON_DIRS["daytrade"],  JSON_PATTERNS["daytrade"])
    f_gi  = find_latest(JSON_DIRS["goodinfo"],  JSON_PATTERNS["goodinfo"])
    f_cmp = find_latest(JSON_DIRS["compareTX"], JSON_PATTERNS["compareTX"])
    f_tx  = find_latest(JSON_DIRS["broker"],    JSON_PATTERNS["TX"])
    f_te  = find_latest(JSON_DIRS["broker"],    JSON_PATTERNS["TE"])

    missing = [n for n, f in [("當沖",f_dt),("goodinfo",f_gi),("compareTX",f_cmp),("TX",f_tx),("TE",f_te)] if f is None]
    if missing:
        print(f"\n❌ 找不到必要 JSON：{missing}，中止。")
        sys.exit(1)

    # ── Step 2: 讀取 + 處理 ──
    print("\n[2] 讀取並處理資料...")
    raw_dt  = load_json(f_dt)
    raw_gi  = load_json(f_gi)
    raw_cmp = load_json(f_cmp)
    raw_tx  = load_json(f_tx)
    raw_te  = load_json(f_te)

    if any(x is None for x in [raw_dt, raw_gi, raw_cmp, raw_tx, raw_te]):
        print("❌ 資料讀取失敗，中止。")
        sys.exit(1)

    dt_data      = process_daytrade(raw_dt)
    ma_data      = process_goodinfo(raw_gi)
    compare_data = process_compare(raw_cmp)
    tx_data      = process_broker(raw_tx)
    te_data      = process_broker(raw_te)

    # 補今日收盤到 TX / TE
    tx_data["close_today"] = compare_data.get("cTX", [None])[-1]
    te_data["close_today"] = compare_data.get("cTE", [None])[-1]

    all_data = {
        "dt":      dt_data,
        "ma":      ma_data,
        "compare": compare_data,
        "tx":      tx_data,
        "te":      te_data,
    }

    date_str = dt_data.get("today_date", datetime.now().strftime("%Y-%m-%d"))
    print(f"  資料日期：{date_str}")

    # ── Step 3: 產生 HTML ──
    print("\n[3] 產生 dashboard.html...")
    GITHUB_REPO_DIR.mkdir(parents=True, exist_ok=True)
    html_content = build_html(all_data)
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"  ✅ 已寫入：{OUTPUT_HTML}  ({len(html_content)//1024} KB)")

    # ── Step 4: Git push ──
    if GIT_AUTO_PUSH:
        print("\n[4] Git commit & push...")
        ok = git_push(GITHUB_REPO_DIR, date_str)
        if ok:
            print("  ✅ Push 成功！")
        else:
            print("  ❌ Push 失敗，請手動確認 git 設定。")
    else:
        print("\n[4] GIT_AUTO_PUSH=False，跳過 push。")
        print(f"  → 請手動執行：cd {GITHUB_REPO_DIR} && git add dashboard.html && git commit -m 'update {date_str}' && git push")

    print("\n✅ 完成！")
    print(f"  GitHub Pages URL 大約是：")
    print(f"  https://mis23ms.github.io/my-stock-dashboard/dashboard.html")
    print("=" * 55)


if __name__ == "__main__":
    main()
