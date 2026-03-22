import requests
from bs4 import BeautifulSoup
import sqlite3
import asyncio
from telegram import Bot
import urllib3

# disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SETTINGS
BOT_TOKEN = "8778402329:AAEXFb1DAn7MXEhT8EHGZcWdxwByRQMruEA"
CHAT_ID = "1793924830"
URL = "https://manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId=20"

# DATABASE SETUP
def setup_db():
    conn = sqlite3.connect('news.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS seen_updates
                 (title TEXT PRIMARY KEY, seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
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

# SCRAPER (LATEST 10 ONLY)
def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(URL, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        updates = []

        for link in soup.find_all('a'):
            text = link.get_text(strip=True)
            href = link.get('href')

            if href and len(text) > 20 and any(word in text.lower() for word in [
                'osmania', 'result', 'exam', 'hall ticket', 'notification', 'timetable', 'ou '
            ]):

                if not href.startswith("http"):
                    href = "https://manabadi.co.in/" + href

                updates.append((text, href))

        # take latest 10
        updates = updates[::-1][:10]

        return updates

    except Exception as e:
        print(f"Error: {e}")
        return []

# TELEGRAM SEND
async def send_telegram(message):
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"Telegram Error: {e}")

# MAIN LOOP
async def main():
    setup_db()
    print("HydNews Scraper Started...")

    while True:
        print("Checking for updates...")
        updates = scrape()

        sent_any = False

        for title, link in updates:
            if is_new(title):
                save_update(title)

                message = f"🔔 NEW UPDATE\n\n{title}\n\n{link}"
                await send_telegram(message)

                print(f"Sent: {title}")
                sent_any = True
                await asyncio.sleep(2)

        # if nothing new
        if not sent_any:
            msg = "❌ No new updates found."
            await send_telegram(msg)
            print("No updates sent.")

        print("Done. Waiting 5 minutes...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
