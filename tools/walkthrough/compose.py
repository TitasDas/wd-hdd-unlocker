"""Compose the walkthrough video frames from the captured app states.

Output: frames/NNNNN.png at 25 fps, 1280x960 (matches the storefront player),
plus usage-demo.vtt, usage-demo-transcript.txt and chapters.json.
"""
import json, math, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captions as CAP
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CAPS = 'caps'
OUT = 'frames'
W, H, FPS = 1280, 960, 25
FONTS = os.environ.get('WALKTHROUGH_FONTS', os.path.expanduser('~/.claude/skills/canvas-design/canvas-fonts/'))
NAVY = (15, 30, 51); BLUE = (31, 95, 191)
shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)


def font(name, size):
    return ImageFont.truetype(FONTS + name, size)

F_TITLE = font('Outfit-Bold.ttf', 64)
F_H2 = font('Outfit-Bold.ttf', 40)
F_BODY = font('InstrumentSans-Regular.ttf', 30)
F_CAP = font('Outfit-Bold.ttf', 50)
F_SMALL = font('InstrumentSans-Regular.ttf', 22)

_bg = None
def background():
    global _bg
    if _bg is None:
        img = Image.new('RGB', (W, H)); px = img.load()
        for y in range(H):
            for x in range(W):
                t = x / W * 0.55 + y / H * 0.45
                px[x, y] = tuple(int(NAVY[i] + (BLUE[i] - NAVY[i]) * t * 0.8) for i in range(3))
        d = ImageDraw.Draw(img)
        for y in range(40, H, 48):
            for x in range(40, W, 48):
                d.ellipse((x, y, x + 2, y + 2), fill=(70, 100, 145))
        _bg = img
    return _bg.copy()


def rounded(im, radius=16):
    mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), radius=radius, fill=255)
    o = im.convert('RGBA'); o.putalpha(mask); return o


