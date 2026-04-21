import time
import random
import os
import json
import urllib.parse
import re
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright

def run():
    # --- 日本時間の取得と時間帯判定 ---
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    hour = now.hour

    # 1. 深夜 2:00 ～ 5:00 は動作させずに終了
    if 2 <= hour < 5:
        print(f"💤 現在 {hour}時（深夜2:00-5:00）のため、動作を停止します。")
        return

    # 2. 時間帯別のキーワード設定
    if 14 <= hour < 17:
        # 14:00 - 16:59
        keywords = ["休職中", "不登校", "在宅ワーク", "読書", "学び", "習慣", "自己啓発", "スキルアップ"]
    elif 17 <= hour < 20:
        # 17:00 - 19:59
        keywords = ["帰り道", "夕暮れ", "孤独", "読書", "学び", "習慣", "自己啓発", "スキルアップ"]
    else:
        # それ以外の時間帯
        keywords = [
            "このままでいいのかな", "モヤモヤ", "ぐるぐる考える", "吐き出す", 
            "ひとり反省会", "自分を立て直す", "本当はどうしたい", "もう頑張れない", 
            "自分を好きになりたい", "楽に生きたい", "言葉にできない", 
            "誰にも言えない本音", "自分のペース", "眠れない夜", "自分と向き合う" "自己啓発", "スキルアップ"
        ]
    
    # 20個に届くまで順に試すため、順番をランダムに入れ替える
    random.shuffle(keywords)
    
    total_count = 0
    MAX_LIKES = 20

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 指紋情報はEdge 146に完全固定（安定動作維持）
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.3856.59",
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                "Accept-Language": "ja-JP,ja;q=0.9",
                "Sec-Ch-Ua": '"Not(A:Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"'
            }
        )

        # クッキー適用ロジック（安定版）
        if os.path.exists("cookie.txt"):
            try:
                with open("cookie.txt", "r", encoding="utf-8") as f:
                    raw_cookies = json.load(f)
                clean_cookies = []
                for ck in raw_cookies:
                    if ck.get("sameSite") not in ["Strict", "Lax", "None"]:
                        ck["sameSite"] = "Lax"
                    clean_ck = {k: v for k, v in ck.items() if k in ["name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"]}
                    clean_cookies.append(clean_ck)
                context.add_cookies(clean_cookies)
                print(f"✅ クッキー適用完了: {len(clean_cookies)}件")
            except Exception as e:
                print(f"⚠️ クッキーエラー回避: {e}")

        page = context.new_page()

        # ログイン判定ロジック（安定版）
        print(f"🚀 noteへアクセス中... (現在時刻: {hour}時)")
        page.goto("https://note.com/notifications", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(12000) 

        title = page.title()
        has_user_menu = page.locator('button[aria-label="ユーザーメニュー"]').count() > 0
        has_post_btn = page.locator('a[href="/posts/new"]').count() > 0
        has_noti_mark = any(char in title for char in ["☆", "★", "(", "1", "2", "3", "4", "5", "6", "7", "8", "9"])

        print(f"📄 [判定ログ] タイトル: {title}")
        print(f"📄 [要素ログ] メニュー: {has_user_menu}, 投稿ボタン: {has_post_btn}, 通知マーク: {has_noti_mark}")

        if (has_user_menu or has_post_btn or has_noti_mark or "通知" in title) and "つくる、つながる" not in title:
            print("✅ ログイン成功を確認！")
        else:
            print("❌ ログイン失敗判定。")
            browser.close()
            return

        # 成功したセッションを保存
        with open("cookie.txt", "w", encoding="utf-8") as f:
            json.dump(context.cookies(), f, indent=2)

        # --- キーワード・おかわりループ ---
        for word in keywords:
            if total_count >= MAX_LIKES:
                break
            
            print(f"🔎 検索開始: 【{word}】 (現在の合計: {total_count}/{MAX_LIKES})")
            url = f"https://note.com/search?q={urllib.parse.quote(word)}&mode=search&sort=new"
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(3000)
            
            btns = page.locator('button[aria-label="スキ"][aria-pressed="false"]').all()
            print(f"🔎 「{word}」で未実行のボタンを {len(btns)} 個発見")

            for btn in btns:
                if total_count >= MAX_LIKES: 
                    break
                try:
                    btn.scroll_into_view_if_needed()
                    time.sleep(random.uniform(4, 9))
                    btn.click(force=True)
                    total_count += 1
                    print(f"[{total_count}/{MAX_LIKES}] スキ！ ({word})")
                    time.sleep(random.uniform(15, 25))
                except: 
                    continue
            
            if total_count < MAX_LIKES:
                print(f"💡 「{word}」の検索結果をすべて処理しました。次へ進みます。")

        browser.close()
    print(f"--- 全行程完了: 合計 {total_count}件 ---")

if __name__ == "__main__":
    run()
