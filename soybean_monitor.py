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
