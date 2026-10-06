from datetime import datetime
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

# ---------------------------------------------------------
# Environment Parsers & Configuration
# ---------------------------------------------------------
def parse_range(var_name: str, default_min: float, default_max: float):
    raw_val = os.getenv(var_name, "").strip()
    if not raw_val:
        return default_min, default_max
    try:
        parts = [p.strip() for p in raw_val.split(",") if p.strip()]
        if len(parts) >= 2:
            return float(parts[0]), float(parts[1])
        elif len(parts) == 1:
            val = float(parts[0])
            return val, val
    except ValueError:
        print(f"[WARN] Invalid range in '{var_name}' ('{raw_val}'). Using defaults ({default_min}, {default_max}).")
    return default_min, default_max


def parse_list(var_name: str, defaults: list):
    raw_val = os.getenv(var_name, "").strip()
    if not raw_val:
        return defaults
    items = [item.strip() for item in raw_val.split(",") if item.strip()]
    return items if items else defaults


RAW_KEYS = os.getenv("SCRAPINGANT_API_KEYS", "Key1:6f88bd467966492d932576583925b36f")[cite: 2]
WORKER_MIN, WORKER_MAX = parse_range("WORKER_COUNT_RANGE", 3, 5)
GAP_MIN, GAP_MAX = parse_range("WORKER_GAP_RANGE", 8.0, 14.0)
CYCLE_MIN, CYCLE_MAX = parse_range("CYCLE_INTERVAL_RANGE", 50.0, 70.0)

BROWSER_RENDERING = os.getenv("BROWSER_RENDERING", "true").strip().lower()

# Pure authentic external referrers (no internal self-referral domains)
DEFAULT_REFERRERS = [
    "https://t.co/",
    "https://x.com/",
    "https://l.facebook.com/",
    "https://www.facebook.com/",
    "https://l.instagram.com/",
    "https://www.instagram.com/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://www.reddit.com/",
    "https://web.telegram.org/",
    "https://discord.com/",
    "https://www.youtube.com/"
]
REFERRERS = parse_list("REFERRERS", DEFAULT_REFERRERS)

# Target links pool using direct path format (/)
DEFAULT_LINKS = [
    "https://app.bullpen.fi/jack",
    "https://app.bullpen.fi/6DNUvqf",
    "https://app.bullpen.fi/652HU1t",
    "https://app.bullpen.fi/tzlMgCf",
    "https://app.bullpen.fi/fNPZlqT",
    "https://app.bullpen.fi/bTi9oJs",
    "https://app.bullpen.fi/QMOvAAL",
    "https://app.bullpen.fi/OVMrJe2",
    "https://app.bullpen.fi/VQH8P3L",
    "https://app.bullpen.fi/xDVN1Bq",
    "https://app.bullpen.fi/CLfcNh1"
]
TARGET_LINKS = parse_list("LINKS", DEFAULT_LINKS)

# High-reputation proxies sorted from highest Cloudflare trust down
HIGH_TRUST_COUNTRIES = [
    ("US", "us"),
    ("DE", "de"),
    ("GB", "gb"),
    ("FR", "fr"),
    ("NL", "nl"),
    ("CA", "ca"),
    ("SE", "se")
]


# ---------------------------------------------------------
# Key Structure & Manager
# ---------------------------------------------------------
class ManagedKey:
    def __init__(self, name: str, token: str):
        self.name = name.strip()[cite: 2]
        self.token = token.strip()[cite: 2]
        if len(self.token) >= 8:[cite: 2]
            self.masked = f"{self.token[:4]}...{self.token[-4:]}"[cite: 2]
        else:
            self.masked = self.token[cite: 2]
        self.tag = f"{self.name} [{self.masked}]"[cite: 2]


class KeyPoolManager:
    def __init__(self, raw_str: str):
        self.active_keys = [][cite: 2]
        self.dead_keys = [][cite: 2]
        self.index = 0[cite: 2]

        entries = [k.strip() for k in raw_str.split(",") if k.strip()][cite: 2]
        for idx, entry in enumerate(entries, start=1):[cite: 2]
            if ":" in entry:[cite: 2]
                name, token = entry.split(":", 1)[cite: 2]
                self.active_keys.append(ManagedKey(name, token))[cite: 2]
            else:
                self.active_keys.append(ManagedKey(f"Key#{idx}", entry))[cite: 2]

    def get_key(self) -> ManagedKey:
        if not self.active_keys:[cite: 2]
            return None[cite: 2]
        key = self.active_keys[self.index % len(self.active_keys)][cite: 2]
        self.index = (self.index + 1) % len(self.active_keys)[cite: 2]
        return key[cite: 2]

    def mark_dead(self, key_obj: ManagedKey, reason: str):
        if key_obj in self.active_keys:[cite: 2]
            self.active_keys.remove(key_obj)[cite: 2]
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")[cite: 2]
            self.dead_keys.append((key_obj, reason, ts))[cite: 2]

            print("\n" + "#" * 70)[cite: 2]
            print(" [PINNED ALERT] API KEY DIED / EXHAUSTED CREDITS")[cite: 2]
            print(f"  Key Identifier : {key_obj.tag}")[cite: 2]
            print(f"  Death Time     : {ts}")[cite: 2]
            print(f"  Confirmed Cause: {reason}")[cite: 2]
            print(f"  Active Remaining: {len(self.active_keys)} key(s)")[cite: 2]
            print("#" * 70 + "\n")[cite: 2]

    def print_pinned_status(self):
        if not self.dead_keys:[cite: 2]
            return[cite: 2]
        print("-" * 70)[cite: 2]
        print(" [PINNED AUDIT] PERMANENTLY DEAD KEYS:")[cite: 2]
        for k_obj, reason, ts in self.dead_keys:[cite: 2]
            print(f"  -> {k_obj.tag} | Died: {ts} | Reason: {reason}")[cite: 2]
        print("-" * 70)[cite: 2]


