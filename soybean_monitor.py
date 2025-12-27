import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import os
from datetime import datetime, timedelta

# ==========================================
# 1. 設定區域 (Configuration)
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
# 2. 核心功能函式
# ==========================================

def send_discord_notify(msg, img_path=None):
    """發送訊息與圖片到 Discord"""
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤: 找不到 DISCORD_WEBHOOK_URL")
        return

    print(f"🔍 準備發送 Discord 通知...")
    try:
        data = {"content": msg}
        files = {}
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
    """下載數據並填補空值"""
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS + 10)).strftime('%Y-%m-%d')
    tickers = [COMMODITY_TICKER] + STOCK_TICKERS
    print(f"Downloading data for: {tickers} from {start_date}")
    
    data = yf.download(tickers, start=start_date, progress=False)['Close']
    data = data.ffill()
    return data

def get_material_strategy(stock_change, soy_change, gap):
    """
    更新後的策略邏輯：納入「終端售價風險」考量
    """
    cost_emoji = "✅" if soy_change < 0 else "🔻"
    cost_status = "成本降" if soy_change < 0 else "成本升"
    
    strategy_msg = ""
    status_icon = ""

    # --- 核心邏輯判斷 ---

    if soy_change < 0: # 情境 A: 原料成本在降 (理論上是利多)
        if stock_change > 0:
            # 股價漲 + 成本降 = 真正的好事
            status_icon = "🚀"
            strategy_msg = "**[利差擴大]** 毛利提升，股價反應正向"
        else:
            # 股價跌 + 成本降 = 注意！可能是「終端產品(豬價)」在跌
            if stock_change < -3.0: 
                # 跌幅明顯，市場在逃命
                status_icon = "⚠️"
                strategy_msg = "**[終端疲弱風險]** 成本雖降，但市場擔憂豬價/營收"
            else:
                # 跌幅輕微，可能只是盤整
                status_icon = "👀"
                strategy_msg = "**[觀望]** 成本優勢尚未發酵，等待營收回穩"
            
    else: # 情境 B: 原料成本在漲 (利空)
        if stock_change > 0:
            status_icon = "🔥"
            strategy_msg = "**[動能強勢]** 成功漲價轉嫁成本"
        else:
            status_icon = "☠️"
            strategy_msg = "**[雙殺]** 成本漲 + 售價跌，嚴格避開"

    # --- 買賣點輔助訊號 ---
    action_note = ""
    
    # 只有在「沒有終端風險」的時候，才建議接刀
    if gap > 15:
        action_note = " (🔴 乖離過大 | 勿追)"
    elif -5 <= gap <= 5 and soy_change < 0 and stock_change > -2:
        # 股價穩、成本降，才是好買點
        action_note = " (🟢 結構轉強 | 關注)"
    elif gap < -10 and soy_change < 0:
        # 雖然乖離大，但如果是因為豬價跌造成的，就要小心，不要隨便接
        action_note = " (🟡 跌深等待打底)"

    return {
        "text": f"{status_icon} {strategy_msg}{action_note}",
        "cost_info": f"{cost_emoji} {cost_status}"
    }

def plot_chart(data):
    plt.figure(figsize=(12, 6))
    plt.style.use('bmh') 
    
    normalized_data = (data / data.iloc[0]) * 100
    
    plt.plot(normalized_data.index, normalized_data[COMMODITY_TICKER], 
             label='Soybean (Cost)', color='red', linewidth=2.5, linestyle='--')
    
    colors = ['blue', 'green', 'orange', 'purple']
    for i, stock in enumerate(STOCK_TICKERS):
        clean_code = stock.split('.')[0]
        clean_name = STOCK_NAMES.get(clean_code, clean_code)
        
        plt.plot(normalized_data.index, normalized_data[stock], 
                 label=f"{clean_code} {clean_name}", color=colors[i % len(colors)], linewidth=1.5)

    plt.title(f"Soybean vs. Feed Stocks ({LOOKBACK_DAYS} Days Normalized)")
    plt.legend()
    plt.grid(True)
    
    img_path = "soybean_chart.png"
    plt.savefig(img_path)
    plt.close()
    return img_path

# ==========================================
# 3. 主程式
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
        
        # 數據計算
        try:
            current_prices = df.iloc[-1]
            prev_prices = df.iloc[-STRATEGY_WINDOW]
        except IndexError:
            current_prices = df.iloc[-1]
            prev_prices = df.iloc[0]

        soy_now = current_prices[COMMODITY_TICKER]
        soy_prev = prev_prices[COMMODITY_TICKER]
        soy_pct_change = ((soy_now - soy_prev) / soy_prev) * 100

        # 產生訊息
        latest_date = df.index[-1].strftime('%Y-%m-%d')
        msg = f"**【黃豆 vs 食品股 監控 (含終端風險)】**\n📅 日期: `{latest_date}`\n"
        msg += f"📉 黃豆成本(近{STRATEGY_WINDOW}日): `{soy_pct_change:+.2f}%`\n\n"
        msg += "**📊 AI 策略判讀:**\n"
        
        for stock_ticker in STOCK_TICKERS:
            stock_code = stock_ticker.split('.')[0]
            stock_name = STOCK_NAMES.get(stock_code, "")
            display_name = f"{stock_code} {stock_name}"
            
            s_now = current_prices[stock_ticker]
            s_prev = prev_prices[stock_ticker]
            stock_pct_change = ((s_now - s_prev) / s_prev) * 100
            
            norm_soy = (df[COMMODITY_TICKER] / df[COMMODITY_TICKER].iloc[0]) * 100
            norm_stock = (df[stock_ticker] / df[stock_ticker].iloc[0]) * 100
            gap = norm_stock.iloc[-1] - norm_soy.iloc[-1]

            analysis = get_material_strategy(stock_pct_change, soy_pct_change, gap)
            
            msg += f"> **{display_name}** ({stock_pct_change:+.1f}%)\n"
            msg += f"> 觀點: {analysis['text']}\n"
            msg += f"> (開口: `{gap:+.1f}` | {analysis['cost_info']})\n\n"

        msg += "💡 *新邏輯：若成本降但股價重挫，可能為「豬價/肉品」跌價風險，勿貿然接刀。*"

        print("Step 3: Sending Discord notification...")
        send_discord_notify(msg, img_path)
        print("Done.")

    except Exception as e:
        print(f"Error in main loop: {e}")

if __name__ == "__main__":
    main()
