import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import os
from datetime import datetime, timedelta

# --- 設定 ---
# 黃豆期貨 (美股代號)
COMMODITY_TICKER = "ZS=F"
# 台股代號 (福壽, 大成, 卜蜂)
STOCK_TICKERS = ["1219.TW", "1210.TW", "1215.TW"]
# 監控天數 (過去半年，適合波段觀察)
LOOKBACK_DAYS = 180

# Discord Webhook URL (從 GitHub Secrets 讀取)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord_notify(msg, img_path=None):
    """發送訊息與圖片到 Discord"""
    if not DISCORD_WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL is not set.")
        return

    try:
        data = {"content": msg}
        files = {}
        
        # 如果有圖片，就附加在請求中
        if img_path and os.path.exists(img_path):
            files = {"file": (os.path.basename(img_path), open(img_path, "rb"))}
        
        if files:
            response = requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)
        else:
            response = requests.post(DISCORD_WEBHOOK_URL, json=data)

        if response.status_code in [200, 204]:
            print("Discord notification sent successfully.")
        else:
            print(f"Failed to send Discord notification: {response.status_code}, {response.text}")
            
    except Exception as e:
        print(f"Error sending to Discord: {e}")
    finally:
        if files:
            files["file"][1].close()

def get_data():
    """下載歷史數據並填補空值"""
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    tickers = [COMMODITY_TICKER] + STOCK_TICKERS
    print(f"Downloading data for: {tickers} from {start_date}")
    
    # 下載收盤價
    data = yf.download(tickers, start=start_date)['Close']
    
    # 填補空值 (避免台美休市日不同步造成的問題)
    data = data.ffill()
    return data

def analyze_market_status(df, stock_ticker):
    """
    自動分析市場狀態 (優化版)
    回傳：(成本狀態, 建議訊號, 開口數值)
    """
    # 取得最新與 20 天前的數據來判斷趨勢
    current_soybean = df[COMMODITY_TICKER].iloc[-1]
    prev_soybean = df[COMMODITY_TICKER].iloc[-20]
    
    # 計算黃豆短期趨勢變化 (%)
    soybean_trend_pct = ((current_soybean - prev_soybean) / prev_soybean) * 100
    
    if soybean_trend_pct > 2:
        cost_status = "⚠️ 成本升"
    elif soybean_trend_pct < -2:
        cost_status = "✅ 成本降"
    else:
        cost_status = "➡️ 成本平"

    # 計算「剪刀開口」 (Spread)
    # 正規化比較：(個股漲幅 - 黃豆漲幅)
    norm_soybean = (df[COMMODITY_TICKER] / df[COMMODITY_TICKER].iloc[0])