def with_shadow(canvas, im, pos, radius=16):
    sh = Image.new('RGBA', (im.width + 100, im.height + 100), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((50, 60, im.width + 50, im.height + 50), radius=radius, fill=(0, 0, 0, 160))
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    canvas.paste(sh, (pos[0] - 50, pos[1] - 50), sh)
    canvas.paste(im, pos, im)


def app_frame(cap, dialog=None, zoom=1.0, focus=(0.5, 0.5), caption='', caption_alpha=1.0, dim=0.0):
    """Screenshot on the brand background, optional dialog composite, Ken Burns zoom, caption bar."""
    shot = Image.open(f'{CAPS}/{cap}.png').convert('RGB')
    if dialog:
        dl = Image.open(f'{CAPS}/{dialog}.png').convert('RGB')
        overlay = Image.new('RGBA', shot.size, (10, 15, 25, 120))
        shot = Image.alpha_composite(shot.convert('RGBA'), overlay).convert('RGB')
        dl = rounded(dl, 12)
        pos = ((shot.width - dl.width) // 2, (shot.height - dl.height) // 2)
        with_shadow(shot, dl, pos, 12)
    # zoom: crop a window around the focus point
    if zoom > 1.0:
        cw, ch = int(shot.width / zoom), int(shot.height / zoom)
        cx, cy = int(shot.width * focus[0]), int(shot.height * focus[1])
        x0 = min(max(cx - cw // 2, 0), shot.width - cw); y0 = min(max(cy - ch // 2, 0), shot.height - ch)
        shot = shot.crop((x0, y0, x0 + cw, y0 + ch))
    box_w = 1160
    shot = shot.resize((box_w, int(shot.height * box_w / shot.width)), Image.LANCZOS)
    shot = rounded(shot, 16)
    canvas = background()
    y = 96
    with_shadow(canvas, shot, ((W - box_w) // 2, y), 16)
    if caption:
        canvas = CAP.caption(canvas, caption, F_CAP, alpha=caption_alpha, accent=(79, 143, 230))
    if dim:
        canvas = Image.blend(canvas, Image.new('RGB', (W, H), NAVY), dim)
    return canvas


def card(lines, sub=None, mark=True, small=None):
    canvas = background(); d = ImageDraw.Draw(canvas)
    y = H // 2 - 40 * len(lines) - (30 if sub else 0)
    if mark:
        lk = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'brand', 'lockup-dark.png')).convert('RGBA')
        data = lk.getdata(); out = []
        for r, g, b, a in data:
            out.append((0, 0, 0, 0) if (abs(r - 15) <= 3 and abs(g - 20) <= 3 and abs(b - 27) <= 3) else (r, g, b, a))
        lk.putdata(out); lk = lk.resize((int(lk.width * 0.7), int(lk.height * 0.7)), Image.LANCZOS)
        canvas.paste(lk, ((W - lk.width) // 2, y - lk.height - 40), lk)
    for line in lines:
        tw = d.textlength(line, font=F_TITLE); d.text(((W - tw) / 2, y), line, font=F_TITLE, fill='#ffffff'); y += 80
    if sub:
        for s in sub:
            tw = d.textlength(s, font=F_BODY); d.text(((W - tw) / 2, y + 10), s, font=F_BODY, fill=(213, 226, 244)); y += 44
    if small:
        tw = d.textlength(small, font=F_SMALL); d.text(((W - tw) / 2, H - 90), small, font=F_SMALL, fill=(169, 189, 217))
    return canvas


# ---- storyboard ---------------------------------------------------------------
# Each scene: (kind, seconds, args). Captions double as the VTT cue text.
SCENES = [
    ('card', 3.2, dict(lines=['Your WD drive.', 'On Linux.'], sub=['WD Security only ships for Windows and Mac.', 'This app does the same job on Linux.'])),
    ('app', 4.0, dict(cap='01-drive-locked', zoom=(1.0, 1.08), focus=(0.55, 0.3), caption='Plug in the drive. Your password hint shows up.')),
    ('typing', 4.6, dict(caption='Type the password once.')),
    ('app', 4.0, dict(cap='04-drive-unlocked', zoom=(1.0, 1.1), focus=(0.5, 0.42), caption='Unlocked and mounted. Copy files as usual.')),
    ('app', 3.6, dict(cap='05-volumes', zoom=(1.12, 1.2), focus=(0.55, 0.7), caption='The files belong to you, not to root.')),
    ('app', 3.6, dict(cap='06-password', zoom=(1.0, 1.06), focus=(0.5, 0.35), caption='Set, change or remove the password.')),
    ('app', 4.0, dict(cap='07-change-dialog', dialog='07-change-dialog-dialog', zoom=(1.05, 1.12), focus=(0.5, 0.5), caption='It still opens with WD Security on Windows and Mac.')),
    ('app', 3.8, dict(cap='08-advanced', zoom=(1.0, 1.06), focus=(0.5, 0.3), caption='Reformat as exFAT, NTFS or ext4.')),
    ('app', 3.6, dict(cap='09-format-dialog', dialog='09-format-dialog-dialog', zoom=(1.05, 1.1), focus=(0.5, 0.5), caption='Pick a filesystem and a name.')),
    ('app', 3.6, dict(cap='10-erase-dialog', dialog='10-erase-dialog-dialog', zoom=(1.05, 1.1), focus=(0.5, 0.5), caption='Lost the password? Erase the drive and start again.')),
    ('app', 3.6, dict(cap='11-activity', zoom=(1.0, 1.06), focus=(0.5, 0.4), caption='Every step is logged, in case you need help.')),
    ('app', 3.4, dict(cap='12-drive-dark', zoom=(1.0, 1.06), focus=(0.5, 0.4), caption='Light or dark, with keyboard shortcuts.')),
    ('app', 3.6, dict(cap='13-ejected', zoom=(1.0, 1.05), focus=(0.5, 0.2), caption='Eject, and the drive locks itself.')),
    ('card', 4.6, dict(lines=['Free. Open source.'], sub=['Get the .deb or the standalone binary', 'at implantintelligence.com'], small='Unofficial. Not affiliated with Western Digital. Use only on drives you own.')),
]
XFADE = 0.6  # seconds


def ease(t):
    return t * t * (3 - 2 * t)


def scene_frame(kind, args, t, dur):
    p = t / dur
    if kind == 'card':
        return card(**args)
    if kind == 'typing':
        n = 9
        i = min(n, int(p * (n + 2)))
        cap = '02-unlock-empty' if i == 0 else '03-typing-%02d' % i
        return app_frame(cap, zoom=1.15 + 0.03 * p, focus=(0.5, 0.3), caption=args['caption'])
    z0, z1 = args.get('zoom', (1.0, 1.0))
    return app_frame(args['cap'], dialog=args.get('dialog'), zoom=z0 + (z1 - z0) * ease(p), focus=args.get('focus', (0.5, 0.5)), caption=args['caption'])


# render: scenes overlap by XFADE; total = sum - (n-1)*XFADE
frame_idx = 0
timeline = []
t_cursor = 0.0
cues = []
prev_tail = []   # frames of the previous scene's last XFADE seconds
total_frames = 0
scene_starts = []
for si, (kind, dur, args) in enumerate(SCENES):
    n = int(round(dur * FPS))
    xf = int(round(XFADE * FPS))
    frames = [scene_frame(kind, args, i / FPS, dur) for i in range(n)]
    start_time = t_cursor
    if si > 0:
        # crossfade: blend the previous tail with this head
        for j in range(xf):
            a = ease((j + 1) / xf)
            blended = Image.blend(prev_tail[j], frames[j], a)
            blended.save(f'{OUT}/{frame_idx:05d}.png'); frame_idx += 1
        body = frames[xf:]
    else:
        body = frames
    keep = body[:-xf] if si < len(SCENES) - 1 else body
    for fr in keep:
        fr.save(f'{OUT}/{frame_idx:05d}.png'); frame_idx += 1
    prev_tail = body[-xf:]
    scene_starts.append((start_time, kind, args))
    t_cursor = frame_idx / FPS - (XFADE if si < len(SCENES) - 1 else 0)
    print('scene', si, kind, 'frames so far', frame_idx)

duration = frame_idx / FPS
# captions + chapters
def ts(s):
    return '%02d:%02d:%06.3f' % (int(s // 3600), int(s % 3600 // 60), s % 60)
vtt = ['WEBVTT', '']
chapters = []
cursor = 0.0
lengths = [dur for _, dur, _ in SCENES]
starts = []
for i, dur in enumerate(lengths):
    starts.append(cursor)
    cursor += dur - (XFADE if i < len(lengths) - 1 else 0)
for i, (kind, dur, args) in enumerate(SCENES):
    s = starts[i]; e = starts[i + 1] if i + 1 < len(starts) else duration
    text = args.get('caption') or ' '.join(args.get('lines', []))
    vtt += [f'{ts(s)} --> {ts(e)}', text, '']
    chapters.append({'title': args.get('chapter') or text.split('.')[0], 'start': round(s, 3), 'time': '%d:%02d' % (int(s // 60), int(s % 60))})
open('usage-demo.vtt', 'w').write('\n'.join(vtt))
open('chapters.json', 'w').write(json.dumps(chapters, indent=1))
transcript = ['WD My Passport Linux Unlocker: a walkthrough', 'Version 2.0.1. Recorded in the app\'s demo mode against a simulated drive.', '']
for kind, dur, args in SCENES:
    transcript.append(args.get('caption') or ' '.join(args.get('lines', []) + (args.get('sub') or [])))
open('usage-demo-transcript.txt', 'w').write('\n'.join(transcript) + '\n')
print('frames', frame_idx, 'duration', duration)
json.dump({'durs': [d for _, d, _ in SCENES], 'xfade': XFADE, 'duration': duration}, open('timing.json', 'w'))
