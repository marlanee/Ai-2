"""Gentle lofi mastering chain (ffmpeg only) for generated tracks.

  python scripts/master_lofi.py in.flac out.flac [--preset warm|tape|clean]

warm : highpass 30 Hz, low-shelf +1.5 dB @120, tame harsh 3-5 kHz (-2 dB), soft high-shelf -2 dB @9 kHz,
       glue compression (2:1, slow), subtle stereo widen, true-peak safe limiter
tape : warm + gentle saturation (asoftclip) + slight wow/flutter (vibrato 0.3 Hz, tiny depth) + lowpass 14 kHz
clean: highpass + harsh-band dip + glue compression only
Loudness is NOT normalized here (compose.py does -14 LUFS for the whole video).
"""
import argparse, subprocess

FF = r"C:\AI\tools\ffmpeg\bin\ffmpeg.exe"
BASE = ["highpass=f=30", "equalizer=f=4000:t=q:w=1.2:g=-2"]
WARM = ["lowshelf=f=120:g=1.5", "highshelf=f=9000:g=-2"]
GLUE = ["acompressor=threshold=-18dB:ratio=2:attack=30:release=250:makeup=2"]
WIDE = ["extrastereo=m=1.15"]
TAPE = ["asoftclip=type=tanh:param=0.9", "vibrato=f=0.3:d=0.02", "lowpass=f=14000"]
LIM = ["alimiter=limit=0.89:attack=5:release=60"]
PRESETS = {"clean": BASE + GLUE + LIM, "warm": BASE + WARM + GLUE + WIDE + LIM, "tape": BASE + WARM + TAPE + GLUE + WIDE + LIM}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--preset", default="warm", choices=PRESETS)
    a = ap.parse_args()
    subprocess.run([FF, "-v", "error", "-y", "-i", a.inp, "-af", ",".join(PRESETS[a.preset]), "-ar", "48000", a.out], check=True)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
