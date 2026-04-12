import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import urllib3
import warnings
import threading
from queue import Queue
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

BOT_TOKEN = "8778402329:AAEXFb1DAn7MXEhT8EHGZcWdxwByRQMruEA"
CHAT_ID = "1793924830"
API_URL = "https://hydnews-api-production.up.railway.app"
THREADS = 15

db_lock = threading.Lock()
new_updates_lock = threading.Lock()
new_updates_found = []
daily_count = [0]
daily_lock = threading.Lock()
last_reset_date = [datetime.now().date()]

MASTER_PAGES = [
    "https://www.manabadi.co.in/institute/Universities-Boards-Entrance-exams-recruitment-exams-of-AP-and-TS.htm",
    "https://www.manabadi.co.in/institute/ViewDocUniversities.aspx",
    "https://www.manabadi.co.in/institute/ViewDocBoards.aspx",
    "https://www.manabadi.co.in/institute/ViewDocEntranceExams.aspx",
    "https://www.manabadi.co.in/institute/ViewDocIndependentInst.aspx",
    "https://www.manabadi.co.in/institute/ViewDocRecruitments.aspx",
]

def get_all_sources():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    sources = []
    seen_ids = set()
    for master_url in MASTER_PAGES:
        try:
            res = requests.get(master_url, headers=headers, verify=False, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                name = link.text.strip()
                source_id = None
                if "sourceid=" in href:
                    source_id = href.split("sourceid=")[-1]
                elif "DocSourceId=" in href:
                    source_id = href.split("DocSourceId=")[-1]
                if name and source_id and source_id not in seen_ids:
                    seen_ids.add(source_id)
                    sources.append({
                        "name": name,
                        "id": source_id,
                        "url": f"https://www.manabadi.co.in/institute/DisplayDocsDetails.aspx?DocSourceId={source_id}"
                    })
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
    print(f"TOTAL SOURCES: {len(sources)}")
    return sources

def setup_db():
    conn = sqlite3.connect("news.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS updates
        (title TEXT PRIMARY KEY, saved_at TEXT)""")
    conn.commit()
    conn.close()

def check_daily_reset():
    today = datetime.now().date()
    if today != last_reset_date[0]:
        with daily_lock:
            send_telegram(
                f"📊 DAILY SUMMARY\n"
                f"Date: {last_reset_date[0]}\n\n"
                f"🆕 Total new updates: {daily_count[0]}\n"
                f"✅ System running 24/7"
            )
            daily_count[0] = 0
            last_reset_date[0] = today

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
        c.execute("INSERT OR IGNORE INTO updates(title, saved_at) VALUES(?,?)",
                  (title, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)

def send_to_api(source, title, url, category):
    def _send():
        try:
            requests.post(f"{API_URL}/updates/add", json={
                "university": source,
                "title": title,
                "url": url,
                "category": category
            }, timeout=30)
        except Exception as e:
            print(f"API Error: {e}")
    t = threading.Thread(target=_send)
    t.daemon = True
    t.start()

def detect_category(title):
    t = title.lower()
    if any(x in t for x in ["result", "revaluation", "rv"]):
        return "Results"
    elif any(x in t for x in ["hall ticket", "admit card", "hallticket"]):
        return "Hall Tickets"
    elif any(x in t for x in ["time table", "timetable", "schedule"]):
        return "Time Tables"
    elif any(x in t for x in ["notification", "apply", "registration", "fee", "last date"]):
        return "Notifications"
    elif any(x in t for x in ["job", "recruitment", "vacancy", "appsc", "tspsc", "upsc", "rrb", "sbi"]):
        return "Recruitments"
    elif any(x in t for x in ["rank card", "score card", "merit"]):
        return "Rank Cards"
    elif any(x in t for x in ["neet", "jee", "eamcet", "eapcet", "icet", "ecet", "polycet", "gate"]):
        return "Entrance Exams"
    elif any(x in t for x in ["10th", "ssc", "inter", "intermediate"]):
        return "Boards"
    else:
        return "General"

def should_skip(title):
    skip_words = [
        "login", "advertise", "mock exam", "apply now",
        "write exam", "view all", "show more", "skip",
        "mobile app", "google play", "scholarships",
        "loans", "careers", "for teachers", "for institutes",
        "contact", "manabadi app", "coaching",
        "institute login", "student login", "online coaching",
        "question papers", "study material", "current affairs",
        "guess papers", "previous papers", "model papers",
        "scert", "ncert", "kaveri", "josh"
    ]
    t = title.lower()
    return any(x in t for x in skip_words) or len(title) < 15

def process_update(source_name, title, url):
    if should_skip(title):
        return
    if is_new(title):
        category = detect_category(title)
        send_to_api(source_name, title, url, category)
        send_telegram(
            f"🔔 NEW UPDATE\n\n"
            f"📂 {category}\n"
            f"🏫 {source_name}\n\n"
            f"📢 {title}\n\n"
            f"🔗 {url}"
        )
        save(title)
        with new_updates_lock:
            new_updates_found.append(source_name)
        with daily_lock:
            daily_count[0] += 1
        print(f"✅ [{category}][{source_name}] {title}")

def scrape_home_page():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get("https://www.manabadi.co.in",
                          headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.find_all("a", href=True):
            title = link.text.strip()
            href = link["href"]
            if "POPUP-Manabadi-Mobile-Alert" in href:
                try:
                    parsed = urlparse(href)
                    params = parse_qs(parsed.query)
                    if "DocUrl" in params:
                        real_url = unquote(params["DocUrl"][0])
                        process_update("General Updates", title, real_url)
                except:
                    pass
            else:
                if href.startswith("http"):
                    full_url = href
                else:
                    full_url = f"https://www.manabadi.co.in{href}"
                process_update("Manabadi Today", title, full_url)
        print("✅ Home page scraped")
    except Exception as e:
        print(f"Home page error: {e}")

def scrape_source(name, source_url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(source_url, headers=headers, verify=False, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.find_all("a", href=True):
            title = link.text.strip()
            href = link["href"]
            if href.startswith("http"):
                full_url = href
            else:
                full_url = f"https://www.manabadi.co.in{href}"
            process_update(name, title, full_url)
    except Exception as e:
        print(f"Error [{name}]: {e}")

def worker(queue, counter, counter_lock, total):
    while True:
        try:
            source = queue.get(timeout=3)
        except:
            break
        scrape_source(source["name"], source["url"])
        with counter_lock:
            counter[0] += 1
            if counter[0] % 25 == 0:
                print(f"Progress: [{counter[0]}/{total}]")
        queue.task_done()

def run_quick_check():
    print("Quick check: home page TODAY UPDATES...")
    scrape_home_page()

def run_full_check(sources):
    print(f"Full check: {len(sources)} sources...")
    queue = Queue()
    for source in sources:
        queue.put(source)
    counter = [0]
    counter_lock = threading.Lock()
    threads = []
    for _ in range(THREADS):
        t = threading.Thread(
            target=worker,
            args=(queue, counter, counter_lock, len(sources))
        )
        t.daemon = True
        t.start()
        threads.append(t)
    queue.join()

def main():
    setup_db()
    print("HydNews COMPLETE Scraper Starting...")

    sources = get_all_sources()
    if not sources:
        send_telegram("⚠️ Could not fetch sources")
        return

    send_telegram(
        f"✅ HydNews Started\n\n"
        f"📊 Total Sources: {len(sources)}\n\n"
        f"✅ Home TODAY UPDATES: every 5 min\n"
        f"✅ All {len(sources)} sources: every 30 min\n"
        f"📊 Daily summary: midnight\n\n"
        f"Coverage:\n"
        f"🏫 All AP/TS Universities\n"
        f"📋 All Boards\n"
        f"📝 All Entrance Exams\n"
        f"💼 All Recruitments\n"
        f"🌍 All India Universities"
    )

    cycle = 1
    full_check_counter = 0

    while True:
        print(f"\n=== Cycle {cycle} ===")
        start_time = time.time()
        new_updates_found.clear()

        check_daily_reset()
        run_quick_check()

        full_check_counter += 1
        if full_check_counter >= 6:
            run_full_check(sources)
            full_check_counter = 0
            sources = get_all_sources()

        elapsed = int(time.time() - start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        total_new = len(new_updates_found)

        if total_new > 0:
            send_telegram(
                f"✅ Cycle {cycle}\n"
                f"🆕 New: {total_new}\n"
                f"📊 Today: {daily_count[0]}\n"
                f"⏱ {minutes}m {seconds}s"
            )

        # Process news every 5 minutes

import anthropic

import os
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
NEWS_API = "https://hydnews-api-production.up.railway.app"

def scrape_careers360_news():
    try:
        from bs4 import BeautifulSoup
        res = requests.get("https://news.careers360.com/latest", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        articles = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/") and len(href) > 10 and href.count("/") == 1:
                full_url = "https://news.careers360.com" + href
                title = a.get_text(strip=True)
                if len(title) > 20 and full_url not in seen:
                    seen.add(full_url)
                    articles.append({"url": full_url, "title": title})
        return articles[:10]
    except Exception as e:
        print("News scrape error:", e)
        return []

def fetch_article_content(url):
    try:
        from bs4 import BeautifulSoup
        res = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script","style","nav","header","footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception as e:
        print("Fetch error:", e)
        return ""

def rewrite_with_claude(title, content):
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = f"""You are an education news writer for Vidyalo.in India.
Rewrite this article in your own words. Return ONLY this JSON, no other text:
{{
  "title_english": "SEO title in English",
  "title_telugu": "Title in Telugu",
  "title_hindi": "Title in Hindi",
  "content_english": "Full article 800 words English with FAQ",
  "content_telugu": "Article in Telugu 400 words",
  "content_hindi": "Article in Hindi 400 words",
  "category": "Results or Hall Tickets or Admissions or Entrance Exams or Recruitment or Education News",
  "slug": "url-slug-english"
}}

Title: {title}
Content: {content[:2000]}"""
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{{"role": "user", "content": prompt}}]
        )
        import json
        text = message.content[0].text.strip()
        if "" in text:
            text = text.split("")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print("Claude error:", e)
        return None

def process_news():
    print("Checking Careers360 news...")
    articles = scrape_careers360_news()
    try:
        check = requests.get(NEWS_API + "/news/all?limit=500", timeout=5)
        existing = [n["slug"] for n in check.json()]
    except:
        existing = []
    for article in articles:
        try:
            content = fetch_article_content(article["url"])
            if not content:
                continue
            result = rewrite_with_claude(article["title"], content)
            if not result:
                continue
            if result["slug"] in existing:
                continue
            result["source_url"] = article["url"]
            result["image_url"] = ""
            res = requests.post(NEWS_API + "/news/add", json=result, timeout=10)
            if res.status_code == 200:
                print(f"News added: {result['title_english'][:50]}")
                existing.append(result["slug"])
        except Exception as e:
            print("Error:", e)

        process_news()
        cycle += 1
        time.sleep(300)

if __name__ == "__main__":
    main()