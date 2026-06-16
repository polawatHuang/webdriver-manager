"""Animation helpers: gradient image generation, hover-scale, best-effort confetti/sound.

All best-effort extras (confetti, sound) fail silently (logged, not raised) so a
missing asset or an unsupported codec never crashes the app — per the agreed
graceful-degradation policy for decorative polish.
"""
import logging

from PIL import Image, ImageTk

import paths

logger = logging.getLogger(__name__)


def make_gradient_image(width: int, height: int, color_start: str, color_end: str) -> ImageTk.PhotoImage:
    """Pillow has no native gradient primitive — build it pixel-column by pixel-column."""

    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    start_rgb = _hex_to_rgb(color_start)
    end_rgb = _hex_to_rgb(color_end)

    image = Image.new("RGB", (width, height))
    for x in range(width):
        t = x / max(1, width - 1)
        r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t)
        g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t)
        b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t)
        for y in range(height):
            image.putpixel((x, y), (r, g, b))
    return ImageTk.PhotoImage(image)


def bind_hover_scale(widget, scale: float = 1.05) -> None:
    """Best-effort 'hover grows 105%' feel via padding, since true widget scaling
    is limited in Tk. Falls back to a no-op if anything about the widget's geometry
    manager doesn't cooperate."""
    try:
        base_padx = widget.cget("width")
        base_pady = widget.cget("height")
    except Exception:
        return

    def _on_enter(_event):
        try:
            widget.configure(
                width=int(base_padx * scale), height=int(base_pady * scale)
            )
        except Exception:
            pass

    def _on_leave(_event):
        try:
            widget.configure(width=base_padx, height=base_pady)
        except Exception:
            pass

    widget.bind("<Enter>", _on_enter)
    widget.bind("<Leave>", _on_leave)


def play_success_sound() -> None:
    try:
        import winsound

        sound_path = paths.resource_path("assets/sounds/success.wav")
        if sound_path.exists():
            winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception as exc:
        logger.debug("Success sound playback skipped: %s", exc)


def play_confetti(label_widget) -> None:
    """Best-effort animated GIF playback on a CTkLabel. No-op if the asset is
    missing or Pillow can't decode it — confetti is decorative, not load-bearing."""
    try:
        gif_path = paths.resource_path("assets/success.gif")
        if not gif_path.exists():
            return
        image = Image.open(gif_path)
        frames = []
        try:
            while True:
                frames.append(ImageTk.PhotoImage(image.copy()))
                image.seek(image.tell() + 1)
        except EOFError:
            pass

        if not frames:
            return

        def _show_frame(index: int):
            if index >= len(frames):
                return
            try:
                label_widget.configure(image=frames[index])
            except Exception:
                return
            label_widget.after(80, _show_frame, index + 1)

        _show_frame(0)
    except Exception as exc:
        logger.debug("Confetti playback skipped: %s", exc)
