#!/usr/bin/env python3
"""Stage 4b - drive a web app and record it as video.

Two things make these read as screen recordings rather than page transitions:

1. A synthetic cursor. Playwright's screencast does not capture a pointer, so one
   is injected and driven by the same mouse events, with a click ripple.
2. Only the performance is kept. Each clip navigates, waits for real content, and
   *then* starts a timed cursor move; the load period is trimmed by keeping just
   the last `useful` seconds. No clip contains dead air or a half-painted page.

Record at the exact pixel size of the frame the footage will sit in - not at
1920x1080 then scaled down - or UI text turns to mush. See SCREEN-CAPTURE.md.

Define clips in a tours.py next to this file, or edit CLIPSET below.

    python3 scripts/capture/tour.py            # every clip
    python3 scripts/capture/tour.py dashboard  # just one
"""
import pathlib, shutil, subprocess, sys, time
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent.parent.parent / "capture"
RAW = HERE / "raw"; RAW.mkdir(parents=True, exist_ok=True)
CLIPS = HERE / "clips"; CLIPS.mkdir(parents=True, exist_ok=True)

VW, VH = 1440, 810          # must match the frame in the deck, 1:1
BASE = "https://app.example.com"   # <- point at your own app

CURSOR = """
(() => {
  if (window.__cur) return;
  const c = document.createElement('div');
  c.style.cssText = `position:fixed;left:0;top:0;width:24px;height:24px;z-index:2147483647;
    pointer-events:none;transform:translate(-100px,-100px);transition:transform 40ms linear;
    filter:drop-shadow(0 2px 3px rgba(0,0,0,.35));`;
  c.innerHTML = `<svg viewBox="0 0 26 26" width="24" height="24">
    <path d="M4 2 L4 20 L9 15.5 L12.5 23 L15.5 21.5 L12 14.5 L19 14 Z"
          fill="#fff" stroke="rgba(0,0,0,.8)" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
  document.documentElement.appendChild(c);
  window.__cur = c;
  addEventListener('mousemove', e => {
    c.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
  }, true);
  window.__ripple = (x, y) => {
    const r = document.createElement('div');
    r.style.cssText = `position:fixed;left:${x}px;top:${y}px;width:12px;height:12px;
      margin:-6px 0 0 -6px;border-radius:50%;border:2.5px solid #3bceac;z-index:2147483646;
      pointer-events:none;opacity:.95;transition:all .45s cubic-bezier(.2,.7,.3,1);`;
    document.documentElement.appendChild(r);
    requestAnimationFrame(() => {
      r.style.width='42px'; r.style.height='42px';
      r.style.margin='-21px 0 0 -21px'; r.style.opacity='0';
    });
    setTimeout(() => r.remove(), 600);
  };
})();
"""


class Driver:
    """Cursor choreography. Coordinates are viewport-relative fractions of VW/VH."""

    def __init__(self, pg):
        self.pg = pg
        self.x, self.y = VW * 0.5, VH * 0.6

    def ensure(self):
        # a single-page app can swap the document out from under the cursor
        try:
            self.pg.evaluate(CURSOR)
        except Exception:
            pass

    def glide(self, x, y, steps=26):
        self.ensure()
        self.pg.mouse.move(x, y, steps=steps)
        self.x, self.y = x, y
        self.pg.wait_for_timeout(70)

    def to(self, locator, steps=26):
        # this driver clicks raw coordinates, so the target must be on screen first
        try:
            locator.scroll_into_view_if_needed(timeout=8000)
            self.pg.wait_for_timeout(450)
        except Exception:
            pass
        box = locator.bounding_box()
        if not box:
            raise RuntimeError("element not visible")
        self.glide(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps)

    def ripple(self):
        self.ensure()
        self.pg.evaluate("([x,y]) => window.__ripple && window.__ripple(x,y)",
                         [self.x, self.y])
        self.pg.wait_for_timeout(200)

    def click(self, locator=None, settle=1200):
        if locator is not None:
            self.to(locator)
        self.ripple()
        self.pg.mouse.click(self.x, self.y)
        self.pg.wait_for_timeout(settle)

    def hold(self, ms):
        self.pg.wait_for_timeout(ms)

    def ready(self, pg, text, path):
        """Navigate, wait for real content, settle. Returns once safe to perform."""
        pg.goto(BASE + path, wait_until="networkidle", timeout=60000)
        pg.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=45000)
        pg.wait_for_timeout(1400)
        self.ensure()


def record(name, body):
    outdir = RAW / name
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir(parents=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(HERE / "profile"), headless=True,
            viewport={"width": VW, "height": VH}, device_scale_factor=1,
            record_video_dir=str(outdir),
            record_video_size={"width": VW, "height": VH},
            args=["--force-color-profile=srgb", "--hide-scrollbars"],
        )
        ctx.add_init_script(CURSOR)
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        d = Driver(pg)
        try:
            t0 = body(pg, d)          # the body returns when performing began
            useful = time.time() - t0
        finally:
            ctx.close()

    webm = next(outdir.glob("*.webm"))
    mp4 = CLIPS / f"{name}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-sseof", f"-{useful:.2f}", "-i", str(webm),
        "-r", "30", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-vf", f"scale={VW}:{VH}:flags=lanczos,fps=30",
        "-an", str(mp4)
    ], check=True)
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                       "format=duration", "-of", "csv=p=0", str(mp4)]))
    print(f"  {name}: {d:.2f}s -> {mp4}")
    return mp4


# ------------------------------------------------------------------ example clips
def c_dashboard(pg, d):
    d.ready(pg, "Dashboard", "/dashboard")
    t0 = time.time()                       # everything before this is trimmed off
    d.glide(VW * .30, VH * .30, 20); d.hold(700)
    d.glide(VW * .62, VH * .52, 30); d.hold(900)
    d.glide(VW * .80, VH * .62, 26); d.hold(1600)
    return t0


CLIPSET = {"dashboard": c_dashboard}

if __name__ == "__main__":
    for n in (sys.argv[1:] or list(CLIPSET)):
        if n not in CLIPSET:
            sys.exit(f"unknown clip {n!r}; known: {', '.join(CLIPSET)}")
        record(n, CLIPSET[n])
