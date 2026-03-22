import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from telegram import Bot

# ===== SETTINGS =====
BOT_TOKEN = "8778402329:AAEXFb1DAn7MXEhT8EHGZcWdxwByRQMruEA"
CHAT_ID = "1793924830"

URL = "https://www.manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId=20"

# ===== DATABASE =====
def setup_db():
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_updates (
            title TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def is_new(title):
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("SELECT title FROM seen_updates WHERE title=?", (title,))
    result = c.fetchone()
    conn.close()
    return result is None

def save_update(title):
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO seen_updates (title) VALUES (?)", (title,))
    conn.commit()
    conn.close()

# ===== TELEGRAM =====
def send_telegram(message):
    try:
        bot = Bot(token=BOT_TOKEN)
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("Sent:", message)
    except Exception as e:
        print("Telegram Error:", e)

# ===== SCRAPER =====
def scrape():
    try:
        response = requests.get(URL, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")

        updates_found = False

        # 🔴 TARGET ONLY REAL TABLE DATA
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")

            # Ensure valid row with content
            if len(cols) >= 2:
                title = cols[1].get_text(strip=True)

                # ignore short/garbage text
                if title and len(title) > 15:
                    if is_new(title):
                        send_telegram(title)
                        save_update(title)
                        updates_found = True

        if not updates_found:
            print("No new updates")

    except Exception as e:
        print("Error:", e)

# ===== MAIN =====
def main():
    print("Hydnews Scraper Started...")
    setup_db()

    while True:
        print("Checking for updates...")
        scrape()
        print("Waiting 5 minutes...")
        time.sleep(300)  # 5 minutes

# ===== RUN =====
if __name__ == "__main__":
    main()