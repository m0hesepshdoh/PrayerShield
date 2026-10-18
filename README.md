# PrayerShield – Internet Cut During Salah/Prayer

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)](https://github.com/YOUR_GITHUB_USERNAME/PrayerShield)
[![Huawei LTE API](https://img.shields.io/badge/powered%20by-huawei--lte--api-blue.svg)](https://github.com/Salamek/huawei-lte-api)

PrayerShield is a small Python daemon that automatically cuts and restores your Huawei LTE router’s mobile data around the five daily prayers (plus Jumu'ah on Fridays). It uses the AlAdhan Prayer Times API to fetch daily timings and the excellent [`huawei-lte-api`](https://github.com/Salamek/huawei-lte-api) library to talk to the router, created by mohammed yousef bafuleh.

---

## Features

- Fetches daily prayer times from the AlAdhan API using your city and country.  
- Handles Fajr, Dhuhr, Asr, Maghrib, and Isha with configurable “off” durations per prayer.  
- Treats Friday Dhuhr as **Jumu'ah** with a separate configurable duration.  
- Talks directly to a Huawei LTE router to toggle mobile data on/off via `huawei-lte-api`.  
- Verifies internet connectivity via ping (multiple DNS IPs) before/after cutting/restoring.  
- Syncs its internal clock with the router’s LTE time (via NTP API) and falls back to system time if needed.  
- Persists the last known prayer times to `prayer_times.json` and uses that as a cache on API failure.  
- Graceful shutdown: tries to restore internet before exiting and catches common signals.  
- Logs everything to `prayer_shield.log` and also to stdout.  

---

## How it works

1. On startup, PrayerShield waits a bit for the router/LTE to sync, then aligns its clock with the router’s reported time.  
2. It enables mobile data to ensure the internet is up and fetches the day’s prayer times from AlAdhan by city/country.  
3. It continuously checks the current time against prayer windows:  
   - During an active prayer window, it ensures mobile data is OFF (and actually cuts it if pings still work).  
   - Between prayers, it ensures mobile data is ON and restores it if it was previously cut.  
4. It sleeps intelligently until just before the next prayer, then repeats the logic.  

Timings are calculated locally from the fetched `HH:MM` strings, and each prayer has a configurable “window” length in minutes. Jumu'ah is handled as a special Dhuhr case on Fridays with a different duration.  

---

## Requirements

- Python 3.9+ (recommended).  
- A supported Huawei LTE router reachable at `http://192.168.8.1/` (or your own URL).  
- Valid admin credentials for the router (embedded in the URL in this script’s default config).  
- Ability to run `ping` from the host machine (Linux/macOS are ideal). The script uses `ping -c 1 -W 3`.  

Python packages (installable via `pip`):

- `huawei-lte-api` – control the Huawei LTE router (toggle data, read NTP time, etc.).  
- `requests` – for HTTP calls to the AlAdhan API.  

Plus standard library modules: `time`, `json`, `os`, `subprocess`, `logging`, `signal`, `sys`, `datetime`, `threading`.  

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/YOUR_GITHUB_USERNAME/PrayerShield.git
   cd PrayerShield
   ```

2. Create and activate a virtual environment (recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   Or, if you do not use `requirements.txt`:

   ```bash
   pip install huawei-lte-api requests
   ```

---

## Configuration

Configuration lives at the top of `script.py` (or your main script).

```python
ROUTER_URL = 'http://YourAdminHere:YourPasswordHere@192.168.8.1/'
CITY = "Jeddah"
COUNTRY = "Saudi Arabia"
DATA_FILE = "prayer_times.json"
OFF_DURATIONS = {"Fajr": 35, "Dhuhr": 30, "Asr": 30, "Maghrib": 20, "Isha": 30}
JUMUAH_DURATION = 40
```

Key fields:

- **ROUTER_URL**: Your router base URL including username and password as `http://user:password@router-ip/`.  
- **CITY** and **COUNTRY**: Passed to `https://api.aladhan.com/v1/timingsByCity` for prayer times.  
- **DATA_FILE**: Local JSON cache of last successfully fetched prayer times.  
- **OFF_DURATIONS**: Minutes the internet stays OFF for each prayer window.  
- **JUMUAH_DURATION**: Special duration for Jumu'ah (Friday Dhuhr).  

Adjust these values to match your location, router, and preferred window lengths.  

---

## Usage

Run PrayerShield directly:

```bash
python script.py
```

It will:

- Wait for LTE time sync and align its internal clock.  
- Keep the internet ON between prayers and OFF during configured prayer windows.  

For long‑running usage on Linux you can:

- Use `screen` or `tmux`, or  
- Add a simple systemd service (example):  

```ini
[Unit]
Description=PrayerShield – LTE Internet Cut During Salah
After=network-online.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/your/project
ExecStart=/path/to/venv/bin/python script.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Logging

By default, PrayerShield logs to:

- `prayer_shield.log` (file)  
- Standard output (console)  

Log format includes timestamp, level, and message.  

---

## Safety notes

- This script controls your router’s mobile data; misconfiguration may leave you without internet during unexpected times.  
- Make sure your `ROUTER_URL` and credentials are correct and **never** commit real passwords to a public repo.  
- You may want to restrict access to the machine running this tool and protect logs if they contain sensitive details.  

---

## Roadmap

- Optional web dashboard for status and overrides.  
- Support for additional prayer time sources.  
- Configurable grace period before and after each prayer.  

(Feel free to open issues or pull requests with feature suggestions.)

---

## Contributing

Contributions, issues, and feature requests are welcome.  
If you plan a larger change, please open an issue first to discuss what you would like to change.

Steps:

1. Fork the repository.  
2. Create your feature branch (`git checkout -b feature/awesome-feature`).  
3. Commit your changes (`git commit -m 'Add awesome feature'`).  
4. Push to the branch (`git push origin feature/awesome-feature`).  
5. Open a Pull Request.  

---

## License

This project is licensed under the MIT License – see the [`LICENSE`](LICENSE) file for details.  

---

## Credits

- **Huawei LTE API** – Python library used to communicate with the router:  
  - Repository: https://github.com/Salamek/huawei-lte-api  
- **AlAdhan Prayer Times API** – used to fetch daily prayer times:  
  - Docs / API: https://aladhan.com/prayer-times-api
