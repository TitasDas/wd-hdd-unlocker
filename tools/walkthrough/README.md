# Walkthrough video

Regenerates the product video shown on implantintelligence.com and the GIF teaser on the GitHub profile. Everything is recorded from the app in demo mode, so no drive is needed.

```bash
pip install -r ../../requirements.txt pillow fonttools
python3 capture.py        # drives the app headless, writes caps/*.png
python3 compose.py        # frames/ at 25 fps, 1280x960, plus captions, transcript, chapters
./encode.sh cipher.mp3    # soundtrack, whooshes, MP4, poster, GIF
```

Fonts come from the canvas-design skill (Outfit and Instrument Sans, both OFL); point `WALKTHROUGH_FONTS` at another directory if it lives elsewhere. The storyboard is the `SCENES` list in `compose.py`: one line per scene with its capture, zoom, focus and caption. Captions double as the VTT cues and chapter titles.
