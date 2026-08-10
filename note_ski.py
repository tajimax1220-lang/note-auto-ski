import time
import random
import os
import json
import urllib.parse
import re
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright

def parse_relative_minutes(time_str):
    if not time_str:
        return 999999
    match = re.search(r'(\d+)\s*(分|時間|日|か月|年)前', time_str)
    if not match:
        return 999999
    
    val = int(match.group(1))
    unit = match.group(2)
    
    if unit == "分":
        return val
    elif unit == "時間":
        return val * 60
    elif unit == "日":
        return val * 1440
    elif unit == "か月":
        return val * 43200
    elif unit == "年":
        return val * 518400
    return 999999

def verify_is_newest_order(page):
    """上位記事の投稿時間を解析し、新着順（新しい順）になっているか数値検証する"""
    # CSSセレクター記法へ修正
    cards = page.locator('section[class*="m-largeNoteWrapper"], article').all()
    minutes_list = []
    
    for card in cards[:5]:
        try:
            card_text = card.inner_text()
            match = re.search(r'(\d+\s*(?:分|時間|日|か月|年)前)', card_text)
            if match:
                time_str = match.group(1).replace(" ", "")
                mins = parse_relative_minutes(time_str)
                minutes_list.append((time_str, mins))
        except:
            continue
            
    if not minutes_list:
        return False, "投稿時間を取得できませんでした"

    first_time_str, first_mins = minutes_list[0]
    
    # 先頭記事が180分（3時間）以上前なら新着順とみなさない
    if first_mins > 180:
        return False, f"先頭記事が古いです ({first_time_str})"

    # 昇順（新しい順）チェック
    for i in range(len(minutes_list) - 1):
        if minutes_list[i][1] > minutes_list[i+1][1] + 30:
            return False, f"昇順になっていません ({minutes_list[i][0]} -> {minutes_list[i+1][0]})"

    return True, f"正常 (先頭: {first_time_str})"

def run():
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    hour = now.hour

    if 2 <= hour < 5:
        print(f"💤 現在 {hour}時（深夜2:00-5:00）のため、動作を停止します。")
        return

    # 【検証用】キーワードを「毎日更新」に固定
    keywords = ["毎日更新"]
    
    total_count = 0
    MAX_LIKES = 1  # 検証用：1件成功で即終了
    processed_users = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.3856.59",
            viewport={'width': 1920, 'height': 1080}
        )

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
        page.wait_for_timeout(8000) 

        if "つくる、つながる" in page.title():
            print("❌ ログイン失敗判定。終了します。")
            browser.close()
            return
        print("✅ ログイン成功を確認！")

        for word in keywords:
            if total_count >= MAX_LIKES:
                break
            
            print(f"\n🔎 検索開始: 【{word}】 (現在の合計: {total_count}/{MAX_LIKES})")
            url = f"https://note.com/search?q={urllib.parse.quote(word)}&context=note&mode=search&sort=new"
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            # 「新着」タブのクリック試行
            try:
                new_tab = page.locator('text="新着"').first
                if new_tab.is_visible():
                    new_tab.click(force=True)
                    page.wait_for_timeout(3000)
            except:
                pass

            # 新着順になっているか数値検証
            is_newest, reason = verify_is_newest_order(page)

            if not is_newest:
                print(f"  └ ⚠️ 新着順の検証失敗 ({reason})。このキーワードはスキップして次へ進みます。")
                continue
            else:
                print(f"  └ ✅ 新着順の検証成功 ({reason})")

            # スクロールしてボタンを取得
            for _ in range(2):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(2000)
            
            btns_locator = page.locator('button[aria-label*="スキ"][aria-label*="この記事にスキをつけたユーザーを見る"]')
            count_in_page = btns_locator.count()
            print(f"🔎 「{word}」で未実行のボタンを {count_in_page} 個発見")

            for i in range(count_in_page):
                if total_count >= MAX_LIKES:
                    break
                
                try:
                    target_btn = btns_locator.nth(i)
                    
                    if target_btn.is_visible() and target_btn.get_attribute("aria-pressed") != "true":
                        user_name = "Unknown"
                        post_time_text = ""
                        article_url = "Unknown"
                        
                        try:
                            parent_card = target_btn.locator('xpath=./ancestor::*[self::article or self::section or contains(@class, "Wrapper")][1]')
                            
                            # ユーザー名抽出
                            user_element = parent_card.locator('.o-largeNoteSummary__userName, [class*="userName"]').first
                            if user_element.count() > 0:
                                user_name = user_element.inner_text().strip()

                            # 記事URL抽出
                            link_element = parent_card.locator('a[href*="/n/"]').first
                            if link_element.count() > 0:
                                href = link_element.get_attribute("href")
                                if href:
                                    article_url = href if href.startswith("http") else f"https://note.com{href}"

                            # 投稿時間抽出
                            card_text = parent_card.inner_text()
                            match = re.search(r'(\d+\s*(?:分|時間|日|か月|年)前)', card_text)
                            if match:
                                post_time_text = match.group(1).replace(" ", "")
                        except:
                            pass

                        # 途中で古い記事（「日前」など）に到達したら即切り替え
                        if any(unit in post_time_text for unit in ["日前", "か月前", "年前"]):
                            print(f"  └ ⚠️ 古い記事（{post_time_text}）に到達したためキーワードを切り替えます。")
                            break

                        if user_name != "Unknown" and user_name in processed_users:
                            continue
                        
                        target_btn.scroll_into_view_if_needed()
                        page.wait_for_timeout(random.randint(2000, 3500))
                        
                        target_btn.click(force=True)
                        total_count += 1
                        
                        time_info = f" / 投稿時間: {post_time_text}" if post_time_text else ""
                        print(f"[{total_count}/{MAX_LIKES}] スキ！ ({word} / ユーザー: {user_name}{time_info})")
                        print(f"  └ 🔗 記事URL: {article_url}")
                        
                        if user_name != "Unknown":
                            processed_users.add(user_name)
                        
                        time.sleep(random.uniform(5, 10))
                except:
                    continue

        with open("cookie.txt", "w", encoding="utf-8") as f:
            json.dump(context.cookies(), f, indent=2)

        browser.close()
    print(f"\n--- 全行程完了: 合計 {total_count}件 ---")

if __name__ == "__main__":
    run()
