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


# ScrapingAnt Credentials & Engine Parameters
RAW_KEYS = os.getenv("SCRAPINGANT_API_KEYS", "Key1:6f88bd467966492d932576583925b36f")
WORKER_MIN, WORKER_MAX = parse_range("WORKER_COUNT_RANGE", 3, 5)
GAP_MIN, GAP_MAX = parse_range("WORKER_GAP_RANGE", 6.0, 12.0)
CYCLE_MIN, CYCLE_MAX = parse_range("CYCLE_INTERVAL_RANGE", 45.0, 60.0)

# Browser Rendering Toggle (Defaults to "true")
BROWSER_RENDERING = os.getenv("BROWSER_RENDERING", "true").strip().lower()

# Default Referrers
DEFAULT_REFERRERS = [
    "https://app.bullpen.fi/",
    "https://www.google.com/",
    "https://www.facebook.com/",
    "https://t.co/",
    "https://x.com/",
    "https://www.reddit.com/",
    "https://web.telegram.org/",
    "https://discord.com/",
    "https://www.youtube.com/"
]
REFERRERS = parse_list("REFERRERS", DEFAULT_REFERRERS)

# Default Links Pool
DEFAULT_LINKS = [
    "https://app.bullpen.fi?via=jack",
    "https://app.bullpen.fi?via=6DNUvqf",
    "https://app.bullpen.fi?via=652HU1t",
    "https://app.bullpen.fi?via=tzlMgCf",
    "https://app.bullpen.fi?via=fNPZlqT",
    "https://app.bullpen.fi?via=bTi9oJs",
    "https://app.bullpen.fi?via=QMOvAAL",
    "https://app.bullpen.fi?via=OVMrJe2",
    "https://app.bullpen.fi?via=VQH8P3L",
    "https://app.bullpen.fi?via=xDVN1Bq",
    "https://app.bullpen.fi?via=CLfcNh1"
]
TARGET_LINKS = parse_list("LINKS", DEFAULT_LINKS)

# Geographic Tiers
TIER_1 = [
    ("FR", "fr"), ("DE", "de"), ("NL", "nl"), ("ES", "es"),
    ("IT", "it"), ("PL", "pl"), ("SE", "se"), ("BR", "br"),
    ("KR", "kr"), ("TR", "tr"), ("VN", "vn"), ("ID", "id"),
    ("CA", "ca"), ("JP", "jp"), ("SG", "sg")
]
TIER_2 = [
    ("US", "us"), ("GB", "gb"), ("CZ", "cz"), ("RO", "ro"),
    ("AE", "ae"), ("MX", "mx"), ("TH", "th"), ("PH", "ph")
]
TIER_3 = [
    ("IN", "in"), ("SA", "sa"), ("HK", "hk"), ("TW", "tw")
]


# ---------------------------------------------------------
# Key Structure & Manager
# ---------------------------------------------------------
class ManagedKey:
    def __init__(self, name: str, token: str):
        self.name = name.strip()
        self.token = token.strip()
        if len(self.token) >= 8:
            self.masked = f"{self.token[:4]}...{self.token[-4:]}"
        else:
            self.masked = self.token
        self.tag = f"{self.name} [{self.masked}]"


class KeyPoolManager:
    def __init__(self, raw_str: str):
        self.active_keys = []
        self.dead_keys = []
        self.index = 0

        entries = [k.strip() for k in raw_str.split(",") if k.strip()]
        for idx, entry in enumerate(entries, start=1):
            if ":" in entry:
                name, token = entry.split(":", 1)
                self.active_keys.append(ManagedKey(name, token))
            else:
                self.active_keys.append(ManagedKey(f"Key#{idx}", entry))

    def get_key(self) -> ManagedKey:
        if not self.active_keys:
            return None
        key = self.active_keys[self.index % len(self.active_keys)]
        self.index = (self.index + 1) % len(self.active_keys)
        return key

    def mark_dead(self, key_obj: ManagedKey, reason: str):
        if key_obj in self.active_keys:
            self.active_keys.remove(key_obj)
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            self.dead_keys.append((key_obj, reason, ts))

            print("\n" + "#" * 70)
            print(f" [PINNED ALERT] API KEY DIED / EXHAUSTED CREDITS")
            print(f"  Key Identifier : {key_obj.tag}")
            print(f"  Death Time     : {ts}")
            print(f"  Confirmed Cause: {reason}")
            print(f"  Active Remaining: {len(self.active_keys)} key(s)")
            print("#" * 70 + "\n")

    def print_pinned_status(self):
        if not self.dead_keys:
            return
        print("-" * 70)
        print(" [PINNED AUDIT] PERMANENTLY DEAD KEYS:")
        for k_obj, reason, ts in self.dead_keys:
            print(f"  -> {k_obj.tag} | Died: {ts} | Reason: {reason}")
        print("-" * 70)


