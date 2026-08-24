#!/usr/bin/env python3
"""Stage 5 - drop recorded screen footage into the rendered deck.

The deck paints a black "screen" area inside a browser-chrome frame. This reads
that rect straight out of the DOM - rather than trusting a hardcoded number that
silently rots when the CSS changes - and overlays the footage there.

Compositing with ffmpeg instead of embedding <video> in the page keeps the
frame-by-frame render deterministic: seeking a video element per screenshot is
where torn and duplicated frames come from.

Requires the deck to expose:
    window.__overlays = [{scene, at, rect:[x,y,w,h]}, ...]
where `at` is the absolute time the footage should start.
"""
import argparse, json, pathlib, shutil, subprocess, sys
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent.parent
OUT = HERE / "out"
CLIPS = HERE / "capture" / "clips"
XFADE = 0.5    # crossfade between clips within one sequence
EDGE = 0.35    # fade from / to the black screen


def dur(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)]))


def build_sequence(name, clips, clip_len):
    """Crossfade a scene's clips into one continuous take."""
    out = OUT / f"seq_{name}.mp4"
    paths = [CLIPS / f"{c}.mp4" for c in clips]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        sys.exit(f"missing footage: {', '.join(missing)} (run capture/tour.py)")
    if len(paths) == 1:
        shutil.copy(paths[0], out)
        return out, dur(out)

    lens = [min(clip_len, dur(p)) for p in paths]
    total = lens[0]
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p in paths:
        cmd += ["-t", str(clip_len), "-i", str(p)]
    graph, prev = "", "[0:v]"
    for i in range(1, len(paths)):
        graph += (f"{prev}[{i}:v]xfade=transition=fade:duration={XFADE}:"
                  f"offset={total - XFADE:.3f}[x{i}];")
        prev = f"[x{i}]"
        total += lens[i] - XFADE
    cmd += ["-filter_complex", graph.rstrip(";"), "-map", prev,
            "-c:v", "libx264", "-preset", "slow", "-crf", "16",
            "-pix_fmt", "yuv420p", "-r", "30", str(out)]
    subprocess.run(cmd, check=True)
    return out, dur(out)


def measure(deck, cut, timings_file):
    """Read overlay times and the true painted rect out of the live DOM."""
    timings = json.load(open(HERE / timings_file))["durations"]
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto((HERE / deck).as_uri() + (f"?cut={cut}" if cut else ""))
        pg.wait_for_function("() => window.__total !== undefined")
        pg.evaluate("d => window.__retime(d)", timings)
        overlays = pg.evaluate("window.__overlays") or []
        for o in overlays:
            pg.evaluate("t => window.__seek(t)", o["at"])
            o["rect"] = pg.evaluate("""() => {
                const s = [...document.querySelectorAll('.scene.on .pframe .screen')].pop();
                if (!s) return null;
                const b = s.getBoundingClientRect();
                return [Math.round(b.x), Math.round(b.y),
                        Math.round(b.width), Math.round(b.height)]; }""")
        b.close()
    return [o for o in overlays if o.get("rect")]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deck", default="deck.html")
    ap.add_argument("--cut", default="")
    ap.add_argument("--timings", default="timings.json")
    ap.add_argument("--video", default="silent.mp4")
    ap.add_argument("--out", default="composited.mp4")
    ap.add_argument("--clip-len", type=float, default=3.15,
                    help="trim each clip to this many seconds (they end on a static hold)")
    ap.add_argument("--sequences", default="",
                    help='scene->clips, e.g. "6:workflows+graph,9:apps+excel"')
    a = ap.parse_args()

    seqmap = {}
    for entry in filter(None, a.sequences.split(",")):
        scene, clips = entry.split(":")
        seqmap[int(scene)] = clips.split("+")
    if not seqmap:
        sys.exit('nothing to composite - pass --sequences "6:clip_a+clip_b"')

    src = OUT / a.video
    if not src.exists():
        sys.exit(f"render the deck first - missing {src}")

    overlays = measure(a.deck, a.cut, a.timings)
    if not overlays:
        sys.exit("deck exposed no overlays; check window.__overlays and .pframe .screen")

    inputs, filters, prev = ["-i", str(src)], [], "[0:v]"
    for k, o in enumerate(overlays, start=1):
        if o["scene"] not in seqmap:
            continue
        seq, d = build_sequence(f'{a.cut or "main"}_{o["scene"]}',
                                seqmap[o["scene"]], a.clip_len)
        x, y, w, h = o["rect"]
        at = o["at"]
        inputs += ["-i", str(seq)]
        filters.append(
            f"[{k}:v]scale={w}:{h},fade=t=in:st=0:d={EDGE},"
            f"fade=t=out:st={d-EDGE:.3f}:d={EDGE},setpts=PTS-STARTPTS+{at:.3f}/TB[c{k}]")
        filters.append(
            f"{prev}[c{k}]overlay=x={x}:y={y}:eof_action=pass:"
            f"enable='between(t,{at:.3f},{at+d:.3f})'[v{k}]")
        prev = f"[v{k}]"
        print(f"  scene {o['scene']}: {d:.2f}s of footage at {at:.2f}s, rect {o['rect']}")

    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs,
                    "-filter_complex", ";".join(filters), "-map", prev,
                    "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(OUT / a.out)], check=True)
    print(f"wrote out/{a.out}")


if __name__ == "__main__":
    main()
