"""Background-thread orchestration. Owns the entire Playwright session and only
ever communicates with the GUI by putting ScrapeEvent objects on a queue — it
never touches a Tk widget directly, so there is no cross-thread widget access."""
import logging
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Literal

import config
from scraper.browser_manager import (
    BrowserLaunchError,
    ChromeNotRunningError,
    PlaywrightSession,
    ProfileCopyError,
    copy_profile_snapshot,
    is_chrome_running,
)
from scraper.exporter import CsvExporter, ExportError
from scraper.facebook_scraper import FacebookCommentScraper, PostNotFoundError
from scraper.parser import dedupe_records, parse_employee

logger = logging.getLogger(__name__)

EventType = Literal["log", "progress", "stat", "status", "success", "error"]


@dataclass
class ScrapeEvent:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)


class ScrapeWorker:
    def __init__(self, post_url: str, event_queue: "queue.Queue[ScrapeEvent]"):
        self.post_url = post_url
        self.event_queue = event_queue

    def _emit(self, type_: EventType, **payload: Any) -> None:
        self.event_queue.put(ScrapeEvent(type=type_, payload=payload))

    def _log(self, message: str, level: str = "info") -> None:
        self._emit("log", message=message, level=level)

    def _progress(self, pct: int, action: str) -> None:
        self._emit("progress", pct=pct, action=action)

    def run(self) -> None:
        try:
            self._emit("status", state="running")
            self._run_scrape()
        except ChromeNotRunningError:
            logger.warning("Chrome process not detected via psutil")
            self._log("✗ ไม่พบ Chrome ที่กำลังทำงาน", level="error")
            self._emit("error", message=config.CHROME_NOT_RUNNING_MSG)
        except PostNotFoundError as exc:
            logger.error("Post navigation failed for %s: %s", self.post_url, exc)
            self._log("✗ ไม่พบโพสต์ Facebook ที่ระบุ", level="error")
            self._emit("error", message=config.POST_NOT_FOUND_MSG)
        except ProfileCopyError:
            logger.exception("Profile copy failed")
            self._log("✗ ไม่สามารถเข้าถึงโปรไฟล์ Chrome ได้", level="error")
            self._emit("error", message=config.PROFILE_COPY_FAILED_MSG)
        except BrowserLaunchError as exc:
            logger.error("Browser launch failed: %s", exc)
            self._log("✗ ไม่สามารถเปิด Chrome ได้", level="error")
            self._emit("error", message=config.BROWSER_LAUNCH_FAILED_MSG)
        except ExportError:
            logger.exception("CSV export failed")
            self._log("✗ บันทึกไฟล์ CSV ไม่สำเร็จ", level="error")
            self._emit("error", message=config.EXPORT_FAILED_MSG)
        except Exception as exc:  # noqa: BLE001 - top-level safety net by design
            logger.exception("Unhandled scrape error")
            self._log(f"✗ เกิดข้อผิดพลาด: {exc}", level="error")
            self._emit("error", message=f"เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ: {exc}")

    def _run_scrape(self) -> None:
        self._progress(0, "กำลังเชื่อมต่อ Browser...")
        if not is_chrome_running():
            raise ChromeNotRunningError()
        self._log("✓ ตรวจพบ Chrome กำลังทำงาน", level="success")

        profile_dir = copy_profile_snapshot()
        self._log("✓ เชื่อมต่อ Chrome สำเร็จ", level="success")

        with PlaywrightSession(profile_dir) as page:
            scraper = FacebookCommentScraper(
                page, progress_callback=self._on_expand_progress
            )

            self._progress(15, "กำลังค้นหาคอมเมนต์...")
            scraper.navigate_to_post(self.post_url)

            total = scraper.get_total_comment_count()
            if total is not None:
                self._log(f"✓ พบ {total} ความคิดเห็น", level="success")
                self._emit("stat", key="total", value=total)

            self._progress(43, "กำลังโหลดความคิดเห็นทั้งหมด...")
            scraper.expand_all_comments()
            self._log("✓ โหลดความคิดเห็นทั้งหมดแล้ว", level="success")

            self._progress(87, "กำลังดึงข้อมูลพนักงาน...")
            raw_comments = scraper.extract_raw_comments()

        total_comments = len(raw_comments)
        self._emit("stat", key="total", value=total_comments)

        parsed_records = []
        for comment in raw_comments:
            parsed = parse_employee(comment["raw_comment"])
            if parsed is None:
                continue
            employee_id, employee_name = parsed
            parsed_records.append(
                {
                    "facebook_name": comment["facebook_name"],
                    "employee_id": employee_id,
                    "employee_name": employee_name,
                    "raw_comment": comment["raw_comment"],
                    "comment_timestamp": comment["comment_timestamp"],
                }
            )

        valid_count = len(parsed_records)
        self._log(f"✓ ดึงข้อมูลสำเร็จ {valid_count} รายการ", level="success")
        self._emit("stat", key="valid", value=valid_count)

        deduped = dedupe_records(parsed_records)
        duplicate_count = valid_count - len(deduped)
        self._log(f"✓ ลบข้อมูลซ้ำ {duplicate_count} รายการ", level="success")
        self._emit("stat", key="duplicate", value=duplicate_count)

        if not deduped:
            self._log("⚠ ไม่พบข้อมูลพนักงานในความคิดเห็น", level="warning")

        self._progress(100, "กำลังสร้างไฟล์ CSV...")
        filepath = CsvExporter().export(deduped)
        self._log("✓ Export CSV สำเร็จ", level="success")
        self._emit("stat", key="exported", value=len(deduped))

        self._emit("success", filepath=str(filepath), count=len(deduped))

    def _on_expand_progress(self, comment_count: int) -> None:
        self._log(f"… กำลังโหลดความคิดเห็น ({comment_count} พบแล้ว)", level="info")


def start_worker(post_url: str, event_queue: "queue.Queue[ScrapeEvent]") -> threading.Thread:
    worker = ScrapeWorker(post_url=post_url, event_queue=event_queue)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    return thread
