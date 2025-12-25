import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import os
from datetime import datetime, timedelta

# ==========================================
# 1. 設定區域 (Configuration)
# ==========================================

# 黃豆期貨 (美股代號)
COMMODITY_TICKER = "ZS=F"

# 台股代號 (建議保留 .TW 格式以利 yfinance 抓取)
STOCK_TICKERS = ["1219.TW", "1210.TW", "1215.TW"]

# 股票代碼與簡稱對照表 (新增功能)
STOCK_NAMES = {
    "1201": "味全",
    "1210": "大成",
    "1215": "卜蜂",
    "1218": "泰山",
    "1219": "福壽",
    "1225": "福懋油"
}

# 繪圖監控天數 (過去半年，適合波段觀察)
LOOKBACK_DAYS = 180

# 策略判斷天數 (計算近期漲跌幅用，例如過去 20 天)
STRATEGY_WINDOW = 20

# Discord Webhook URL (從 GitHub Secrets 或環境變數讀取)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# ==========================================
# 2. 核心功能函式
# ==========================================

def send_discord_notify(msg, img_path=None):
    """發送訊息與圖片到 Discord (包含錯誤處理)"""
    
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤: 找不到 DISCORD_WEBHOOK_URL 環境變數！")
        return

    print(f"🔍 準備發送 Discord 通知...")

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
            print("✅ Discord 通知發送成功！")
        else:
            print(f"❌ 發送失敗: {response.status_code}, {response.text}")
            
    except Exception as e:
        print(f"❌ 發送異常: {e}")
    finally:
        if files:
            files["file"][1].close()

def get_data():
    """下載歷史數據並填補空值"""
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS + 10)).strftime('%Y-%m-%d')
    tickers = [COMMODITY_TICKER] + STOCK_TICKERS
    print(f"Downloading data for: {tickers} from {start_date}")
    
    # 下載收盤價
    data = yf.download(tickers, start=start_date, progress=False)['Close']
    
    # 填補空值 (避免台美休市日不同步造成的問題)
    data = data.ffill()
    return data

def get_material_strategy(stock_change, soy_change, gap):
    """
    根據股價與黃豆(原料)的漲跌幅關係，給出策略建議 (新版策略矩陣)
    :param stock_change: 個股近期漲跌幅
    :param soy_change: 黃豆近期漲跌幅
    :param gap: 開口度 (Normalized Stock - Normalized Soy)
    """
    
    # 1. 判斷成本狀態
    cost_status = "成本降" if soy_change < 0 else "成本升"
    cost_emoji = "✅" if soy_change < 0 else "🔻"
    
    strategy_msg = ""
    status_icon = ""

    # 2. 策略矩陣邏輯 (四象限)
    if soy_change < 0: # --- 情境：成本降低 (原料跌) ---
        if stock_change > 0:
            status_icon = "🚀"
            strategy_msg = "**[利差擴大]** 獲利爆發期，續抱/加碼"
        else:
            # 股價還在跌，但成本已經降了 -> 注意是否有超跌買點
            status_icon = "👀"
            strategy_msg = "**[潛在轉機]** 成本優勢尚未反應，留意打底"
            
    else: # --- 情境：成本上升 (原料漲) ---
        if stock_change > 0:
            # 股價跟著漲，代表有漲價轉嫁能力
            status_icon = "🔥"
            strategy_msg = "**[動能強勢]** 產品漲價成功，順勢操作"
        else:
            # 成本漲，股價跌 -> 雙殺
            status_icon = "☠️"
            strategy_msg = "**[利潤壓縮]** 獲利遭侵蝕，建議避開"

    # 3. 結合開口度做最後修飾
    extra_note = ""
    if gap > 15:
        extra_note = " (⚠️乖離過大)"
    elif gap < -10 and soy_change < 0:
        extra_note = " (✨黃金交叉預備)"

    return {
        "text": f"{status_icon} {strategy_msg}{extra_note}",
        "cost_info": f"{cost_emoji} {cost_status}"
    }

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
    colors = ['blue', 'green', 'orange', 'purple']
    for i, stock in enumerate(STOCK_TICKERS):
        clean_code = stock.split('.')[0] # 去除 .TW
        clean_name = STOCK_NAMES.get(clean_code, clean_code) # 取得中文名
        
        plt.plot(normalized_data.index, normalized_data[stock], 
                 label=f"{clean_code} {clean_name}", color=colors[i % len(colors)], linewidth=1.5)

    plt.title(f"Soybean vs. Feed Stocks ({LOOKBACK_DAYS} Days Normalized)")
    plt.xlabel("Date")
    plt.ylabel("Relative Performance (Start=100)")
    plt.legend()
    plt.grid(True)
    
    img_path = "soybean_chart.png"
    plt.savefig(img_path)
    plt.close()
    return img_path

