# Walkthrough video

Regenerates the product video shown on implantintelligence.com and the GIF teaser on the GitHub profile. Everything is recorded from the app in demo mode, so no drive is needed.

```bash
pip install -r ../../requirements.txt pillow fonttools
python3 capture.py        # drives the app headless, writes caps/*.png
python3 compose.py        # frames/ at 25 fps, 1280x960, plus captions, transcript, chapters
./encode.sh cipher.mp3    # soundtrack, whooshes, MP4, poster, GIF
```

Fonts come from the canvas-design skill (Outfit and Instrument Sans, both OFL); point `WALKTHROUGH_FONTS` at another directory if it lives elsewhere. The storyboard is the `SCENES` list in `compose.py`: one line per scene with its capture, zoom, focus and caption. Captions double as the VTT cues and chapter titles.

## Narration

`narration.json` holds the spoken script, one line per scene. `narrate.py` voices it with Kokoro-82M (Apache 2.0, runs on CPU: `pip install torch --index-url https://download.pytorch.org/whl/cpu kokoro soundfile`), and `mix.py` lays it onto the video. Render first with `NARRATION_LENS=<key>-lens.json` so each scene holds long enough for its line, then run `mix.py <key>` to add the voice, duck the music under it with a sidechain compressor, and write captions and a transcript that follow the narration. Paths in `mix.py` point at the working folder used to build the published video; adjust them to yours. The video pages label the narration as a synthetic voice.
