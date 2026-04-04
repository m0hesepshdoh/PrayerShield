import time
import json
import os
import subprocess
import requests
import logging
import signal
import sys
import threading
from datetime import datetime, timedelta
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection

# ── Config ────────────────────────────────────────────────────────────────────
# URL must include router credentials; see huawei-lte-api docs.
ROUTER_URL = 'http://admin:password@192.168.8.1/'
CITY = "Jeddah"              # City for AlAdhan 
COUNTRY = "Saudi Arabia"     # Country for AlAdhan

# Minutes the internet stays OFF for each prayer.
OFF_DURATIONS = {"Fajr": 35, "Dhuhr": 30, "Asr": 30, "Maghrib": 20, "Isha": 30}
# Special duration for Friday Jumu'ah
JUMUAH_DURATION = 40
DATA_FILE = "prayer_times.json"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('prayer_shield.log'),
        logging.StreamHandler()
    ]
)

# ── Main class ────────────────────────────────────────────────────────────────
class PrayerShield:

    def __init__(self):
        self.running = True
        self.prayer_data = None
        self.last_fetch_date = None
        self.time_offset = timedelta(0)
        signal.signal(signal.SIGINT,  self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def shutdown(self, signum, frame):
        logging.info("Shutdown signal received — restoring internet...")
        self.running = False
        for attempt in range(3):
            if self.set_mobile_data(True):
                break
            time.sleep(1)
        time.sleep(2)
        sys.exit(0)
        
    # ── Internet control ────────────────────────────────────────────────────────
    def restore_internet(self):
        """Restore internet and verify it's working."""
        if self.set_mobile_data(True):
        # Wait for router to apply changes
            time.sleep(5)
            # Verify internet is actually working
            if self.can_reach_internet():
                logging.info("Internet restored and verified")
            return True
        else:
            logging.warning("Internet turned on but not reachable yet")
        return False

    # ── Router time sync ──────────────────────────────────────────────────────
    # Read router NTP info to get LTE-synced time.
    def get_router_time(self):
        try:
            with Connection(ROUTER_URL) as conn:
                raw = Client(conn).s_ntp.timeinfo().get('currentlocaltime', '')
                dt = datetime.strptime(raw.replace('T', ' '), "%Y-%m-%d %H:%M:%S")
                return dt if dt.year >= 2024 else None
        except Exception as e:
            logging.error(f"Router time error: {e}")
            return None

    def wait_for_lte_sync(self, timeout=80, interval=10):
        logging.info("Waiting for LTE time sync...")
        deadline = time.time() + timeout
        while self.running and time.time() < deadline:
            t = self.get_router_time()
            if t:
                logging.info(f"LTE synced: {t}")
                return t
            logging.warning(f"Not synced yet — retrying in {interval}s")
            time.sleep(interval)
        logging.warning("LTE sync timeout — falling back to system time")
        return datetime.now()

    def sync_clock(self):
        rt = self.wait_for_lte_sync()
        self.time_offset = rt - datetime.now()
        logging.info(f"Clock offset: {self.time_offset}")

    def now(self):
        """Current time adjusted to match router/LTE clock."""
        return datetime.now() + self.time_offset

    # ── Router data toggle ────────────────────────────────────────────────────

    def set_mobile_data(self, enable: bool, retries=3) -> bool:
        for attempt in range(retries):
            try:
                with Connection(ROUTER_URL) as conn:
                    Client(conn).dial_up.set_mobile_dataswitch(
                        dataswitch=1 if enable else 0
                    )
                logging.info(f"Mobile data → {'ON' if enable else 'OFF'}")
                return True
            except Exception as e:
                if attempt == retries - 1:
                    logging.error(f"set_mobile_data failed after {retries} attempts: {e}")
                    return False
                wait = 2 ** attempt
                logging.warning(f"Attempt {attempt+1} failed, retrying in {wait}s...")
                time.sleep(wait)
        return False

    # ── Internet reachability via ping ────────────────────────────────────────

    def can_reach_internet(self) -> bool:
        """Ping multiple reliable DNS servers."""
        targets = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
        for target in targets:
                try:
                    result = subprocess.run(
                    ["ping", "-c", "1", "-W", "3", target],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5
                    )
                    if result.returncode == 0:
                        return True
                except Exception:
                    continue
        return False

    # ── Prayer times ──────────────────────────────────────────────────────────

    def get_prayer_times(self) -> dict | None:
        """Fetch today's prayer times from Aladhan API; fall back to cache."""
        try:
            url = (
                f"https://api.aladhan.com/v1/timingsByCity"
                f"?city={CITY}&country={COUNTRY}&method=4"
            )
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            timings = r.json()['data']['timings']
            prayers = {
                k: timings[k].split(' ')[0]
                for k in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
                if k in timings
            }
            with open(DATA_FILE, 'w') as f:
                json.dump(prayers, f)
            logging.info(f"Prayer times updated: {prayers}")
            return prayers

        except Exception as e:
            logging.error(f"API fetch failed: {e}")
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    cached = json.load(f)
                logging.info("Using cached prayer times")
                return cached
            logging.error("No cache available")
            return None
    
    def get_active_prayer(self, now: datetime) -> str | None:
        """Returns the name of the active prayer, handling Jumu'ah on Fridays."""
        if not self.prayer_data:
            return None
            
        is_friday = now.weekday() == 4 
        
        for name, t_str in self.prayer_data.items():
            p_dt = datetime.strptime(t_str, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            
            if is_friday and name == "Dhuhr":
                display_name = "Jumu'ah"
                duration = JUMUAH_DURATION
            else:
                display_name = name
                duration = OFF_DURATIONS.get(name, 25)
            
            if p_dt <= now <= p_dt + timedelta(minutes=duration):
                return display_name
        return None

    def get_next_prayer(self, now: datetime) -> tuple[str | None, datetime | None]:
        """
        Returns (name, datetime) of the next upcoming prayer.
        If all today's prayers have passed, wraps to tomorrow.
        """
        if not self.prayer_data:
            return None, None
        upcoming = []
        for name, t_str in self.prayer_data.items():
            p_dt = datetime.strptime(t_str, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            if p_dt <= now:
                p_dt += timedelta(days=1)
            upcoming.append((name, p_dt))
        upcoming.sort(key=lambda x: x[1])
        return upcoming[0] if upcoming else (None, None)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        logging.info("=== Prayer Shield started ===")
        time.sleep(80)
        self.sync_clock()
        self.set_mobile_data(True)
        internet_was_cut = False

        while self.running:
            try:
                now = self.now()

                # Refresh prayer times once per day
                if self.last_fetch_date != now.date() or not self.prayer_data:
                    self.prayer_data = self.get_prayer_times()
                    self.last_fetch_date = now.date()

                if not self.prayer_data:
                    logging.error("No prayer data available — retrying in 5 min")
                    time.sleep(300)
                    continue

                active = self.get_active_prayer(now)

                if active:
                    # ── Prayer window: internet must be OFF ──
                    if self.can_reach_internet():
                        # Ping succeeded → internet still ON → cut it
                        logging.info(
                            f"{active} prayer time — internet reachable, turning OFF"
                        )
                        self.set_mobile_data(False)
                        internet_was_cut = True
                    else:
                        if not internet_was_cut:
                            logging.info(
                                f"{active} prayer time — internet already OFF"
                            )
                            internet_was_cut = True
                    # Check every 60s during prayer window
                    time.sleep(60)

                else:
                    # ── Between prayers: internet must be ON ──
                    if internet_was_cut:
                        logging.info("Prayer window ended — restoring internet")
                        self.restore_internet()
                        internet_was_cut = False

                    # Sleep until 60 s before the next prayer
                    name, next_dt = self.get_next_prayer(now)
                    if next_dt:
                        sleep_secs = max(30, (next_dt - now).total_seconds() - 60)
                        logging.info(
                            f"Next prayer: {name} at "
                            f"{next_dt.strftime('%H:%M')} — "
                            f"sleeping {sleep_secs / 60:.1f} min"
                        )
                        time.sleep(sleep_secs)
                    else:
                        time.sleep(300)

            except Exception as e:
                logging.error(f"Main loop error: {e}", exc_info=True)
                time.sleep(60)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    shield = PrayerShield()
    try:
        shield.run()
    except KeyboardInterrupt:
        shield.shutdown(None, None)
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        try:
            shield.set_mobile_data(True)
        except Exception:
            pass
        sys.exit(1)