pool = KeyPoolManager(RAW_KEYS)


# ---------------------------------------------------------
# Dynamic Links Picker (No Duplicates Per Cycle)
# ---------------------------------------------------------
def generate_cycle_links(worker_count: int):
    count = min(worker_count, len(TARGET_LINKS))
    return random.sample(TARGET_LINKS, count)


def pick_country():
    roll = random.random()
    if roll < 0.50:
        return "T1", *random.choice(TIER_1)
    elif roll < 0.85:
        return "T2", *random.choice(TIER_2)
    else:
        return "T3", *random.choice(TIER_3)


# ---------------------------------------------------------
# Worker Bot Task
# ---------------------------------------------------------
def execute_bot(bot_id: int, total_bots: int, target_url: str):
    key_obj = pool.get_key()
    if not key_obj:
        return

    tier, label, code = pick_country()
    params = {
        "x-api-key": key_obj.token,
        "url": target_url,
        "browser": BROWSER_RENDERING,
        "proxy_country": code,
        "proxy_type": "residential"
    }

    url = f"https://api.scrapingant.com/v2/general?{urllib.parse.urlencode(params)}"
    chosen_referrer = random.choice(REFERRERS)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Ant-Referer": chosen_referrer
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=75) as resp:
            print(f"[Bot-{bot_id}/{total_bots}] [{tier}-{label}] [Target: {target_url}] [Ref: {chosen_referrer}] [{key_obj.tag}] -> HTTP {resp.status} OK")

    except urllib.error.HTTPError as e:
        raw_detail = e.read().decode("utf-8", errors="ignore")[:75].strip()

        if e.code in (401, 403):
            reason_msg = f"HTTP {e.code} Credits Exhausted / Invalid Token ({raw_detail})"
            pool.mark_dead(key_obj, reason_msg)
        elif e.code == 409:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 409 Concurrency: {raw_detail}")
        elif e.code == 404:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 404 Route unreachable: {raw_detail}")
        elif e.code == 423:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 423 Anti-bot challenge: {raw_detail}")
        else:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [WARNING] HTTP {e.code}: {raw_detail}")

    except Exception as ex:
        print(f"[Bot-{bot_id}] [{key_obj.tag}] [CLIENT ERROR]: {str(ex)}")

    gap = random.uniform(GAP_MIN, GAP_MAX)
    time.sleep(gap)


# ---------------------------------------------------------
# Engine Main Loop
# ---------------------------------------------------------
def main():
    print("==================================================")
    print("      SCRAPING ENGINE INITIALIZED (RAILWAY/RENDER) ")
    print("==================================================")
    print(f"Total Active Keys    : {len(pool.active_keys)}")
    print(f"Browser Rendering    : {BROWSER_RENDERING}")
    print(f"Configured Referrers : {len(REFERRERS)}")
    print(f"Configured Links     : {len(TARGET_LINKS)}")
    print(f"Workers Per Cycle    : {int(WORKER_MIN)} - {int(WORKER_MAX)}")
    print(f"Worker Gap Range     : {GAP_MIN:.1f}s - {GAP_MAX:.1f}s")
    print(f"Cycle Duration Range : {CYCLE_MIN:.1f}s - {CYCLE_MAX:.1f}s")
    print("==================================================\n")

    cycle_num = 1

    try:
        while True:
            if not pool.active_keys:
                print("\n" + "!" * 70)
                print(" [SHUTDOWN] ALL CONFIGURED KEYS ARE COMPLETELY DEAD / EXHAUSTED.")
                pool.print_pinned_status()
                print("!" * 70 + "\n")
                sys.exit(0)

            cycle_start = time.time()
            worker_count = random.randint(int(WORKER_MIN), int(WORKER_MAX))
            target_cycle_time = random.uniform(CYCLE_MIN, CYCLE_MAX)

            print(f"\n--- [Cycle #{cycle_num}] Starting {worker_count} bots | Target: {target_cycle_time:.1f}s | Active Keys: {len(pool.active_keys)} ---")

            cycle_links = generate_cycle_links(worker_count)

            for idx, target_url in enumerate(cycle_links, start=1):
                execute_bot(idx, len(cycle_links), target_url)

            elapsed = time.time() - cycle_start
            wait_time = target_cycle_time - elapsed

            pool.print_pinned_status()

            if wait_time > 0 and pool.active_keys:
                print(f"--- [Cycle #{cycle_num} Complete] Elapsed: {elapsed:.1f}s | Pausing {wait_time:.1f}s before next round ---")
                time.sleep(wait_time)
            elif pool.active_keys:
                print(f"--- [Cycle #{cycle_num} Complete] Elapsed: {elapsed:.1f}s | Starting next round immediately ---")

            cycle_num += 1

    except KeyboardInterrupt:
        print("\nTermination signal received. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()