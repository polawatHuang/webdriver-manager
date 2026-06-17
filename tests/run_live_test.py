"""Quick live smoke-test: run from the project root with  python tests/run_live_test.py"""
import queue
import time
import sys

sys.path.insert(0, ".")
from scraper.worker import start_worker

URL = "https://www.facebook.com/groups/601770683277539/permalink/27130417069986206/"

q: queue.Queue = queue.Queue()
t = start_worker(URL, q)

start = time.time()
while t.is_alive() or not q.empty():
    try:
        ev = q.get(timeout=2)
        elapsed = time.time() - start
        if ev.type == "progress":
            pct = ev.payload["pct"]
            action = ev.payload["action"]
            print(f"[{elapsed:.1f}s] PROGRESS {pct}% | {action}")
        elif ev.type == "log":
            level = ev.payload["level"]
            msg = ev.payload["message"]
            print(f"[{elapsed:.1f}s] LOG [{level}] {msg}")
        elif ev.type in ("success", "error", "stat"):
            print(f"[{elapsed:.1f}s] {ev.type.upper()} {ev.payload}")
            if ev.type in ("success", "error"):
                break
    except queue.Empty:
        if not t.is_alive():
            break

total = time.time() - start
print(f"\nTotal time: {total:.1f}s")
