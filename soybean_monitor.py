import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import os
import json
from datetime import datetime, timedelta

# ==========================================
# 1. 設定區域
# ==========================================

COMMODITY_TICKER = "ZS=F"
STOCK_TICKERS = ["1219.TW", "1210.TW", "1215.TW"]

STOCK_NAMES = {
    "1201": "味全",
    "1210": "大成",
    "1215": "卜蜂",
    "1218": "泰山",
    "1219": "福壽",
    "1225": "福懋油"
}

LOOKBACK_DAYS = 180
STRATEGY_WINDOW = 20
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# ==========================================
# 2. 外部資料抓取功能 (新增：營收API)
# ==========================================

def get_twse_revenue_data():
    """
    從證交所 Open Data API 抓取最新月份的全體上市公司營收
    回傳: Dictionary { '1210': 1.23, '1215': -5.4 } (單位: 年增率%)
    """
    print("☁️ 正在連線證交所抓取最新營收資料...")
    url = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            revenue_map = {}
            for row in data:
                # 資料欄位: "公司代號", "營業收入-去年同月增減百分比"
                code = row.get("公司代號")
                yoy = row.get("營業收入-去年同月增減百分比", "0")
                try:
                    revenue_map[code] = float(yoy)
                except:
                    revenue_map[code] = 0.0
            print(f"✅ 成功取得 {len(revenue_map)} 檔股票營收資料")
            return revenue_map
        else:
            print(f"❌ 證交所 API 連線失敗: {res.status_code}")
            return {}
    except Exception as e:
        print(f"❌ 營收抓取錯誤: {e}")
        return {}

def send_discord_notify(msg, img_path=None):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        data = {"content": msg}
        files = {}
        if img_path and os.path.exists(img_path):
            files = {"file": (os.path.basename(img_path), open(img_path, "rb"))}
        
        if files:
            requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)
        else:
            requests.post(DISCORD_WEBHOOK_URL, json=data)
        print("✅ Discord 通知發送成功")
    except Exception as e:
        print(f"❌ Discord 發送錯誤: {e}")
    finally:
        if files: files["file"][1].close()

def get_data():
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS + 10)).strftime('%Y-%m-%d')
    tickers = [COMMODITY_TICKER] + STOCK_TICKERS
    print(f"Downloading price data from {start_date}...")
    data = yf.download(tickers, start=start_date, progress=False)['Close']
    data = data.ffill()
    return data

# ==========================================
# 3. 核心策略邏輯 (三維判斷)
# ==========================================

def get_final_strategy(stock_change, soy_change, gap, revenue_yoy):
    """
    綜合判斷：股價動能 + 原料成本 + 營收基本面
    """
    # 符號與狀態定義
    cost_ok = soy_change < 0
    rev_ok = revenue_yoy > 0
    
    cost_str = "成本↘" if cost_ok else "成本↗"
    rev_str = f"營收{'🔺' if rev_ok else '🔻'}{revenue_yoy:+.1f}%"
    
    signal_icon = ""
    signal_text = ""
    
    # --- 邏輯樹 ---
    
    if cost_ok: # A. 成本端是好的 (黃豆跌)
        if rev_ok:
            # 1. 成本降 + 營收增 = 完美
            signal_icon = "🚀"
            signal_text = "**[雙引擎啟動]** 成本降且營收增，強力看多"
        elif revenue_yoy < -5.0:
            # 2. 成本降 + 營收大減 = 終端出問題 (如豬價崩)
            signal_icon = "⚠️"
            signal_text = "**[基本面衰退]** 雖然成本降，但營收大減，避開"
        else:
            # 3. 成本降 + 營收持平/微跌 = 轉機股
            if gap < -5:
                signal_icon = "👀"
                signal_text = "**[潛在轉機]** 營收平平但成本優勢將發酵"
            else:
                signal_icon = "⚖️"
                signal_text = "**[觀望]** 等待營收回溫"
                
    else: # B. 成本端是壞的 (黃豆漲)
        if rev_ok and stock_change > 0:
            signal_icon = "🔥"
            signal_text = "**[漲價效應]** 營收強勢，可抵銷成本壓力"
        else:
            signal_icon = "☠️"
            signal_text = "**[雙殺風險]** 成本漲且無營收支撐，危險"

    # --- 補充警語 ---
    note = ""
    if gap > 15: note = " (🚫乖離大)"
    elif gap < -10 and cost_ok and revenue_yoy > -3: note = " (✨黃金買點)"

    return {
        "text": f"{signal_icon} {signal_text}{note}",
        "details": f"{cost_str} | {rev_str} | 開口{gap:+.1f}"
    }

