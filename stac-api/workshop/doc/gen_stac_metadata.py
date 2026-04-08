from PIL import Image, ImageDraw, ImageFont
import math

# Colors
BG_COLOR = "#1e2d3e"
BLUE_BTN = "#2d6fa3"
GREEN_BTN = "#217a52"
VALUE_BOX = "#ffffff"
TITLE_COLOR = "#ffffff"
LABEL_COLOR = "#ffffff"
VALUE_COLOR = "#111111"
SECTION_COLOR = "#ccddee"

W, H = 1300, 590
PADDING = 30
TITLE_H = 60
COL_GAP = 40
CORNER_R = 8
BTN_W = 180
ROW_H = 68
ROW_GAP = 10

def rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
    draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
    draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
    draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)

def text_size(font, text):
    return font.getsize(text)  # returns (w, h) in Pillow < 9

def draw_row(draw, x, y, w, label, value, btn_color, font_bold, font_reg):
    btn_x2 = x + BTN_W
    row_y2 = y + ROW_H
    # Button
    rounded_rect(draw, (x, y, btn_x2, row_y2), CORNER_R, btn_color)
    # Value box
    rounded_rect(draw, (btn_x2 + 8, y, x + w, row_y2), CORNER_R, VALUE_BOX)
    # Label text centered in button
    lw, lh = text_size(font_bold, label)
    draw.text((x + BTN_W//2 - lw//2, y + ROW_H//2 - lh//2), label, fill=LABEL_COLOR, font=font_bold)
    # Value text
    vw, vh = text_size(font_reg, value)
    draw.text((btn_x2 + 18, y + ROW_H//2 - vh//2), value, fill=VALUE_COLOR, font=font_reg)

img = Image.new("RGB", (W, H), BG_COLOR)
draw = ImageDraw.Draw(img)

# Fonts
try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    font_bold  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    font_sec   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    font_reg   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
except:
    font_title = font_bold = font_sec = font_reg = ImageFont.load_default()

# Title
title = "STAC Item"
tw, _ = text_size(font_title, title)
draw.text((W//2 - tw//2, 18), title, fill=TITLE_COLOR, font=font_title)

# Layout: two equal columns
col_w = (W - 2*PADDING - COL_GAP) // 2
left_x = PADDING
right_x = PADDING + col_w + COL_GAP

top_y = TITLE_H + 10

# --- Metadata section (left) ---
draw.text((left_x, top_y), "Metadata", fill=SECTION_COLOR, font=font_sec)
top_y += 28

metadata = [
    ("id",         "20250414_bci/whole_rx1rii"),
    ("datetime",   "2025-04-14"),
    ("collection", "2024_bci"),
    ("bbox",       "[-79.87, 9.13, -79.82, 9.18]"),
    ("platform",   "Trinity F90 — Sony RX1R II"),
    ("resolution", "3.8 cm/px  3 081 ha"),
]

y = top_y
for label, value in metadata:
    draw_row(draw, left_x, y, col_w, label, value, BLUE_BTN, font_bold, font_reg)
    y += ROW_H + ROW_GAP

# --- Assets section (right) ---
y = TITLE_H + 10
draw.text((right_x, y), "Assets (direct file links)", fill=SECTION_COLOR, font=font_sec)
y += 28

assets = [
    ("rgb/optimized",  "https://kanopia.org/.../whole_rx1rii_rgb.cog.tif"),
    ("dsm/optimized",  "https://kanopia.org/.../whole_rx1rii_dsm.cog.tif"),
    ("pc/optimized",   "https://kanopia.org/.../whole_rx1rii_copc.laz"),
    ("rgb/thumbnail",  "https://kanopia.org/.../whole_rx1rii_thumbnail.png"),
]

for label, value in assets:
    draw_row(draw, right_x, y, col_w, label, value, GREEN_BTN, font_bold, font_reg)
    y += ROW_H + ROW_GAP

img.save("/home/vincelf/vscode-workspaces/lefolab-utils/stac-api/workshop/doc/stac-metadata-only.png")
print(f"Saved {W}x{H} image")
