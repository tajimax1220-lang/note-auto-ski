import time
import random
import os
import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright

def run():
    # --- 日本時間の取得と時間帯判定 ---
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    hour = now.hour

    if 2 <= hour < 5:
        print(f"💤 現在 {hour}時（深夜2:00-5:00）のため、動作を停止します。")
        return

    # キーワード設定
    if 14 <= hour < 17:
        keywords = ["休職中", "不登校", "在宅ワーク", "読書", "学び", "習慣", "自己啓発", "スキルアップ"]
    elif 17 <= hour < 20:
        keywords = ["帰り道", "夕暮れ", "孤独", "読書", "学び", "習慣", "自己啓発", "スキルアップ"]
    else:
        keywords = [
            "このままでいいのかな", "モヤモヤ", "ぐるぐる考える", "吐き出す", 
            "ひとり反省会", "自分を立て直す", "本当はどうしたい", "もう頑張れない", 
            "自分を好きになりたい", "楽に生きたい", "言葉にできない", 
            "誰にも言えない本音", "自分のペース", "眠れない夜", "自分と向き合う", "自己啓発", "スキルアップ"
        ]
    
    random.shuffle(keywords)
    total_count = 0
    MAX_LIKES = 20
    
    # 処理済みユーザーを記録するセット（同一稼働内での重複防止）
    processed_users = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.3856.59",
            viewport={'width': 1920, 'height': 1080}
        )

        # クッキー適用
        if os.path.exists("cookie.txt"):
            try:
                with open("cookie.txt", "r", encoding="utf-8") as f:
                    raw_cookies = json.load(f)
                context.add_cookies(raw_cookies)
                print(f"✅ クッキー適用完了: {len(raw_cookies)}件")
            except Exception as e:
                print(f"⚠️ クッキーエラー回避: {e}")

        page = context.new_page()

        print(f"🚀 noteへアクセス中... (現在時刻: {hour}時)")
        page.goto("https://note.com/notifications", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(10000) 

        # ログイン確認（簡易化）
        if "つくる、つながる" in page.title():
            print("❌ ログイン失敗判定。")
            browser.close()
            return
        print("✅ ログイン成功を確認！")

        # --- キーワードループ ---
        for word in keywords:
            if total_count >= MAX_LIKES:
                break
            
            print(f"🔎 検索開始: 【{word}】 (現在の合計: {total_count}/{MAX_LIKES})")
            url = f"https://note.com/search?q={urllib.parse.quote(word)}&mode=search&sort=new"
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            
            # 1キーワードにつき最大3回まで追加スクロールして記事を掘り起こす
            for _ in range(3):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(2000)
            
            # 各記事のカード要素を特定して取得
            cards_locator = page.locator('div[data-testname="card"], article')
            cards_count = cards_locator.count()
            print(f"🔎 「{word}」の検索結果から記事候補を {cards_count} 件取得しました")

            for i in range(cards_count):
                if total_count >= MAX_LIKES:
                    break
                
                try:
                    card = cards_locator.nth(i)
                    if not card.is_visible():
                        continue
                        
                    # カード内からユーザー名（クリエイターページへのリンクテキスト）を抽出
                    user_element = card.locator('a[href*="/n/"]').first
                    if user_element.count() > 0:
                        user_name = user_element.inner_text().strip()
                    else:
                        user_name = "Unknown"
