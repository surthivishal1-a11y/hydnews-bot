import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import urllib3
import warnings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

BOT_TOKEN = "8778402329:AAGzD3n2P_miQeLOMkqeS2p5UZ28v3-nRGc"
CHAT_ID = "1793924830"

def get_all_universities():
    """Automatically fetch ALL universities from manabadi"""
    url = "https://www.manabadi.co.in/institute/ViewDocUniversities.aspx"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    universities = []
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "DisplayDocsDetails.aspx?DocSourceId=" in href:
                name = link.text.strip()
                doc_id = href.split("DocSourceId=")[-1]
                if name and doc_id:
                    universities.append({"name": name, "id": doc_id})
        print(f"Found {len(universities)} universities automatically")
    except Exception as e:
        print(f"Error fetching university list: {e}")
    return universities

def setup_db():
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS updates (title TEXT PRIMARY KEY)")
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

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print("Telegram Error:", e)

def scrape_university(name, doc_id):
    url = f"https://www.manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId={doc_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.find_all("a"):
            title = link.text.strip()
            if len(title) < 15:
                continue
            if any(x in title.lower() for x in ["login", "home", "mobile app", "books", "articles", "scholarships", "loans", "advertise"]):
                continue
            if is_new(title):
                message = f"🔔 NEW UPDATE\n\n🏫 {name}\n\n📢 {title}\n\n🔗 {url}"
                send_telegram(message)
                save(title)
                print(f"Sent: [{name}] {title}")
                time.sleep(1)
    except Exception as e:
        print(f"Error [{name}]: {e}")

def main():
    setup_db()
    print("HydNews — Auto fetching all universities from Manabadi...")
    universities = get_all_universities()
    if not universities:
        send_telegram("⚠️ Could not fetch university list")
        return
    send_telegram(f"✅ System started — monitoring {len(universities)} universities")
    while True:
        print(f"\nChecking {len(universities)} universities...")
        for uni in universities:
            scrape_university(uni["name"], uni["id"])
            time.sleep(2)
        print("All done. Waiting 5 minutes...")
        time.sleep(300)

if _name_ == "_main_":
    main()