# ==========================================
# 3. 主程式流程
# ==========================================

def main():
    try:
        print("Step 1: Fetching data...")
        df = get_data()
        
        if df.empty:
            print("No data fetched.")
            return

        print("Step 2: Plotting chart...")
        img_path = plot_chart(df)
        
        # --- 數據計算準備 ---
        # 取得最新與 N 天前的數據來計算「近期漲跌幅」(用於策略判斷)
        try:
            current_prices = df.iloc[-1]
            prev_prices = df.iloc[-STRATEGY_WINDOW] # 20天前
        except IndexError:
            # 萬一資料不足 20 天，改用第一天
            current_prices = df.iloc[-1]
            prev_prices = df.iloc[0]

        # 計算黃豆近期漲跌
        soy_now = current_prices[COMMODITY_TICKER]
        soy_prev = prev_prices[COMMODITY_TICKER]
        soy_pct_change = ((soy_now - soy_prev) / soy_prev) * 100

        # --- 產生訊息內容 ---
        latest_date = df.index[-1].strftime('%Y-%m-%d')
        msg = f"**【黃豆 vs 食品股 智能監控】**\n📅 日期: `{latest_date}`\n"
        msg += f"📉 黃豆(近{STRATEGY_WINDOW}日)變動: `{soy_pct_change:+.2f}%`\n\n"
        msg += "**📊 個股 AI 策略判讀:**\n"
        
        for stock_ticker in STOCK_TICKERS:
            # 1. 準備數據
            stock_code = stock_ticker.split('.')[0]
            stock_name = STOCK_NAMES.get(stock_code, "")
            display_name = f"{stock_code} {stock_name}"
            
            # 個股近期漲跌
            s_now = current_prices[stock_ticker]
            s_prev = prev_prices[stock_ticker]
            stock_pct_change = ((s_now - s_prev) / s_prev) * 100
            
            # 開口度 (用全區間正規化計算)
            norm_soy = (df[COMMODITY_TICKER] / df[COMMODITY_TICKER].iloc[0]) * 100
            norm_stock = (df[stock_ticker] / df[stock_ticker].iloc[0]) * 100
            gap = norm_stock.iloc[-1] - norm_soy.iloc[-1]

            # 2. 呼叫策略核心
            analysis = get_material_strategy(stock_pct_change, soy_pct_change, gap)
            
            # 3. 組合訊息 (使用 Blockquote 格式 > )
            msg += f"> **{display_name}** ({stock_pct_change:+.1f}%)\n"
            msg += f"> 策略: {analysis['text']}\n"
            msg += f"> (開口度: `{gap:+.1f}` | {analysis['cost_info']})\n\n"

        msg += "💡 *策略邏輯：結合「原料成本漲跌」與「股價動能」之雙向判讀矩陣。*"

        print("Step 3: Sending Discord notification...")
        send_discord_notify(msg, img_path)
        print("Done.")

    except Exception as e:
        print(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()
