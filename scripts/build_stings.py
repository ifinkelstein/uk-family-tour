#!/usr/bin/env python3
"""Synthesize short period-FLAVORED plucked-string intro/outro stings with ffmpeg
(additive synthesis; no external samples). Melody choice evokes each region:
Renaissance-major for London, pentatonic for Scotland, open modal for York."""
import subprocess
from pathlib import Path

OUT = Path("/Users/ilya/projects/London-trip-vacation/tour-app/build-audio/music")
TMP = OUT / "tmp"
TMP.mkdir(parents=True, exist_ok=True)

NOTE = {'D3':146.83,'G3':196.0,'A3':220.0,'C4':261.63,'D4':293.66,'E4':329.63,
        'F4':349.23,'F#4':369.99,'G4':392.0,'A4':440.0,'B4':493.88,'C5':523.25,'D5':587.33}

def pluck(freq, dur, path, decay=5.5):
    expr = (f"exp(-t*{decay})*(0.6*sin(2*PI*{freq}*t)+0.3*sin(2*PI*2*{freq}*t)"
            f"+0.15*sin(2*PI*3*{freq}*t)+0.08*sin(2*PI*4*{freq}*t))")
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
                    f"aevalsrc={expr}:d={dur}:s=44100","-ac","1",str(path)],
                   check=True, capture_output=True)

def sting(seq, out, decay=5.5, tail=0.45):
    files = []
    for i,(n,d) in enumerate(seq):
        p = TMP/f"n{i}.wav"; pluck(NOTE[n], d, p, decay); files.append(p)
    listf = TMP/"list.txt"; listf.write_text("".join(f"file '{f}'\n" for f in files))
    raw = TMP/"raw.wav"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listf),
                    "-c","copy",str(raw)], check=True, capture_output=True)
    total = sum(d for _,d in seq)
    subprocess.run(["ffmpeg","-y","-i",str(raw),"-af",
        f"aecho=0.7:0.4:55:0.25,afade=t=out:st={max(0,total-tail):.2f}:d={tail},"
        f"loudnorm=I=-19:TP=-3","-ac","1","-b:a","96k",str(out)],
        check=True, capture_output=True)
    return out

# London — bright Renaissance major arpeggio up to the octave
sting([('C4',0.30),('E4',0.30),('G4',0.30),('C5',0.60)], OUT/"london-intro.mp3", decay=6.0)
sting([('G4',0.45),('C4',0.75)], OUT/"london-outro.mp3", decay=4.8)
# Edinburgh / Scotland — major-pentatonic run
sting([('D4',0.28),('F#4',0.28),('A4',0.28),('B4',0.28),('D5',0.55)], OUT/"edinburgh-intro.mp3", decay=6.0)
sting([('A4',0.45),('D4',0.75)], OUT/"edinburgh-outro.mp3", decay=4.8)
# York — open modal fifths (medieval feel)
sting([('D4',0.34),('A4',0.34),('D5',0.55)], OUT/"york-intro.mp3", decay=5.2)
sting([('A4',0.45),('D4',0.75)], OUT/"york-outro.mp3", decay=4.8)

for f in sorted(OUT.glob("*.mp3")):
    # report duration
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","default=nk=1:nw=1",str(f)], capture_output=True, text=True)
    print(f"{f.name}: {float(r.stdout.strip()):.2f}s")
