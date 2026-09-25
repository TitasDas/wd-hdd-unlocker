"""Synthesize every narration line with Kokoro and record its length."""
import json, sys
import numpy as np, soundfile as sf
from kokoro import KPipeline
S = json.load(open('scripts.json')); which = sys.argv[1:] or list(S)
for key in which:
    cfg = S[key]; p = KPipeline(lang_code=cfg['lang'], repo_id='hexgrad/Kokoro-82M'); lens = []
    for i, text in enumerate(cfg['lines']):
        if not text:
            lens.append(0.0); continue
        audio = np.concatenate([a.numpy() for _, _, a in p(text, voice=cfg['voice'], speed=cfg['speed'])])
        # trim leading/trailing silence, add a tiny fade so cuts are clean
        nz = np.where(np.abs(audio) > 0.01)[0]; audio = audio[max(0, nz[0] - 600): nz[-1] + 2400]
        f = 480; audio[:f] *= np.linspace(0, 1, f); audio[-f:] *= np.linspace(1, 0, f)
        sf.write(f'{key}-{i:02d}.wav', audio, 24000); lens.append(round(len(audio) / 24000, 3))
    json.dump(lens, open(f'{key}-lens.json', 'w')); print(key, lens)
