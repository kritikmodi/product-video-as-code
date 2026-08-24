#!/usr/bin/env python3
"""Stage 6 - master the audio and mux it onto the picture.

The bed is loudness-normalised to a target *before* ducking. That detail matters:
applying a fixed "-23dB" gain assumes you know how loud the generated music is,
and AI-generated beds vary wildly. Getting this wrong is how a film ships with a
music track that is technically present and completely inaudible.

Chain:
    bed -> loudnorm to --music-lufs (the voice sits at -16, so this sets separation)
        -> sidechain-ducked by the voice
        -> mixed with the voice, edges faded
        -> final loudnorm to broadcast level
"""
import argparse, pathlib, subprocess

HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "out"

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--video", default=str(OUT / "silent.mp4"))
ap.add_argument("--voice", default=str(OUT / "voice.wav"))
ap.add_argument("--music", default=str(HERE / "audio" / "bed.mp3"),
                help="optional; skipped entirely if the file is absent")
ap.add_argument("--music-lufs", type=float, default=-23.0,
                help="bed loudness before ducking. Voice is -16 LUFS, so -23 leaves "
                     "the bed clearly audible in gaps without competing. Go quieter "
                     "(-26) for a denser script, louder (-20) for a sparse one.")
ap.add_argument("--final", default=str(OUT / "final.mp4"))
a = ap.parse_args()

has_music = pathlib.Path(a.music).exists()

cmd = ["ffmpeg", "-y", "-v", "error", "-i", a.video, "-i", a.voice]
if has_music:
    cmd += ["-stream_loop", "-1", "-i", a.music]
    graph = (
        f"[2:a]loudnorm=I={a.music_lufs}:TP=-6:LRA=7,"
        "aformat=sample_rates=48000:channel_layouts=stereo[bed];"
        "[bed][1:a]sidechaincompress=threshold=0.05:ratio=4:attack=15:release=320[duck];"
        "[duck][1:a]amix=inputs=2:normalize=0:duration=first,"
        "afade=t=in:st=0:d=1.5,areverse,afade=t=in:st=0:d=2.2,areverse,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]"
    )
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[out]"]
else:
    cmd += ["-map", "0:v", "-map", "1:a"]

cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", a.final]
subprocess.run(cmd, check=True)
print(("mixed with music bed: " if has_music else "voice only: ") + a.final)
print("verify:  ffmpeg -nostats -i <file> -af volumedetect -f null /dev/null")
