import requests
from bs4 import BeautifulSoup
import sqlite3
import asyncio
from telegram import Bot

# ===== SETTINGS =====
BOT_TOKEN = "8778402329:AAEXFb1DAn7MXEhT8EHGZcWdxwByRQMruEA"
CHAT_ID = "1793924830"
URL = "https://manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId=20"

# ===== DATABASE =====
def setup_db():
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_updates (
            title TEXT PRIMARY KEY,
            seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_new(title):
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute("SELECT title FROM seen_updates WHERE title=?", (title,))
    result = c.fetchone()
    conn.close()
    return result is None

def save_update(title):
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO seen_updates (title) VALUES (?)", (title,))
    conn.commit()
    conn.close()

# ===== SCRAPER =====
def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(URL, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        updates = []
        for link in soup.find_all('a'):
            text = link.get_text(strip=True)

            if len(text) > 20 and any(word in text.lower() for word in [
                'result', 'exam', 'notification', 'timetable', 'hall ticket'
            ]):
                updates.append(text)

        return updates[:10]

    except Exception as e:
        print("Error:", e)
        return []

# ===== TELEGRAM =====
async def send_telegram(message):
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print("Telegram Error:", e)

# ===== MAIN =====
async def main():
    setup_db()
    print("HydNews Scraper Started...")

    while True:
        print("Checking for updates...")

        updates = scrape()

        if not updates:
            print("No updates found from site.")
            await send_telegram("⚠️ No updates found")
        else:
            new_found = False

            for update in updates:
                if is_new(update):
                    save_update(update)
                    msg = f"🔔 NEW UPDATE\n\n{update}\n\nSource: Manabadi"
                    await send_telegram(msg)
                    print("Sent:", update)
                    new_found = True
                    await asyncio.sleep(2)

            if not new_found:
                print("No updates sent.")
                await send_telegram("✅ No new updates")

        print("Waiting 5 minutes...\n")
        await asyncio.sleep(300)

# ===== RUN =====
if __name__ == "__main__":
    asyncio.run(main())
