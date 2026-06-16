"""Builds the dashboard layout: header, hero/URL input, main button, progress,
stats, live log, and result sections — mapped 1:1 to the spec's screen layout."""
import customtkinter as ctk

import config
from ui.animations import bind_hover_scale
from ui.widgets import ActivityLogBox, ProgressRing, StatCard, StatusBadge


class Dashboard:
    def __init__(self, master: ctk.CTk, on_start, on_open_folder, on_open_csv, on_run_again):
        self.master = master
        self.on_start = on_start
        self.on_open_folder = on_open_folder
        self.on_open_csv = on_open_csv
        self.on_run_again = on_run_again

        self.root = ctk.CTkScrollableFrame(master, fg_color=config.COLOR_BG)
        self.root.pack(fill="both", expand=True, padx=16, pady=16)

        self._build_header()
        self._build_hero()
        self._build_main_button()
        self._build_progress_section()
        self._build_stats_section()
        self._build_log_section()
        self._build_result_section()

        self.set_progress_visible(False)
        self.set_result_visible(False)

    # ---- Header -----------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self.root, fg_color=config.COLOR_CARD, corner_radius=20,
            border_width=1, border_color=config.COLOR_CARD_BORDER,
        )
        header.pack(fill="x", pady=(0, 16))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=20, pady=16, fill="x", expand=True)

        title_row = ctk.CTkFrame(left, fg_color="transparent")
        title_row.pack(anchor="w")
        ctk.CTkLabel(title_row, text="🎁", font=("Segoe UI Emoji", 28)).pack(side="left", padx=(0, 10))
        text_col = ctk.CTkFrame(title_row, fg_color="transparent")
        text_col.pack(side="left")
        ctk.CTkLabel(
            text_col, text=config.APP_NAME, font=("Segoe UI", 22, "bold"),
            text_color=config.COLOR_TEXT_PRIMARY, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col, text="Collect Facebook Campaign Participants Automatically",
            font=("Segoe UI", 12), text_color=config.COLOR_TEXT_SECONDARY, anchor="w",
        ).pack(anchor="w")

        self.status_badge = StatusBadge(header)
        self.status_badge.pack(side="right", padx=20, pady=16)

    # ---- Hero / URL input ---------------------------------------------------
    def _build_hero(self) -> None:
        hero = ctk.CTkFrame(
            self.root, fg_color=config.COLOR_CARD, corner_radius=20,
            border_width=1, border_color=config.COLOR_CARD_BORDER,
        )
        hero.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            hero, text="Facebook Comments  →  AI Collection Engine  →  CSV Export",
            font=("Segoe UI", 14, "bold"), text_color=config.COLOR_TEXT_SECONDARY,
        ).pack(pady=(20, 12))

        cards_row = ctk.CTkFrame(hero, fg_color="transparent")
        cards_row.pack(pady=(0, 16))
        for emoji, label in (("💬", "Facebook\nComments"), ("🤖", "AI Collection\nEngine"), ("📄", "CSV\nExport")):
            card = ctk.CTkFrame(
                cards_row, fg_color=config.COLOR_BG, corner_radius=14, width=140, height=90,
                border_width=1, border_color=config.COLOR_CARD_BORDER,
            )
            card.pack(side="left", padx=10)
            ctk.CTkLabel(card, text=emoji, font=("Segoe UI Emoji", 22)).pack(pady=(14, 0))
            ctk.CTkLabel(
                card, text=label, font=("Segoe UI", 11), text_color=config.COLOR_TEXT_SECONDARY,
            ).pack()

        entry_row = ctk.CTkFrame(hero, fg_color="transparent")
        entry_row.pack(pady=(0, 20), padx=20, fill="x")
        ctk.CTkLabel(
            entry_row, text="วาง URL โพสต์ Facebook", font=("Segoe UI", 12),
            text_color=config.COLOR_TEXT_SECONDARY, anchor="w",
        ).pack(anchor="w")
        self.url_entry = ctk.CTkEntry(
            entry_row, placeholder_text="https://www.facebook.com/.../posts/...",
            height=40, corner_radius=10,
        )
        self.url_entry.pack(fill="x", pady=(6, 0))
        self.url_error_label = ctk.CTkLabel(
            entry_row, text="", font=("Segoe UI", 11), text_color=config.COLOR_ERROR, anchor="w",
        )
        self.url_error_label.pack(anchor="w", pady=(4, 0))

    # ---- Main button ----------------------------------------------------
    def _build_main_button(self) -> None:
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(pady=(0, 16))

        self.main_button = ctk.CTkButton(
            frame, text="🚀 เริ่มดึงข้อมูลจาก Facebook",
            width=400, height=100, corner_radius=24,
            font=("Segoe UI", 18, "bold"),
            fg_color=config.COLOR_PRIMARY_BLUE, hover_color=config.COLOR_PRIMARY_PURPLE,
            command=self._handle_start_click,
        )
        self.main_button.pack()
        bind_hover_scale(self.main_button, scale=1.05)

        ctk.CTkLabel(
            frame, text="เปิดโพสต์ Facebook ทิ้งไว้ แล้วกดปุ่มนี้",
            font=("Segoe UI", 12), text_color=config.COLOR_TEXT_SECONDARY,
        ).pack(pady=(8, 0))

    def _handle_start_click(self) -> None:
        url = self.url_entry.get().strip()
        if not url or "facebook.com" not in url.lower():
            self.url_error_label.configure(text=config.INVALID_URL_MSG)
            return
        self.url_error_label.configure(text="")
        self.on_start(url)

    # ---- Progress section -------------------------------------------------
    def _build_progress_section(self) -> None:
        self.progress_frame = ctk.CTkFrame(
            self.root, fg_color=config.COLOR_CARD, corner_radius=20,
            border_width=1, border_color=config.COLOR_CARD_BORDER,
        )
        self.progress_ring = ProgressRing(self.progress_frame, size=160)
        self.progress_ring.pack(pady=(24, 8))
        self.action_label = ctk.CTkLabel(
            self.progress_frame, text="", font=("Segoe UI", 13),
            text_color=config.COLOR_TEXT_SECONDARY,
        )
        self.action_label.pack(pady=(0, 24))

    # ---- Stats section ----------------------------------------------------
    def _build_stats_section(self) -> None:
        self.stats_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.stats_frame.pack(fill="x", pady=(0, 16))
        for i in range(4):
            self.stats_frame.grid_columnconfigure(i, weight=1)

        self.stat_card_total = StatCard(self.stats_frame, "ความคิดเห็นทั้งหมด")
        self.stat_card_valid = StatCard(self.stats_frame, "ข้อมูลที่ถูกต้อง")
        self.stat_card_dupe = StatCard(self.stats_frame, "ข้อมูลซ้ำ")
        self.stat_card_exported = StatCard(self.stats_frame, "Export สำเร็จ")

        for i, card in enumerate(
            (self.stat_card_total, self.stat_card_valid, self.stat_card_dupe, self.stat_card_exported)
        ):
            card.grid(row=0, column=i, sticky="nsew", padx=8)

    # ---- Live activity log --------------------------------------------------
    def _build_log_section(self) -> None:
        log_card = ctk.CTkFrame(
            self.root, fg_color=config.COLOR_CARD, corner_radius=20,
            border_width=1, border_color=config.COLOR_CARD_BORDER,
        )
        log_card.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(
            log_card, text="Live Activity Log", font=("Segoe UI", 13, "bold"),
            text_color=config.COLOR_TEXT_PRIMARY, anchor="w",
        ).pack(anchor="w", padx=16, pady=(12, 4))
        self.log_box = ActivityLogBox(log_card, height=140)
        self.log_box.pack(fill="x", padx=16, pady=(0, 16))

    # ---- Result section -----------------------------------------------------
    def _build_result_section(self) -> None:
        self.result_frame = ctk.CTkFrame(
            self.root, fg_color=config.COLOR_CARD, corner_radius=20,
            border_width=1, border_color=config.COLOR_SUCCESS,
        )
        ctk.CTkLabel(self.result_frame, text="🎉 ดึงข้อมูลสำเร็จ!", font=("Segoe UI", 20, "bold"),
                     text_color=config.COLOR_SUCCESS).pack(pady=(24, 8))
        self.result_filename_label = ctk.CTkLabel(
            self.result_frame, text="", font=("Segoe UI", 13), text_color=config.COLOR_TEXT_PRIMARY,
        )
        self.result_filename_label.pack()
        self.result_count_label = ctk.CTkLabel(
            self.result_frame, text="", font=("Segoe UI", 13), text_color=config.COLOR_TEXT_SECONDARY,
        )
        self.result_count_label.pack(pady=(0, 16))

        button_row = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        button_row.pack(pady=(0, 24))
        ctk.CTkButton(
            button_row, text="📂 เปิดโฟลเดอร์", command=lambda: self.on_open_folder(),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            button_row, text="📄 เปิดไฟล์ CSV", command=lambda: self.on_open_csv(),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            button_row, text="🔄 ดึงข้อมูลอีกครั้ง", command=lambda: self.on_run_again(),
        ).pack(side="left", padx=8)

    # ---- Visibility helpers -------------------------------------------------
    def set_progress_visible(self, visible: bool) -> None:
        if visible:
            self.progress_frame.pack(fill="x", pady=(0, 16), before=self.stats_frame)
        else:
            self.progress_frame.pack_forget()

    def set_result_visible(self, visible: bool) -> None:
        if visible:
            self.result_frame.pack(fill="x", pady=(0, 16))
        else:
            self.result_frame.pack_forget()

    def reset(self) -> None:
        self.main_button.configure(text="🚀 เริ่มดึงข้อมูลจาก Facebook", state="normal")
        self.status_badge.set_state("ready")
        self.set_progress_visible(False)
        self.set_result_visible(False)
        self.log_box.clear()
        for card in (
            self.stat_card_total, self.stat_card_valid,
            self.stat_card_dupe, self.stat_card_exported,
        ):
            card.animate_to(0, duration_ms=200)
