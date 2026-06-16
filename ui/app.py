"""Root application window. Owns the worker thread's event queue and is the
ONLY place that touches Tk widgets in response to worker output — the worker
thread only ever calls queue.put(), this class is the sole consumer via the
GUI-thread after()-driven poll loop."""
import logging
import os
import queue
import threading
import tkinter.messagebox as messagebox

import customtkinter as ctk

import config
from scraper.worker import ScrapeEvent, start_worker
from ui.animations import play_confetti, play_success_sound
from ui.dashboard import Dashboard

logger = logging.getLogger(__name__)

QUEUE_POLL_INTERVAL_MS = 100


class CollectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(config.APP_NAME)
        self.geometry(config.WINDOW_SIZE)
        self.resizable(False, False)
        self.configure(fg_color=config.COLOR_BG)

        self.event_queue: "queue.Queue[ScrapeEvent]" = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self._last_filepath: str | None = None

        self.dashboard = Dashboard(
            self,
            on_start=self.on_start_clicked,
            on_open_folder=self.on_open_folder,
            on_open_csv=self.on_open_csv,
            on_run_again=self.on_run_again,
        )

        self.after(QUEUE_POLL_INTERVAL_MS, self._poll_queue)

    # ---- User actions -----------------------------------------------------
    def on_start_clicked(self, post_url: str) -> None:
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return  # re-entrancy guard — a run is already in progress

        self.dashboard.main_button.configure(text="⏳ กำลังรวบรวมข้อมูล...", state="disabled")
        self.dashboard.status_badge.set_state("running")
        self.dashboard.set_result_visible(False)
        self.dashboard.set_progress_visible(True)
        self.dashboard.log_box.clear()

        self.worker_thread = start_worker(post_url, self.event_queue)

    def on_open_folder(self) -> None:
        if self._last_filepath:
            os.startfile(os.path.dirname(self._last_filepath))

    def on_open_csv(self) -> None:
        if self._last_filepath:
            os.startfile(self._last_filepath)

    def on_run_again(self) -> None:
        self.dashboard.reset()

    # ---- Queue polling (GUI thread only) -----------------------------------
    def _poll_queue(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.after(QUEUE_POLL_INTERVAL_MS, self._poll_queue)

    def _handle_event(self, event: ScrapeEvent) -> None:
        handler = getattr(self, f"_on_{event.type}", None)
        if handler is None:
            logger.warning("No handler for event type %s", event.type)
            return
        handler(event.payload)

    def _on_log(self, payload: dict) -> None:
        self.dashboard.log_box.append(payload["message"], level=payload.get("level", "info"))

    def _on_progress(self, payload: dict) -> None:
        self.dashboard.progress_ring.set_progress(payload["pct"])
        self.dashboard.action_label.configure(text=payload["action"])

    def _on_stat(self, payload: dict) -> None:
        card_map = {
            "total": self.dashboard.stat_card_total,
            "valid": self.dashboard.stat_card_valid,
            "duplicate": self.dashboard.stat_card_dupe,
            "exported": self.dashboard.stat_card_exported,
        }
        card = card_map.get(payload["key"])
        if card:
            card.animate_to(payload["value"])

    def _on_status(self, payload: dict) -> None:
        self.dashboard.status_badge.set_state(payload["state"])

    def _on_success(self, payload: dict) -> None:
        self._last_filepath = payload["filepath"]
        self.dashboard.status_badge.set_state("success")
        self.dashboard.set_progress_visible(False)

        filename = os.path.basename(payload["filepath"])
        self.dashboard.result_filename_label.configure(text=f"บันทึกข้อมูลแล้ว: {filename}")
        self.dashboard.result_count_label.configure(
            text=f"จำนวนข้อมูลทั้งหมด: {payload['count']} รายการ"
        )
        self.dashboard.set_result_visible(True)
        self.dashboard.main_button.configure(text="🚀 เริ่มดึงข้อมูลจาก Facebook", state="normal")

        play_success_sound()
        play_confetti(self.dashboard.result_filename_label)

    def _on_error(self, payload: dict) -> None:
        self.dashboard.status_badge.set_state("error")
        self.dashboard.set_progress_visible(False)
        self.dashboard.main_button.configure(text="🚀 เริ่มดึงข้อมูลจาก Facebook", state="normal")
        messagebox.showerror(config.APP_NAME, payload["message"])
