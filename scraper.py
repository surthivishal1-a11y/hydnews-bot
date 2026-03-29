import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import urllib3
import warnings
import threading
from queue import Queue

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

BOT_TOKEN = "8778402329:AAGzD3n2P_miQeLOMkqeS2p5UZ28v3-nRGc"
CHAT_ID = "1793924830"
API_URL = "https://hydnews-api-production.up.railway.app"
THREADS = 10

PRIORITY_UNIVERSITIES = [
    "Osmania University",
    "JNTU Hyderabad",
    "Kakatiya University",
    "Telangana University",
    "Palamuru University",
]

db_lock = threading.Lock()
new_updates_found = []
new_updates_lock = threading.Lock()

def get_all_universities():
    url = "https://www.manabadi.co.in/institute/ViewDocUniversities.aspx"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    universities = []
    seen_ids = set()
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "DisplayDocsDetails.aspx?DocSourceId=" in href:
                name = link.text.strip()
                doc_id = href.split("DocSourceId=")[-1]
                if name and doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    universities.append({"name": name, "id": doc_id})
        print(f"Found {len(universities)} universities")
    except Exception as e:
        print(f"Error: {e}")
    return universities

def setup_db():
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS updates (title TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def is_new(title):
    with db_lock:
        conn = sqlite3.connect("news.db")
        c = conn.cursor()
        c.execute("SELECT title FROM updates WHERE title=?", (title,))
        result = c.fetchone()
        conn.close()
        return result is None

def save(title):
    with db_lock:
        conn = sqlite3.connect("news.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO updates(title) VALUES(?)", (title,))
        conn.commit()
        conn.close()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def send_to_api(university, title, url):
    try:
        requests.post(f"{API_URL}/updates/add", json={
            "university": university,
            "title": title,
            "url": url
        }, timeout=5)
    except Exception as e:
        print(f"API Error: {e}")

def scrape_university(name, doc_id):
    url = f"https://www.manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId={doc_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    found_new = False
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.find_all("a"):
            title = link.text.strip()
            if len(title) < 15:
                continue
            if any(x in title.lower() for x in [
                "login", "home", "mobile app", "books", "articles",
                "scholarships", "loans", "advertise", "manabadi",
                "institute login", "student login", "google play"
            ]):
                continue
            if is_new(title):
                send_to_api(name, title, url)
                send_telegram(f"🔔 NEW UPDATE\n\n🏫 {name}\n\n📢 {title}\n\n🔗 {url}")
                save(title)
                found_new = True
                with new_updates_lock:
                    new_updates_found.append(name)
                print(f"Sent: [{name}] {title}")
    except Exception as e:
        print(f"Error [{name}]: {e}")
    return found_new

def worker(queue, counter, counter_lock, total, priority_results):
    while True:
        try:
            uni = queue.get(timeout=3)
        except:
            break
        found = scrape_university(uni["name"], uni["id"])
        if uni["name"] in PRIORITY_UNIVERSITIES:
            with counter_lock:
                priority_results[uni["name"]] = found
        with counter_lock:
            counter[0] += 1
            print(f"[{counter[0]}/{total}] {uni['name']}")
        queue.task_done()

def main():
    setup_db()
    print("HydNews Scraper Starting...")

    universities = get_all_universities()
    if not universities:
        send_telegram("⚠️ Could not fetch university list")
        return

    send_telegram(
        f"✅ HydNews Started\n"
        f"🏫 Monitoring {len(universities)} universities\n"
        f"⚡ Fast mode — 10 parallel checks\n"
        f"🔗 API: Connected"
    )

    cycle = 1
    while True:
        print(f"\n--- Cycle {cycle} ---")
        start_time = time.time()
        new_updates_found.clear()

        queue = Queue()
        for uni in universities:
            queue.put(uni)

        counter = [0]
        counter_lock = threading.Lock()
        priority_results = {}

        threads = []
        for _ in range(THREADS):
            t = threading.Thread(
                target=worker,
                args=(queue, counter, counter_lock, len(universities), priority_results)
            )
            t.daemon = True
            t.start()
            threads.append(t)

        queue.join()

        elapsed = int(time.time() - start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60

        priority_status = ""
        for uni_name in PRIORITY_UNIVERSITIES:
            if uni_name in priority_results:
                status = "🆕 New update" if priority_results[uni_name] else "😴 No update"
                priority_status += f"\n{uni_name}: {status}"

        total_new = len(new_updates_found)

        send_telegram(
            f"✅ Cycle {cycle} Complete\n"
            f"🏫 {len(universities)} universities checked\n"
            f"🆕 New updates: {total_new}\n"
            f"⏱ Time: {minutes}m {seconds}s\n"
            f"\n📊 Priority:{priority_status}\n"
            f"\n💤 Next check in 5 minutes"
        )

        cycle += 1
        time.sleep(300)

if __name__ == "__main__":
    main()