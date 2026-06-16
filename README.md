# TOA Lucky Draw Collector

Collect employee data from Facebook Lucky Draw post comments — one pasted URL, one click, one CSV.

## For end users

1. Open Google Chrome and make sure you're logged into Facebook.
2. Run `TOA Lucky Draw Collector.exe` (inside the folder you were given — don't move just the .exe by itself, it needs the `ms-playwright` folder next to it).
3. Paste the Facebook post URL into the box.
4. Click **🚀 เริ่มดึงข้อมูลจาก Facebook**.
5. Wait for the progress to reach 100%. A CSV is saved automatically to:
   `Documents\TOA Lucky Draw Exports\facebook_comments_YYYYMMDD_HHMMSS.csv`
6. Use **📂 เปิดโฟลเดอร์** / **📄 เปิดไฟล์ CSV** to jump straight to the result, or **🔄 ดึงข้อมูลอีกครั้ง** to run again.

No CMD, no Python install, no debugging flags required.

### If something goes wrong

| Message | What it means | What to do |
|---|---|---|
| กรุณาเปิด Google Chrome และ Login Facebook ก่อนใช้งาน | Chrome isn't running | Open Chrome, log into Facebook, try again |
| ไม่พบหน้าต่าง Facebook Post / กรุณาเปิดโพสต์ที่ต้องการก่อน | The pasted URL isn't a reachable post, or the Facebook session has expired | Double-check the URL, make sure you're still logged in, try again |
| ไม่สามารถบันทึกไฟล์ได้ / กรุณาปิดไฟล์ CSV ที่เปิดอยู่ | A previous export CSV is open in Excel, blocking the write | Close the CSV file, click "ดึงข้อมูลอีกครั้ง" |

Logs for diagnosing issues are written to a `logs/` folder next to the .exe.

## How it works

The app extracts the **employee ID + name** from each comment using the pattern `\b\d{8}\b` (any 8 consecutive digits), e.g. `"11212155 สมชาย ใจดี"` → ID `11212155`, name `สมชาย ใจดี`. Comments without an 8-digit ID (e.g. `"ร่วมกิจกรรมครับ"`) are skipped. Duplicate employee IDs are removed, keeping the first comment seen for each ID.

It does **not** read the Facebook tab you already have open — Chrome doesn't expose that without enabling remote debugging first, which this app deliberately avoids. Instead it copies your Chrome profile (cookies/login only, not your live browser) into a temporary folder and drives a hidden, separate Chromium instance against that copy, so it reuses your Facebook login without touching the Chrome window you're using.

## For developers

### Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Run from source

```bash
python main.py
```

Set `HEADLESS = False` in `config.py` to watch the automation browser while debugging selector issues.

### Tests

```bash
pytest tests/
```

`tests/test_parser.py` covers the employee-ID regex and dedupe logic against the spec's literal examples — this is the most correctness-critical, cheaply-testable part of the app, independent of any Facebook/Playwright flakiness.

### Building the distributable

Playwright ships as a Python package but its actual ~200MB Chromium **browser binary** is downloaded separately and isn't something PyInstaller can cleanly embed into a single-file exe. This project therefore builds in **onedir** mode (a folder, not one .exe) and ships the browser binary as a sibling folder:

```bash
pyinstaller build.spec
```

This produces `dist\TOA Lucky Draw Collector\TOA Lucky Draw Collector.exe`. Then copy the Chromium binary the build machine already downloaded via `playwright install chromium` into the dist folder:

```bash
# Find your local Chromium folder, typically:
#   %LOCALAPPDATA%\ms-playwright\chromium-<version>
# Copy it into:
xcopy /E /I "%LOCALAPPDATA%\ms-playwright" "dist\TOA Lucky Draw Collector\ms-playwright"
```

Zip the entire `dist\TOA Lucky Draw Collector\` folder and distribute that — not just the .exe. The app reads `PLAYWRIGHT_BROWSERS_PATH` from that sibling `ms-playwright` folder at startup (see `main.py` / `paths.py`), so end users never run `playwright install` themselves.

**Alternative (true onefile)**: if you'd rather ship a literal single .exe matching `pyinstaller --onefile --windowed --icon=assets/icon.ico main.py`, you can — but then IT must run `playwright install chromium` once on each end-user machine before first use, since the binary won't be bundled. That breaks the "zero setup" goal unless IT support is reliably available, which is why onedir is the default here.

### Project layout

```
main.py                # entry point — logging, PLAYWRIGHT_BROWSERS_PATH, launches the GUI
paths.py                # frozen-vs-source path resolution
config.py               # constants: colors, regex, timing, default dirs
ui/
  app.py                 # root window, thread-safe queue polling, event dispatch
  dashboard.py            # builds every section of the dashboard layout
  widgets.py               # StatusBadge, StatCard, ProgressRing, ActivityLogBox
  animations.py             # gradient image gen, hover-scale, best-effort confetti/sound
scraper/
  browser_manager.py       # Chrome detection, profile copy, Playwright session
  facebook_scraper.py       # navigation, expand/scroll-until-exhausted, raw extraction
  parser.py                  # employee ID/name regex parsing + first-wins dedupe
  exporter.py                 # UTF-8-SIG CSV export
  worker.py                    # background thread orchestration, emits events to a queue
tests/test_parser.py            # unit tests for the regex/dedupe logic
assets/                          # logo, icon, confetti gif, success sound (placeholders — swap freely)
```

### Known limitations (accepted, not bugs)

- Facebook's DOM/ARIA structure can change at any time; this is an unofficial scraper with no API guarantee. Selector logic lives in one place (`facebook_scraper.py`) for fast patching.
- If the copied session is stale (expired cookie, security checkpoint), the app reports "post not found" rather than a distinct message — there's no way to solve a 2FA/checkpoint prompt headlessly, so the user just needs to refresh their Chrome login.
- The scroll/expand loop uses a fixed wait + round-count heuristic, not a true "comments fully loaded" signal (Facebook has no such signal exposed). The round delay and ceiling are tunable constants in `config.py` — validate against a real large-comment-count post if 5,000-comment runs prove too slow or stop too early.
- No Selenium fallback is implemented — Playwright only. If Playwright ever becomes unavailable as a dependency, a Selenium-based `browser_manager`/`facebook_scraper` pair would need to be written from scratch following the same module shape.
