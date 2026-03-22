import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from telegram import Bot

BOT_TOKEN = "8778402329:AAEXFb1DAn7MXEhT8EHGZcWdxwByRQMruEA"
CHAT_ID = "1793924830"

URL = "https://www.manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId=20"

def setup_db():
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS seen_updates (title TEXT PRIMARY KEY)")
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

def send_telegram(message):
    try:
        bot = Bot(token=BOT_TOKEN)
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("Sent:", message)
    except Exception as e:
        print("Telegram Error:", e)

def scrape():
    try:
        response = requests.get(URL, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")

        links = soup.find_all("a")

        for link in links:
            title = link.get_text(strip=True)

            if title and len(title) > 10:
                if is_new(title):
                    send_telegram(title)
                    save_update(title)

    except Exception as e:
        print("Error:", e)

def main():
    print("Started...")
    setup_db()

    while True:
        print("Checking...")
        scrape()
        time.sleep(300)

if _name_ == "_main_":
    main()