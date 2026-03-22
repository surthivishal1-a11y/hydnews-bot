import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import urllib3
import warnings

# 🔥 REMOVE SSL WARNING
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

# ===== SETTINGS =====
BOT_TOKEN = "8778402329:AAEXFb1DAn7MXEhT8EHGZcWdxwByRQMruEA"
CHAT_ID = "1793924830"

URL = "https://www.manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId=20"


# ===== DATABASE =====
def setup_db():
    conn = sqlite3.connect("news.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            title TEXT PRIMARY KEY
        )
    """)

    conn.commit()
    conn.close()


def is_new(title):
    conn = sqlite3.connect("news.db")
    c = conn.cursor()

    c.execute("SELECT title FROM updates WHERE title=?", (title,))
    result = c.fetchone()

    conn.close()
    return result is None


def save(title):
    conn = sqlite3.connect("news.db")
    c = conn.cursor()

    c.execute("INSERT OR IGNORE INTO updates(title) VALUES(?)", (title,))
    conn.commit()
    conn.close()


# ===== TELEGRAM =====
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        })
    except Exception as e:
        print("Telegram Error:", e)


# ===== SCRAPER =====
def check_updates():
    print("Checking updates...")

    try:
        res = requests.get(URL, verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")

        links = soup.find_all("a")

        updates_found = []

        for link in links:
            title = link.text.strip()

            # 🔥 FILTER ONLY VALID ITEMS
            if len(title) < 10:
                continue

            if any(x in title.lower() for x in [
                "login", "home", "mobile app", "books", "articles",
                "teachers", "institutes", "loans"
            ]):
                continue

            updates_found.append(title)

            if is_new(title):
                message = f"🆕 NEW UPDATE:\n{title}\n{URL}"
                send_telegram(message)
                save(title)
                print("Sent:", title)

        # 🔥 SEND STATUS EVEN IF NO UPDATE
        if len(updates_found) == 0:
            send_telegram("❌ No updates found on website")
            print("No updates on site")

        else:
            send_telegram(f"✅ Checked: {len(updates_found)} items found")
            print("Checked items:", len(updates_found))

    except Exception as e:
        send_telegram(f"⚠️ ERROR:\n{e}")
        print("Error:", e)


# ===== MAIN LOOP =====
def main():
    setup_db()

    print("Scraper Started...")

    while True:
        check_updates()
        print("Waiting 5 minutes...\n")
        time.sleep(300)   # 5 minutes


# ===== RUN =====
if _name_ == "_main_":
    main()