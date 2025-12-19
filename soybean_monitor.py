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
    norm_soybean = (df[COMMODITY_TICKER] / df[COMMODITY_TICKER].iloc[0]) * 100
    norm_stock = (df[stock_ticker] / df[stock_ticker].iloc[0]) * 100
    
    spread = norm_stock.iloc[-1] - norm_soybean.iloc[-1]
    
    # --- 訊號判斷邏輯 (由寬到窄) ---
    if spread > 15:
        # 開口過大，代表已經漲了一大段
        signal = "🔥 **強勢多頭 (續抱/獲利)**"
    elif spread > 5 and soybean_trend_pct <= 0:
        # 開口適中 + 成本沒漲 = 最佳佈局點
        signal = "🌟 **黃金開口 (佈局點)**"
    elif spread > 0:
        # 股價剛開始強過原料
        signal = "📈 轉強中"
    elif spread < -10:
        # 股價遠低於原料漲幅
        signal = "☠️ **結構轉弱 (避開)**"
    elif spread < -5:
        signal = "🥶 利潤壓縮"
    else:
        signal = "👀 觀望整理"

    return cost_status, signal, spread

def plot_chart(data):
    """繪製走勢比較圖"""
    plt.figure(figsize=(12, 6))
    plt.style.use('bmh') 
    
    # 正規化數據：以第一天為基準 (100)
    normalized_data = (data / data.iloc[0]) * 100
    
    # 繪製黃豆 (紅色虛線，加粗)
    plt.plot(normalized_data.index, normalized_data[COMMODITY_TICKER], 
             label='Soybean (Cost)', color='red', linewidth=2.5, linestyle='--')
    
    # 繪製台股
    colors = ['blue', 'green', 'orange']
    for i, stock in enumerate(STOCK_TICKERS):
        clean_name = stock.split('.')[0] # 去除 .TW
        plt.plot(normalized_data.index, normalized_data[stock], 
                 label=clean_name, color=colors[i % len(colors)], linewidth=1.5)

    plt.title(f"Soybean vs. Feed Stocks ({LOOKBACK_DAYS} Days Normalized)")
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
        
        # --- 產生訊息內容 ---
        latest_date = df.index[-1].strftime('%Y-%m-%d')
        msg = f"**【黃豆 vs 食品股 智能監控】**\n📅 日期: `{latest_date}`\n"
        
        # 黃豆整體漲跌 (區間)
        soybean_change = ((df[COMMODITY_TICKER].iloc[-1] - df[COMMODITY_TICKER].iloc[0]) / df[COMMODITY_TICKER].iloc[0]) * 100
        msg += f"📉 黃豆區間變動: `{soybean_change:.2f}%`\n\n"
        
        msg += "**📊 個股 AI 判讀:**\n"
        
        for stock in STOCK_TICKERS:
            cost_status, signal, spread = analyze_market_status(df, stock)
            stock_name = stock.split('.')[0] 
            
            # 組合訊息
            msg += f"> **{stock_name}**: {signal}\n"
            msg += f"> (開口度: `{spread:.1f}` | {cost_status})\n\n"

        msg += "💡 *開口度大於 5 且成本穩定，通常為最佳切入點；若開口過大(>15)則留意追高風險。*"

        print("Sending Discord notification...")
        send_discord_notify(msg, img_path)
        print("Done.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
    
def send_discord_notify(msg, img_path=None):
    """發送訊息與圖片到 Discord (Debug 版)"""
    
    # 1. 檢查網址是否存在
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤: 找不到 DISCORD_WEBHOOK_URL 環境變數！")
        print("   -> 請檢查 GitHub Settings > Secrets 是否有設定")
        print("   -> 請檢查 YAML 檔的 env: 區塊是否正確對應")
        return

    print(f"🔍 嘗試發送 Webhook，網址長度: {len(DISCORD_WEBHOOK_URL)}") # 不印出完整網址以保安全

    try:
        data = {"content": msg}
        files = {}
        
        if img_path and os.path.exists(img_path):
            files = {"file": (os.path.basename(img_path), open(img_path, "rb"))}
        
        # 發送請求
        if files:
            response = requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)
        else:
            response = requests.post(DISCORD_WEBHOOK_URL, json=data)

        # 2. 檢查 Discord 回傳的詳細錯誤
        if response.status_code in [200, 204]:
            print("✅ Discord 通知發送成功！")
        else:
            print(f"❌ 發送失敗！狀態碼: {response.status_code}")
            print(f"❌ 錯誤內容: {response.text}") # 這裡會顯示 Discord 拒絕的具體原因
            
    except Exception as e:
        print(f"❌ 發生異常: {e}")
    finally:
        if files:
            files["file"][1].close()
