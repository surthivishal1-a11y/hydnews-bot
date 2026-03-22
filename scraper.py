import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from telegram import Bot

# ===== YOUR SETTINGS =====
BOT_TOKEN = "8778402329:AAEXFb1DAn7MXEhT8EHGZcWdxwByRQMruEA"
CHAT_ID = "1793924830"

# 👉 ONLY ONE WEBSITE
URL = "https://manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId=20"

# ===== DATABASE SETUP =====
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
    c.execute("INSERT INTO seen_updates (title) VALUES (?)", (title,))
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
def check_updates():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(URL, headers=headers, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")

        # 👉 Adjust this if website changes
        links = soup.find_all("a")

        new_found = False

        for link in links:
            title = link.text.strip()

            if title and len(title) > 10:  # filter junk
                if is_new(title):
                    save_update(title)
                    send_telegram(title)
                    new_found = True

        if not new_found:
            print("No updates found")

    except Exception as e:
        print("Error:", e)

# ===== MAIN LOOP =====
if _name_ == "_main_":
    print("Hydnews Scraper Started...")

    setup_db()

    while True:
        print("Checking for updates...")
        check_updates()
        print("Waiting 5 minutes...")
        time.sleep(300)