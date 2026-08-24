#!/usr/bin/env python3
"""Stage 3 - render the HTML deck to frames, deterministically.

Frames are seeked one at a time via window.__seek(t) and piped straight into
ffmpeg. Nothing is driven by wall-clock time, so a slow machine produces a
byte-comparable result to a fast one - which is what makes re-renders safe.

The timeline is rendered in fixed-size chunks so a stalled screenshot costs one
chunk rather than the whole pass; re-running resumes from the last completed part.

    python3 scripts/render.py                        # full render
    python3 scripts/render.py --cut short            # a scene subset
    python3 scripts/render.py --preview 2 8 20       # stills, for checking layout
"""
import sys, os, json, time, argparse, pathlib, subprocess
from playwright.sync_api import sync_playwright, Error as PWError

HERE = pathlib.Path(__file__).resolve().parent.parent
CHUNK = 600            # frames per resumable part
SHOT_TIMEOUT = 120_000


def encoder(path, fps):
    return subprocess.Popen([
        "ffmpeg", "-y", "-v", "error",
        "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-x264-params", "keyint=60:min-keyint=30",
        str(path),
    ], stdin=subprocess.PIPE)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--deck", default="deck.html")
    ap.add_argument("--video", default="out/silent.mp4")
    ap.add_argument("--timings", default="timings.json")
    ap.add_argument("--cut", default="", help="value for ?cut= in the deck")
    ap.add_argument("--parts", default="", help="suffix for the parts dir, to keep cuts apart")
    ap.add_argument("--fresh", action="store_true", help="discard finished chunks first")
    ap.add_argument("--preview", nargs="*", type=float, help="render stills at these times")
    ap.add_argument("--out", default="preview", help="directory for --preview stills")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()

    override = None
    tpath = HERE / args.timings
    if tpath.exists():
        override = json.load(open(tpath)).get("durations")

    parts_dir = HERE / "out" / ("parts" + (args.parts or ""))
    parts_dir.mkdir(parents=True, exist_ok=True)
    if args.fresh:
        for f in parts_dir.glob("part_*.mp4"):
            f.unlink()

    deck_url = (HERE / args.deck).as_uri() + (f"?cut={args.cut}" if args.cut else "")

    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text",
                                    "--font-render-hinting=none", "--hide-scrollbars"])
        pg = b.new_page(viewport={"width": args.width, "height": args.height},
                        device_scale_factor=1)
        pg.set_default_timeout(SHOT_TIMEOUT)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(deck_url)
        try:
            pg.wait_for_function("() => window.__total !== undefined", timeout=20000)
        except PWError:
            b.close()
            sys.exit("deck never initialised - page errors:\n  " +
                     "\n  ".join(errors or ["(none captured; check the console)"]))

        if override:
            pg.evaluate("d => window.__retime(d)", override)

        total = pg.evaluate("window.__total")
        print(json.dumps(pg.evaluate("window.__scenes")), file=sys.stderr)
        print(f"total = {total:.2f}s", file=sys.stderr)

        if args.preview:
            out = HERE / args.out
            out.mkdir(parents=True, exist_ok=True)
            for i, t in enumerate(args.preview):
                pg.evaluate("t => window.__seek(t)", t)
                pg.screenshot(path=str(out / f"prev_{i:02d}_{t:g}s.png"))
            print(f"wrote {len(args.preview)} stills to {args.out}/", file=sys.stderr)
            b.close()
            return

        n = int(round(total * args.fps))
        nchunks = (n + CHUNK - 1) // CHUNK
        t_start = time.time()

        for c in range(nchunks):
            part = parts_dir / f"part_{c:03d}.mp4"
            if part.exists() and part.stat().st_size > 0:
                print(f"chunk {c+1}/{nchunks} cached", file=sys.stderr, flush=True)
                continue
            tmp = part.with_suffix(".tmp.mp4")
            ff = encoder(tmp, args.fps)
            lo, hi = c * CHUNK, min(n, (c + 1) * CHUNK)
            for i in range(lo, hi):
                pg.evaluate("t => window.__seek(t)", i / args.fps)
                for attempt in range(3):
                    try:
                        ff.stdin.write(pg.screenshot(type="png"))
                        break
                    except PWError:
                        if attempt == 2:
                            raise
                        print(f"  retry frame {i}", file=sys.stderr, flush=True)
            ff.stdin.close(); ff.wait()
            tmp.rename(part)
            el = time.time() - t_start
            eta = (el / max(hi - lo * 0, 1)) * (n - hi)
            print(f"chunk {c+1}/{nchunks} done ({hi}/{n} frames, {hi/args.fps:.0f}s)"
                  f"  eta {eta/60:.1f}m", file=sys.stderr, flush=True)
        b.close()

    lst = HERE / "out" / ("parts" + (args.parts or "") + ".txt")
    lst.write_text("".join(f"file '{parts_dir / f'part_{c:03d}.mp4'}'\n"
                           for c in range(nchunks)))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
                    str(HERE / args.video)], check=True)
    print(f"wrote {args.video} ({n} frames)", file=sys.stderr)


if __name__ == "__main__":
    main()
