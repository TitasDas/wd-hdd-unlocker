"""Lay narration onto a walkthrough, duck the music under it, encode, and write captions.

usage: mix.py wd|fm|dd|rs
"""
import json, os, subprocess, sys
import numpy as np, soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__)); VO = os.path.join(HERE, '..', 'voice')
key = sys.argv[1]
S = json.load(open(f'{VO}/scripts.json'))[key]
LENS = json.load(open(f'{VO}/{key}-lens.json'))
SR = 24000

def shown(t):
    for a, b in (('W D', 'WD'), ('ex-fat', 'exFAT'), ('N T F S', 'NTFS'), ('ext four', 'ext4'), ('U S B', 'USB'), ('P D F', 'PDF')):
        t = t.replace(a, b)
    return t

def ts(s): return '%02d:%02d:%06.3f' % (int(s // 3600), int(s % 3600 // 60), s % 60)

if key in ('wd', 'fm'):
    wd = os.path.join(HERE, 'fm' if key == 'fm' else '')
    T = json.load(open(os.path.join(wd, 'timing.json'))); durs, xf = T['durs'], T['xfade']; duration = T['duration']
    starts = []; c = 0.0
    for i, d in enumerate(durs):
        starts.append(c); c += d - (xf if i < len(durs) - 1 else 0)
    offsets = [0.5] + [s + 0.45 for s in starts[1:]]
    music, skip, frames = (os.path.join(HERE, 'cipher.mp3'), 12, os.path.join(wd, 'frames')) if key == 'wd' else (os.path.join(wd, 'lobby-time.mp3'), 8, os.path.join(wd, 'frames'))
    whoosh_at = starts[1:]
elif key == 'dd':
    wd = os.path.join(HERE, 'dd'); T = json.load(open(f'{wd}/timing.json')); duration = T['duration']; cues = T['cues']; intro = T['intro']
    offsets = [0.4, 2.7 * intro / 5.2 + 0.2] + [c[0] + 0.35 for c in cues[1:8]] + [None] + [cues[-1][0] + 0.5]
    music, skip, frames = f'{wd}/wallpaper.mp3', 6, f'{wd}/frames'
    whoosh_at = T['cue_starts']
else:  # readstand: the existing video, its own music, narration at each chapter
    src = '/home/td/work/software-shop-wd-unlocker/public/media/readstand/0.2.2/usage-demo.mp4'
    chapters = [0.0, 3.08, 15.2, 51.32, 72.48, 88.96, 105.28, 112.12, 126.0, 141.76, 154.2, 174.08, 187.64, 213.08]
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src]).decode())
    offsets = [0.2, 5.9] + [c + 1.75 for c in chapters[2:13]] + [chapters[13] + 0.6]
    wd = os.path.join(HERE, 'rs')

track = np.zeros(int((duration + 1) * SR), dtype=np.float32); cues = []
for i, text in enumerate(S['lines']):
    if not text or offsets[i] is None: continue
    clip, sr = sf.read(f'{VO}/{key}-{i:02d}.wav', dtype='float32'); assert sr == SR
    a = int(offsets[i] * SR); track[a:a + len(clip)] += clip[:len(track) - a]
    cues.append((offsets[i], offsets[i] + len(clip) / SR, shown(text)))
peak = np.abs(track).max(); track *= 0.89 / peak if peak else 1
sf.write(f'{wd}/voice.wav', track[:int(duration * SR)], SR)
for a, (s, e, _) in enumerate(cues):
    if a + 1 < len(cues): assert e <= cues[a + 1][0] + 0.05, f'overlap at cue {a}: {e:.2f} > {cues[a+1][0]:.2f}'
    assert e <= duration + 0.05, f'cue {a} runs past the end'

vtt = ['WEBVTT', ''] + sum(([f'{ts(s)} --> {ts(e)}', t, ''] for s, e, t in cues), [])
open(f'{wd}/usage-demo.vtt', 'w').write('\n'.join(vtt))
names = {'wd': 'WD My Passport Linux Unlocker', 'fm': 'Forced Move', 'dd': 'Desktop Drawer', 'rs': 'Readstand'}
voice_note = f"Narration: synthetic voice ({S['voice']}, Kokoro-82M, Apache 2.0)."
music_note = {'wd': 'Music: Cipher by Kevin MacLeod (incompetech.com), CC BY 4.0.', 'fm': 'Music: Lobby Time by Kevin MacLeod (incompetech.com), CC BY 4.0.',
              'dd': 'Music: Wallpaper by Kevin MacLeod (incompetech.com), CC BY 4.0. Wallpaper photo by Daniel Mirlea, Linux Mint backgrounds, Unsplash License.',
              'rs': 'Music: Meditation Impromptu 01 and 02 by Kevin MacLeod (incompetech.com), CC BY 4.0.'}[key]
open(f'{wd}/usage-demo-transcript.txt', 'w').write(f"{names[key]}: a narrated walkthrough\n\n" + '\n\n'.join(t for _, _, t in cues) + f"\n\n{voice_note}\n{music_note}\n")

duck = 'sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450:makeup=1'
if key == 'rs':
    fc = f"[0:a]volume=1.0[m];[1:a]aresample=44100,volume=1.25,asplit[v1][v2];[m][v1]{duck}[md];[md][v2]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-i', f'{wd}/voice.wav', '-filter_complex', fc, '-map', '0:v', '-map', '[a]',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', f'{wd}/usage-demo.mp4'], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '9', '-i', f'{wd}/usage-demo.mp4', '-frames:v', '1', '-q:v', '3', f'{wd}/usage-demo-poster.jpg'], check=True)
else:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anoisesrc=color=pink:amplitude=0.5:duration=0.6:sample_rate=44100', '-af',
                    'bandpass=f=800:width_type=o:w=1.4,afade=t=in:st=0:d=0.2,afade=t=out:st=0.25:d=0.35', f'{wd}/whoosh.wav'], check=True)
    ins = ['-i', music, '-i', f'{wd}/voice.wav']; fc = [f"[0:a]atrim=start={skip},asetpts=PTS-STARTPTS,volume=0.34,afade=t=in:st=0:d=1.5,afade=t=out:st={duration - 2.5:.2f}:d=2.5[m]",
                                                       f"[1:a]aresample=44100,volume=1.25,asplit[v1][v2]", f"[m][v1]{duck}[md]"]
    mixin = '[md][v2]'
    for k, s in enumerate(whoosh_at):
        ins += ['-i', f'{wd}/whoosh.wav']; ms = int(s * 1000); fc.append(f"[{k + 2}:a]adelay={ms}|{ms},volume=0.16[w{k}]"); mixin += f'[w{k}]'
    fc.append(f"{mixin}amix=inputs={len(whoosh_at) + 2}:normalize=0:duration=first,alimiter=limit=0.95[a]")
    subprocess.run(['ffmpeg', '-v', 'error', '-y'] + ins + ['-filter_complex', ';'.join(fc), '-map', '[a]', '-t', f'{duration}', '-ar', '44100', '-ac', '2', f'{wd}/audio.wav'], check=True)
    out = f'{wd}/usage-demo.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '25', '-i', f'{frames}/%05d.png', '-i', f'{wd}/audio.wav', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-c:a', 'aac', '-b:a', '160k', '-shortest', out], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '4', '-i', out, '-frames:v', '1', '-q:v', '3', f'{wd}/usage-demo-poster.jpg'], check=True)
print(key, 'duration', round(duration, 1), 'cues', len(cues))
