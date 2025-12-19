import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import os
from datetime import datetime, timedelta

# --- 設定 ---
# 黃豆期貨 (美股)
COMMODITY_TICKER = "ZS=F" 
# 台股 (福壽, 大成, 卜蜂)
STOCK_TICKERS = ["1219.TW", "1210.TW", "1215.TW"] 
# 監控天數
LOOKBACK_DAYS = 180 

# Discord Webhook URL (從 GitHub Secrets 讀取)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord_notify(msg, img_path=None):
    if not DISCORD_WEBHOOK_URL:
        print("Error: DISCORD_WEBHOOK_URL is not set.")
        return

    try:
        data = {"content": msg}
        files = {}
        
        # 如果有圖片，就附加在請求中
        if img_path and os.path.exists(img_path):
            # 'file' 是 Discord 識別附件的關鍵字
            files = {"file": (os.path.basename(img_path), open(img_path, "rb"))}
        
        # 發送請求
        if files:
            response = requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)
        else:
            response = requests.post(DISCORD_WEBHOOK_URL, json=data)

        # 檢查回應
        if response.status_code in [200, 204]:
            print("Discord notification sent successfully.")
        else:
            print(f"Failed to send Discord notification: {response.status_code}, {response.text}")
            
    except Exception as e:
        print(f"Error sending to Discord: {e}")
    finally:
        # 關閉檔案控點 (如果有的話)
        if files:
            files["file"][1].close()

def get_data():
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    # 下載數據
    tickers = [COMMODITY_TICKER] + STOCK_TICKERS
    data = yf.download(tickers, start=start_date)['Close']
    # 填補空值
    data = data.ffill()
    return data

def plot_chart(data):
    plt.figure(figsize=(12, 6))
    plt.style.use('bmh') 
    
    # 正規化數據：以第一天為基準 (100)
    normalized_data = (data / data.iloc[0]) * 100
    
    # 繪製黃豆 (紅色虛線)
    plt.plot(normalized_data.index, normalized_data[COMMODITY_TICKER], 
             label='Soybean Futures (ZS=F)', color='red', linewidth=2.5, linestyle='--')
    
    # 繪製台股
    colors = ['blue', 'green', 'orange']
    for i, stock in enumerate(STOCK_TICKERS):
        plt.plot(normalized_data.index, normalized_data[stock], 
                 label=stock, color=colors[i % len(colors)], linewidth=1.5)

    plt.title(f"Soybean vs. Feed Stocks ({LOOKBACK_DAYS} Days)")
    plt.xlabel("Date")
    plt.ylabel("Relative Performance (Start=100)")
    plt.legend()
    plt.grid(True)
    
    img_path = "soybean_chart.png"
    plt.savefig(img_path)
    plt.close()
    return img_path

def main():
    try:
        print("Fetching data...")
        df = get_data()
        
        if df.empty:
            print("No data fetched.")
            return

        print("Plotting chart...")
        img_path = plot_chart(df)
        
        # 計算簡單漲跌幅
        soybean_change = ((df[COMMODITY_TICKER].iloc[-1] - df[COMMODITY_TICKER].iloc[0]) / df[COMMODITY_TICKER].iloc[0]) * 100
        latest_date = df.index[-1].strftime('%Y-%m-%d')
        
        # 訊息內容
        msg = f"**【黃豆 vs 食品股監控】**\n📅 日期: `{latest_date}`\n"
        msg += f"📉 黃豆期貨區間變動: `{soybean_change:.2f}%`\n"
        msg += "💡 *觀察重點: 若紅線(成本)大幅向下，藍/綠線(股價)尚未反應，可能為進場機會。*"

        send_discord_notify(msg, img_path)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