pool = KeyPoolManager(RAW_KEYS)[cite: 2]


def generate_cycle_links(worker_count: int, link_pool: list):
    count = min(worker_count, len(link_pool))
    return random.sample(link_pool, count)


def pick_country():
    return random.choice(HIGH_TRUST_COUNTRIES)


# ---------------------------------------------------------
# Worker Bot Task
# ---------------------------------------------------------
def execute_bot(bot_id: int, total_bots: int, target_url: str):
    key_obj = pool.get_key()[cite: 2]
    if not key_obj:[cite: 2]
        return[cite: 2]

    label, code = pick_country()
    params = {
        "x-api-key": key_obj.token,[cite: 2]
        "url": target_url,[cite: 2]
        "browser": BROWSER_RENDERING,
        "proxy_country": code,[cite: 2]
        # Executes wait inside browser instance to complete anti-bot checks
        "js_snippet": "await new Promise(r => setTimeout(r, 4500));"
    }

    url = f"https://api.scrapingant.com/v2/general?{urllib.parse.urlencode(params)}"[cite: 2]
    chosen_referrer = random.choice(REFERRERS)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Ant-Referer": chosen_referrer,
        "Ant-Referrer": chosen_referrer
    }

    req = urllib.request.Request(url, headers=headers)[cite: 2]

    try:
        with urllib.request.urlopen(req, timeout=85) as resp:
            print(f"[Bot-{bot_id}/{total_bots}] [{label}] [Target: {target_url}] [Ref: {chosen_referrer}] [{key_obj.tag}] -> HTTP {resp.status} OK")

    except urllib.error.HTTPError as e:[cite: 2]
        raw_detail = e.read().decode("utf-8", errors="ignore")[:75].strip()[cite: 2]

        if e.code in (401, 403):[cite: 2]
            reason_msg = f"HTTP {e.code} Credits Exhausted / Invalid Token ({raw_detail})"[cite: 2]
            pool.mark_dead(key_obj, reason_msg)[cite: 2]
        elif e.code == 409:[cite: 2]
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 409 Concurrency: {raw_detail}")[cite: 2]
        elif e.code == 404:[cite: 2]
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 404 Route unreachable: {raw_detail}")[cite: 2]
        elif e.code == 423:[cite: 2]
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 423 Anti-bot challenge: {raw_detail}")[cite: 2]
        else:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [WARNING] HTTP {e.code}: {raw_detail}")[cite: 2]

    except Exception as ex:[cite: 2]
        print(f"[Bot-{bot_id}] [{key_obj.tag}] [CLIENT ERROR]: {str(ex)}")[cite: 2]

    # Staggered sequential delay prevents ScrapingAnt 409 concurrency spikes
    gap = random.uniform(GAP_MIN, GAP_MAX)
    time.sleep(gap)


# ---------------------------------------------------------
# Engine Main Loop
# ---------------------------------------------------------
def main():
    print("==================================================")[cite: 2]
    print("      SCRAPING ENGINE INITIALIZED (OPTIMIZED)     ")
    print("==================================================")[cite: 2]
    print(f"Total Active Keys    : {len(pool.active_keys)}")[cite: 2]
    print(f"Browser Rendering    : {BROWSER_RENDERING}")
    print(f"Active Referrers     : {len(REFERRERS)}")
    print(f"Active Links Pool    : {len(TARGET_LINKS)}")
    print(f"Workers Per Cycle    : {int(WORKER_MIN)} - {int(WORKER_MAX)}")[cite: 2]
    print(f"Worker Gap Range     : {GAP_MIN:.1f}s - {GAP_MAX:.1f}s")[cite: 2]
    print(f"Cycle Duration Range : {CYCLE_MIN:.1f}s - {CYCLE_MAX:.1f}s")[cite: 2]
    print("==================================================\n")[cite: 2]

    cycle_num = 1[cite: 2]

    try:
        while True:[cite: 2]
            current_links = parse_list("LINKS", DEFAULT_LINKS)

            if not current_links:
                print("----------------------------------------------------------------------")
                print(" [IDLE WAITING] No links detected. Set LINKS=url1,url2 in Railway.")
                print(" Re-checking in 20 seconds...")
                print("----------------------------------------------------------------------\n")
                time.sleep(20)
                continue

            if not pool.active_keys:[cite: 2]
                print("\n" + "!" * 70)[cite: 2]
                print(" [SHUTDOWN] ALL CONFIGURED KEYS ARE COMPLETELY DEAD / EXHAUSTED.")[cite: 2]
                pool.print_pinned_status()[cite: 2]
                print("!" * 70 + "\n")[cite: 2]
                sys.exit(0)[cite: 2]

            cycle_start = time.time()[cite: 2]
            worker