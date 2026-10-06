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
RAW_KEYS = os.getenv("SCRAPINGANT_API_KEYS", "Key1:6f88bd467966492d932576583925b36f")[cite: 2]
WORKER_MIN, WORKER_MAX = parse_range("WORKER_COUNT_RANGE", 3, 5)
GAP_MIN, GAP_MAX = parse_range("WORKER_GAP_RANGE", 6.0, 12.0)
CYCLE_MIN, CYCLE_MAX = parse_range("CYCLE_INTERVAL_RANGE", 45.0, 60.0)

# Browser Rendering Toggle (Defaults to "true")
BROWSER_RENDERING = os.getenv("BROWSER_RENDERING", "true").strip().lower()

# Default Referrers (Authentic list)
DEFAULT_REFERRERS = [
    "https://app.bullpen.fi/",
    "https://bullpen.fi/",
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
# Configurable comma-separated links environment variable
TARGET_LINKS = parse_list("LINKS", DEFAULT_LINKS)

# Geographic Tiers
TIER_1 = [
    ("FR", "fr"), ("DE", "de"), ("NL", "nl"), ("ES", "es"),
    ("IT", "it"), ("PL", "pl"), ("SE", "se"), ("BR", "br"),
    ("KR", "kr"), ("TR", "tr"), ("VN", "vn"), ("ID", "id"),
    ("CA", "ca"), ("JP", "jp"), ("SG", "sg")
][cite: 2]
TIER_2 = [
    ("US", "us"), ("GB", "gb"), ("CZ", "cz"), ("RO", "ro"),
    ("AE", "ae"), ("MX", "mx"), ("TH", "th"), ("PH", "ph")
][cite: 2]
TIER_3 = [
    ("IN", "in"), ("SA", "sa"), ("HK", "hk"), ("TW", "tw")
][cite: 2]


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
            print(f" [PINNED ALERT] API KEY DIED / EXHAUSTED CREDITS")[cite: 2]
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


# ---------------------------------------------------------
# Dynamic Links Picker (No Duplicates Per Cycle)
# ---------------------------------------------------------
def generate_cycle_links(worker_count: int):
    # random.sample guarantees zero duplicate links within the same cycle
    count = min(worker_count, len(TARGET_LINKS))
    return random.sample(TARGET_LINKS, count)


def pick_country():
    roll = random.random()[cite: 2]
    if roll < 0.50:[cite: 2]
        return "T1", *random.choice(TIER_1)[cite: 2]
    elif roll < 0.85:[cite: 2]
        return "T2", *random.choice(TIER_2)[cite: 2]
    else:
        return "T3", *random.choice(TIER_3)[cite: 2]


# ---------------------------------------------------------
# Worker Bot Task
# ---------------------------------------------------------
def execute_bot(bot_id: int, total_bots: int, target_url: str):
    key_obj = pool.get_key()[cite: 2]
    if not key_obj:[cite: 2]
        return[cite: 2]

    tier, label, code = pick_country()[cite: 2]
    params = {
        "x-api-key": key_obj.token,[cite: 2]
        "url": target_url,[cite: 2]
        "browser": BROWSER_RENDERING,
        "proxy_country": code,[cite: 2]
        "proxy_type": "residential"
    }

    url = f"https://api.scrapingant.com/v2/general?{urllib.parse.urlencode(params)}"[cite: 2]
    
    # Pick a random referrer dynamically on every request
    chosen_referrer = random.choice(REFERRERS)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Ant-Referer": chosen_referrer
    }

    req = urllib.request.Request(url, headers=headers)[cite: 2]

    try:
        with urllib.request.urlopen(req, timeout=75) as resp:
            print(f"[Bot-{bot_id}/{total_bots}] [{tier}-{label}] [Target: {target_url}] [Ref: {chosen_referrer}] [{key_obj.tag}] -> HTTP {resp.status} OK")

    except urllib.error.HTTPError as e:[cite: 2]
        raw_detail = e.read().decode("utf-8", errors="ignore")[:75].strip()

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

    # Staggered spacing between requests to eliminate 409 concurrency spikes on 1 key
    gap = random.uniform(GAP_MIN, GAP_MAX)
    time.sleep(gap)


# ---------------------------------------------------------
# Engine Main Loop
# ---------------------------------------------------------
def main():
    print("==================================================")[cite: 2]
    print("      SCRAPING ENGINE INITIALIZED (RAILWAY/RENDER) ")[cite: 2]
    print("==================================================")[cite: 2]
    print(f"Total Active Keys    : {len(pool.active_keys)}")[cite: 2]
    print(f"Browser Rendering    : {BROWSER_RENDERING}")
    print(f"Configured Referrers : {len(REFERRERS)}")
    print(f"Configured Links     : {len(TARGET_LINKS)}")
    print(f"Workers Per Cycle    : {int(WORKER_MIN)} - {int(WORKER_MAX)}")[cite: 2]
    print(f"Worker Gap Range     : {GAP_MIN:.1f}s - {GAP_MAX:.1f}s")[cite: 2]
    print(f"Cycle Duration Range : {CYCLE_MIN:.1f}s - {CYCLE_MAX:.1f}s")[cite: 2]
    print("==================================================\n")[cite: 2]

    cycle_num = 1[cite: 2]

    try:
        while True:[cite: 2]
            if not pool.active_keys:[cite: 2]
                print("\n" + "!" * 70)[cite: 2]
                print(" [SHUTDOWN] ALL CONFIGURED KEYS ARE COMPLETELY DEAD / EXHAUSTED.")[cite: 2]
                pool.print_pinned_status()[cite: 2]
                print("!" * 70 + "\n")[cite: 2]
                sys.exit(0)[cite: 2]

            cycle_start = time.time()[cite: 2]
            worker_count = random.randint(int(WORKER_MIN), int(WORKER_MAX))[cite: 2]
            target_cycle_time = random.uniform(CYCLE_MIN, CYCLE_MAX)[cite: 2]

            print(f"\n--- [Cycle #{cycle_num}] Starting {worker_count} bots | Target: {target_cycle_time:.1f}s | Active Keys: {len(pool.active_keys)} ---")[cite: 2]

            # Fetches unique links with zero duplicates within this cycle
            cycle_links = generate_cycle_links(worker_count)

            # Sequential requests to adhere to free tier 1-request concurrency limit
            for idx, target_url in enumerate(cycle_links, start=1):
                execute_bot(idx, len(cycle_links), target_url)

            elapsed = time.time() - cycle_start[cite: 2]
            wait_time = target_cycle_time - elapsed[cite: 2]

            pool.print_pinned_status()[cite: 2]

            if wait_time > 0 and pool.active_keys:[cite: 2]
                print(f"--- [Cycle #{cycle_num} Complete] Elapsed: {elapsed:.1f}s | Pausing {wait_time:.1f}s before next round ---")[cite: 2]
                time.sleep(wait_time)[cite: 2]
            elif pool.active_keys:[cite: 2]
                print(f"--- [Cycle #{cycle_num} Complete] Elapsed: {elapsed:.1f}s | Starting next round immediately ---")[cite: 2]

            cycle_num += 1[cite: 2]

    except KeyboardInterrupt:[cite: 2]
        print("\nTermination signal received. Exiting.")[cite: 2]
        sys.exit(0)[cite: 2]


if __name__ == "__main__":[cite: 2]
    main()[cite: 2]