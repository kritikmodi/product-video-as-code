#!/usr/bin/env python3
"""Stage 2 - derive scene timings from the real voiceover, build the voice track.

This is the hinge of the whole pipeline. Scene durations are *measured* from the
narration rather than guessed, so the picture can never drift out of sync with
the voice. Rewording a line changes its clip length, which changes that scene's
duration, which the renderer picks up automatically.

Expects audio/vo_01.mp3 ... vo_NN.mp3, one per scene in script.json.
Writes timings.json (consumed by render.py and composite.py) and out/voice.wav.
"""
import argparse, json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent.parent

# Defaults. Every one is overridable per project from the command line.
LEAD = 0.38       # silence before narration starts inside a scene
TAIL = 0.60       # silence after it ends, before the next scene
TAIL_LAST = 1.90  # longer hold on the closing card
MIN = {}          # {scene: seconds} floor, e.g. a logo reveal needing room
EXTRA = {}        # {scene: seconds} added on, e.g. to hold on screen footage


def dur(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)]).strip())


def parse_map(spec, fallback):
    """Parse "3:4.2,7:1.5" into {3: 4.2, 7: 1.5}."""
    if not spec:
        return fallback
    return {int(k): float(v) for k, v in
            (kv.split(":") for kv in spec.split(",") if kv)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", default="script.json")
    ap.add_argument("--audio", default="audio")
    ap.add_argument("--timings", default="timings.json")
    ap.add_argument("--voice", default="voice.wav")
    ap.add_argument("--lead", type=float, default=LEAD)
    ap.add_argument("--tail", type=float, default=TAIL)
    ap.add_argument("--tail-last", type=float, default=TAIL_LAST)
    ap.add_argument("--min", default="", help='floor per scene, "3:3.3"')
    ap.add_argument("--extra", default="", help='extra hold per scene, "6:6.3"')
    ap.add_argument("--lufs", type=float, default=-16.0,
                    help="delivery loudness for the voice track")
    a = ap.parse_args()

    out_dir = HERE / "out"
    out_dir.mkdir(exist_ok=True)
    mins, extras = parse_map(a.min, MIN), parse_map(a.extra, EXTRA)
    aud = HERE / a.audio

    scenes = json.load(open(HERE / a.script))["scenes"]
    n = len(scenes)
    files = [aud / f"vo_{i:02d}.mp3" for i in range(1, n + 1)]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        sys.exit(f"missing narration: {', '.join(missing)}\n"
                 f"generate one clip per scene into {aud}/ first")

    vos = [dur(f) for f in files]
    durs, parts = [], []
    for i, v in enumerate(vos):
        tail = a.tail_last if i == n - 1 else a.tail
        d = max(a.lead + v + tail, mins.get(i + 1, 0)) + extras.get(i + 1, 0)
        durs.append(round(d, 3))
        pad_end = d - a.lead - v
        # Lay each clip into its own slot: lead-in silence, the line, then pad
        # out to the scene length so the concatenation lands frame-accurately.
        parts.append(
            f"[{i}:a]adelay={int(a.lead*1000)}|{int(a.lead*1000)},"
            f"apad=pad_dur={pad_end:.3f},atrim=0:{d:.3f},aresample=48000[a{i}]")

    json.dump({"durations": durs}, open(HERE / a.timings, "w"), indent=1)
    for i, (s, d, v) in enumerate(zip(scenes, durs, vos), start=1):
        label = str(s.get("slide", ""))[:44]
        print(f"  {i:>2}. {d:6.2f}s  (vo {v:5.2f}s)  {label}")
    print(f"total = {sum(durs):.2f}s")

    cmd = ["ffmpeg", "-y", "-v", "error"]
    for f in files:
        cmd += ["-i", str(f)]
    graph = (";".join(parts) + ";" + "".join(f"[a{i}]" for i in range(n)) +
             f"concat=n={n}:v=0:a=1[vo];"
             f"[vo]loudnorm=I={a.lufs}:TP=-1.5:LRA=11,aresample=48000[out]")
    cmd += ["-filter_complex", graph, "-map", "[out]",
            "-c:a", "pcm_s16le", str(out_dir / a.voice)]
    subprocess.run(cmd, check=True)
    print(f"wrote {a.timings} and out/{a.voice} - now run render.py")


if __name__ == "__main__":
    main()
