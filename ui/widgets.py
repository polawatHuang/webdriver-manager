"""Reusable custom widgets for the dashboard."""
import tkinter as tk

import customtkinter as ctk

import config

_STATUS_STYLES = {
    "ready": ("🔴", "พร้อมใช้งาน", config.COLOR_ERROR),
    "running": ("🟡", "กำลังรวบรวมความคิดเห็น", config.COLOR_WARNING),
    "success": ("🟢", "Export สำเร็จ", config.COLOR_SUCCESS),
    "error": ("🔴", "เกิดข้อผิดพลาด", config.COLOR_ERROR),
}

_LOG_TAG_COLORS = {
    "success": config.COLOR_SUCCESS,
    "info": config.COLOR_INFO,
    "warning": config.COLOR_WARNING,
    "error": config.COLOR_ERROR,
}

_MAX_LOG_LINES = 500


class StatusBadge(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=config.COLOR_CARD, corner_radius=999, **kwargs)
        self.label = ctk.CTkLabel(self, text="", font=("Segoe UI", 13, "bold"))
        self.label.pack(padx=16, pady=8)
        self.set_state("ready")

    def set_state(self, state: str) -> None:
        emoji, text, color = _STATUS_STYLES.get(state, _STATUS_STYLES["ready"])
        self.label.configure(text=f"{emoji} {text}", text_color=color)


class StatCard(ctk.CTkFrame):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(
            master, fg_color=config.COLOR_CARD, corner_radius=16,
            border_width=1, border_color=config.COLOR_CARD_BORDER, **kwargs
        )
        self._value = 0
        self._animation_job = None

        self.title_label = ctk.CTkLabel(
            self, text=title, font=("Segoe UI", 13),
            text_color=config.COLOR_TEXT_SECONDARY,
        )
        self.title_label.pack(padx=20, pady=(16, 4))

        self.value_label = ctk.CTkLabel(
            self, text="0", font=("Segoe UI", 32, "bold"),
            text_color=config.COLOR_TEXT_PRIMARY,
        )
        self.value_label.pack(padx=20, pady=(0, 16))

    def animate_to(self, target_value: int, duration_ms: int = 600) -> None:
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)

        start_value = self._value
        steps = max(1, duration_ms // 16)
        delta = target_value - start_value
        step_count = {"n": 0}

        def _step():
            step_count["n"] += 1
            progress = min(1.0, step_count["n"] / steps)
            eased = 1 - (1 - progress) ** 2  # quadratic ease-out
            current = round(start_value + delta * eased)
            self._value = current
            self.value_label.configure(text=str(current))
            if progress < 1.0:
                self._animation_job = self.after(16, _step)
            else:
                self._animation_job = None

        _step()


class ProgressRing(ctk.CTkFrame):
    """Canvas-based progress ring with a CTkProgressBar fallback that shares the
    same set_progress() call signature, in case Canvas drawing misbehaves."""

    def __init__(self, master, size: int = 180, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.size = size
        self._pct = 0
        self._use_fallback = False

        try:
            self.canvas = tk.Canvas(
                self, width=size, height=size, bg=config.COLOR_BG, highlightthickness=0
            )
            self.canvas.pack()
            self.pct_label = ctk.CTkLabel(
                self, text="0%", font=("Segoe UI", 22, "bold"),
                text_color=config.COLOR_TEXT_PRIMARY,
            )
            self.pct_label.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            self._use_fallback = True
            self.bar = ctk.CTkProgressBar(self, width=size, mode="determinate")
            self.bar.set(0)
            self.bar.pack()

    def set_progress(self, pct: float) -> None:
        self._pct = max(0, min(100, pct))
        if self._use_fallback:
            self.bar.set(self._pct / 100)
            return

        try:
            self.canvas.delete("ring")
            pad = 14
            extent = -self._pct * 3.6
            self.canvas.create_arc(
                pad, pad, self.size - pad, self.size - pad,
                start=90, extent=-360, style="arc",
                outline=config.COLOR_CARD_BORDER, width=14, tags="ring",
            )
            self.canvas.create_arc(
                pad, pad, self.size - pad, self.size - pad,
                start=90, extent=extent, style="arc",
                outline=config.COLOR_PRIMARY_BLUE, width=14, tags="ring",
            )
            self.pct_label.configure(text=f"{int(self._pct)}%")
        except Exception:
            self._use_fallback = True
            self.canvas.pack_forget()
            self.bar = ctk.CTkProgressBar(self, width=self.size, mode="determinate")
            self.bar.pack()
            self.bar.set(self._pct / 100)


class ActivityLogBox(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        super().__init__(
            master, fg_color=config.COLOR_CARD, corner_radius=16,
            font=("Consolas", 12), wrap="word", **kwargs
        )
        for level, color in _LOG_TAG_COLORS.items():
            self.tag_config(level, foreground=color)
        self.configure(state="disabled")
        self._line_count = 0

    def append(self, message: str, level: str = "info") -> None:
        self.configure(state="normal")
        self.insert("end", message + "\n", level)
        self._line_count += 1
        if self._line_count > _MAX_LOG_LINES:
            self.delete("1.0", "2.0")
            self._line_count -= 1
        self.see("end")
        self.configure(state="disabled")

    def clear(self) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        self._line_count = 0
        self.configure(state="disabled")
