"""One-off helper to generate placeholder visual assets. Not part of the app."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).parent.parent / "assets"
ASSETS.mkdir(exist_ok=True)
(ASSETS / "sounds").mkdir(exist_ok=True)


def make_logo() -> Image.Image:
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, 248, 248], radius=48, fill=(59, 130, 246, 255))
    draw.rounded_rectangle([8, 8, 248, 248], radius=48, outline=(139, 92, 246, 255), width=8)
    try:
        font = ImageFont.truetype("seguiemj.ttf", 140)
        bbox = draw.textbbox((0, 0), "\U0001F381", font=font, embedded_color=True)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((256 - w) / 2 - bbox[0], (256 - h) / 2 - bbox[1]), "\U0001F381", font=font, embedded_color=True)
    except Exception as exc:
        print("emoji glyph unavailable, using plain mark:", exc)
        draw.ellipse([78, 78, 178, 178], fill=(255, 255, 255, 230))
    return img


def make_confetti_gif(frames: int = 12, size: int = 200) -> list[Image.Image]:
    import random

    random.seed(42)
    colors = [(59, 130, 246), (139, 92, 246), (34, 197, 94), (245, 158, 11), (239, 68, 68)]
    particles = [
        {
            "x": random.randint(0, size),
            "y": random.randint(-size, 0),
            "vy": random.uniform(4, 10),
            "color": random.choice(colors),
            "r": random.randint(3, 6),
        }
        for _ in range(40)
    ]
    images = []
    for _ in range(frames):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for p in particles:
            draw.ellipse([p["x"] - p["r"], p["y"] - p["r"], p["x"] + p["r"], p["y"] + p["r"]], fill=p["color"])
            p["y"] += p["vy"]
            if p["y"] > size:
                p["y"] = random.randint(-20, 0)
        images.append(img.convert("RGB"))
    return images


logo = make_logo()
logo.save(ASSETS / "logo.png")
logo.save(ASSETS / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

confetti_frames = make_confetti_gif()
confetti_frames[0].save(
    ASSETS / "success.gif",
    save_all=True,
    append_images=confetti_frames[1:],
    duration=80,
    loop=0,
)

print("Assets generated:", list(ASSETS.iterdir()))
