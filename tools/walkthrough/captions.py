"""Broadcast-style captions shared by the walkthrough videos.

A soft transparent scrim rises from the bottom edge; large white type sits on it
with a gentle shadow, left-aligned on a fixed margin, wrapping to two lines.
Each video passes its own typeface so they keep their own character.
"""
from PIL import Image, ImageDraw, ImageFilter

_scrims = {}


def scrim(w, h, height=360, max_alpha=220):
    key = (w, h, height, max_alpha)
    if key not in _scrims:
        s = Image.new('RGBA', (w, h), (0, 0, 0, 0)); px = s.load()
        for y in range(h - height, h):
            t = (y - (h - height)) / height
            a = int(max_alpha * (t ** 1.6))
            for x in range(w):
                px[x, y] = (8, 10, 14, a)
        _scrims[key] = s
    return _scrims[key]


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ''
    for word in words:
        trial = (cur + ' ' + word).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = word
    if cur:
        lines.append(cur)
    return lines


def caption(img, text, font, alpha=1.0, margin=72, bottom=64, accent=None, line_gap=1.18, scrim_from_x=0):
    """Draw a caption onto img (RGB) and return it. alpha fades the whole caption."""
    if not text or alpha <= 0:
        return img
    w, h = img.size
    base = img.convert('RGBA')
    sc = scrim(w, h)
    if scrim_from_x:
        # keep the left of the frame clear (e.g. a menu lives there), with a soft horizontal fade in
        sc = sc.copy(); a = sc.getchannel('A'); fade = Image.new('L', (w, h), 255); fd = ImageDraw.Draw(fade)
        for x in range(0, scrim_from_x):
            fd.line((x, 0, x, h), fill=int(255 * max(0, (x - scrim_from_x + 120) / 120)))
        from PIL import ImageChops
        sc.putalpha(ImageChops.multiply(a, fade))
    if alpha < 1:
        sc = sc.copy(); sc.putalpha(sc.getchannel('A').point(lambda v: int(v * alpha)))
    base = Image.alpha_composite(base, sc)
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    lines = wrap(d, text, font, w - 2 * margin)[:2]
    size = font.size; lh = int(size * line_gap)
    y = h - bottom - lh * len(lines)
    if accent:
        d.rectangle((margin - 26, y + 6, margin - 18, y + lh * len(lines) - 8), fill=accent + (int(255 * alpha),))
    shadow = Image.new('RGBA', (w, h), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
    for i, line in enumerate(lines):
        sd.text((margin + 2, y + i * lh + 3), line, font=font, fill=(0, 0, 0, int(170 * alpha)))
        d.text((margin, y + i * lh), line, font=font, fill=(255, 255, 255, int(255 * alpha)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    base = Image.alpha_composite(base, shadow)
    base = Image.alpha_composite(base, layer)
    return base.convert('RGB')
