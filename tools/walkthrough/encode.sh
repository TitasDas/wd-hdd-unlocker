#!/usr/bin/env bash
# Mix the soundtrack with a short whoosh at every scene change and encode the video.
# Run compose.py first (it writes frames/ and starts are derived from its storyboard).
# Music: "Cipher" by Kevin MacLeod, CC BY 4.0, from
#   https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cipher2.mp3
set -euo pipefail
cd "$(dirname "$0")"
MUSIC="${1:-cipher.mp3}"
[[ -f "$MUSIC" ]] || { echo "Download the track to $MUSIC first (see the comment above)." >&2; exit 1; }
DUR=$(python3 -c "
durs=[3.2,4.0,4.6,4.0,3.6,3.4,4.0,3.4,3.6,3.6,3.2,3.2,3.6,4.6]; xf=0.6
starts=[]; c=0.0
for i,d in enumerate(durs):
    starts.append(c); c+=d-(xf if i<len(durs)-1 else 0)
open('starts.txt','w').write(' '.join('%.3f'%s for s in starts[1:])); print(round(c,2))")
ffmpeg -v error -y -f lavfi -i "anoisesrc=color=pink:amplitude=0.6:duration=0.7:sample_rate=44100" \
  -af "bandpass=f=900:width_type=o:w=1.6,afade=t=in:st=0:d=0.25,afade=t=out:st=0.3:d=0.4,volume=0.9" whoosh.wav
STARTS=$(cat starts.txt); N=$(echo $STARTS | wc -w)
INPUTS="-i $MUSIC"; FILTER="[0:a]atrim=start=12,asetpts=PTS-STARTPTS,volume=0.32,afade=t=in:st=0:d=1.5,afade=t=out:st=$(python3 -c "print($DUR-2.5)"):d=2.5[m];"; MIX="[m]"; k=1
for s in $STARTS; do INPUTS="$INPUTS -i whoosh.wav"; ms=$(python3 -c "print(int($s*1000))"); FILTER="$FILTER[$k:a]adelay=${ms}|${ms},volume=0.35[w$k];"; MIX="$MIX[w$k]"; k=$((k+1)); done
FILTER="$FILTER${MIX}amix=inputs=$((N+1)):normalize=0:duration=first[aout]"
ffmpeg -v error -y $INPUTS -filter_complex "$FILTER" -map "[aout]" -t "$DUR" -ar 44100 -ac 2 audio.wav
ffmpeg -v error -y -framerate 25 -i frames/%05d.png -i audio.wav -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 160k -shortest usage-demo.mp4
ffmpeg -v error -y -ss 5 -i usage-demo.mp4 -frames:v 1 -q:v 3 usage-demo-poster.jpg
ffmpeg -v error -y -framerate 25 -start_number 190 -i frames/%05d.png -frames:v 150 -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" teaser.gif
echo "usage-demo.mp4 ($DUR s), usage-demo-poster.jpg, usage-demo.vtt, usage-demo-transcript.txt, chapters.json, teaser.gif"