def plot_chart(data):
    plt.figure(figsize=(12, 6))
    plt.style.use('bmh') 
    norm_data = (data / data.iloc[0]) * 100
    
    plt.plot(norm_data.index, norm_data[COMMODITY_TICKER], 
             label='Soybean (Cost)', color='red', linewidth=2.5, linestyle='--')
    
    colors = ['blue', 'green', 'orange', 'purple']
    for i, stock in enumerate(STOCK_TICKERS):
        code = stock.split('.')[0]
        name = STOCK_NAMES.get(code, code)
        plt.plot(norm_data.index, norm_data[stock], 
                 label=f"{code} {name}", color=colors[i % len(colors)], linewidth=1.5)

    plt.title(f"Soybean vs. Feed Stocks ({LOOKBACK_DAYS} Days)")
    plt.legend()
    plt.grid(True)
    img_path = "soybean_chart.png"
    plt.savefig(img_path)
    plt.close()
    return img_path

# ==========================================
# 4. 主程式
# ==========================================

def main():
    try:
        # 1. 抓取股價與營收
        df = get_data()
        revenue_data = get_twse_revenue_data() # 取得所有公司營收
        
        if df.empty: return
        img_path = plot_chart(df)
        
        # 2. 計算基礎數據
        current = df.iloc[-1]
        prev = df.iloc[-STRATEGY_WINDOW] if len(df) > STRATEGY_WINDOW else df.iloc[0]
        
        soy_now = current[COMMODITY_TICKER]
        soy_pct = ((soy_now - prev[COMMODITY_TICKER]) / prev[COMMODITY_TICKER]) * 100
        
        # 3. 產生報告
        date_str = df.index[-1].strftime('%Y-%m-%d')
        msg = f"**【黃豆 vs 食品股 全方位監控】**\n📅 `{date_str}`\n"
        msg += f"📉 黃豆成本(近{STRATEGY_WINDOW}日): `{soy_pct:+.2f}%`\n\n"
        
        for ticker in STOCK_TICKERS:
            code = ticker.split('.')[0]
            name = STOCK_NAMES.get(code, "")
            
            # 取得個股數據
            s_pct = ((current[ticker] - prev[ticker]) / prev[ticker]) * 100
            
            # 開口度
            norm_soy = (df[COMMODITY_TICKER] / df[COMMODITY_TICKER].iloc[0]) * 100
            norm_stock = (df[ticker] / df[ticker].iloc[0]) * 100
            gap = norm_stock.iloc[-1] - norm_soy.iloc[-1]
            
            # 取得該股營收 YoY (若抓不到給 0)
            rev_yoy = revenue_data.get(code, 0.0)
            
            # AI 判讀
            analysis = get_final_strategy(s_pct, soy_pct, gap, rev_yoy)
            
            msg += f"> **{code} {name}** (股價 {s_pct:+.1f}%)\n"
            msg += f"> 策略: {analysis['text']}\n"
            msg += f"> (`{analysis['details']}`)\n\n"
            
        msg += "💡 *三維邏輯：成本(黃豆) + 基本面(營收) + 技術面(開口)*"
        
        send_discord_notify(msg, img_path)

    except Exception as e:
        print(f"Main Loop Error: {e}")

if __name__ == "__main__":
    main()
