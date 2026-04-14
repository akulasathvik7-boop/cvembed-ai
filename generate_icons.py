"""
Run this script ONCE to generate the PWA icons for CVEmbed AI.
Usage: python generate_icons.py
"""
from PIL import Image
import os, sys

src = os.path.join(os.path.dirname(__file__),
    r"C:\Users\Meridian\.gemini\antigravity\brain\f57ce1f0-e18d-4d6e-abe3-eedf4b9fb907\icon_512_1776138448317.png")
dest = os.path.join(os.path.dirname(__file__), "static")

if not os.path.exists(src):
    # Fallback: generate a simple purple icon if the source isn't found
    print(f"Source icon not found at: {src}")
    print("Generating a simple placeholder icon instead...")
    from PIL import ImageDraw, ImageFont

    def make_icon(size, path):
        img = Image.new("RGBA", (size, size), (3, 11, 24, 255))
        draw = ImageDraw.Draw(img)
        # Background gradient-ish circle
        cx, cy = size // 2, size // 2
        r = int(size * 0.42)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(124, 58, 237, 255))
        # Text "CV"
        font_size = int(size * 0.35)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        text = "CV"
        bbox = draw.textbbox((0,0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx - tw//2, cy - th//2), text, fill=(255, 255, 255, 255), font=font)
        img.save(path)
        print(f"  Saved {path} ({size}x{size})")

    make_icon(512, os.path.join(dest, "icon-512.png"))
    make_icon(192, os.path.join(dest, "icon-192.png"))
else:
    img = Image.open(src).convert("RGBA")
    img.resize((512, 512), Image.LANCZOS).save(os.path.join(dest, "icon-512.png"))
    print(f"  Saved icon-512.png")
    img.resize((192, 192), Image.LANCZOS).save(os.path.join(dest, "icon-192.png"))
    print(f"  Saved icon-192.png")

print("\nDone! Both icons are in the static/ folder.")
