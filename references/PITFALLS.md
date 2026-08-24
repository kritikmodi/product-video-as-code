# Pitfalls

Every one of these was hit in production. They are ordered by how long each took
to find, not by severity.

## The timeline engine paints the wrong thing from frame zero

**Symptom:** an element that should fade in at 9s is visible from the scene's first
frame.

**Cause:** the engine applies every timeline entry each frame and clamps progress to
`[0,1]`. A *second* entry on the same element - a fade-out, say - clamps to its
`from` value (opacity 1) before its start time, overriding the entry that should be
in charge.

**Fix:** only the first entry registered for an element may paint before its own
start time.

```js
const primary = !sc.tl.some(e => e.el === n);   // at registration
...
if (!e.primary && lt < e.at) return;            // when applying
```

Any keyframe engine that layers multiple entries per element needs this. It looks
like a CSS problem and is not.

## A JavaScript string terminates early

**Symptom:** the deck never initialises; `window.__total` is undefined and the
renderer times out waiting.

**Cause:** an over-escaped apostrophe. Writing `\\'` into the file produces an
escaped backslash followed by a quote that closes the string.

**Fix:** capture the page error instead of guessing.

```python
pg.on("pageerror", lambda e: errors.append(str(e)))
```

`render.py` does this and reports it rather than hanging. Worth wiring in early -
"missing ) after argument list" points straight at the line.

## Two renders, one parts directory

**Symptom:** `FileNotFoundError` renaming `part_000.tmp.mp4`, and output that is
some blend of two versions.

**Cause:** starting a render while another is still running, then clearing the
shared parts directory out from under it.

**Fix:** check before starting.

```bash
pgrep -f render.py && echo BUSY || python3 scripts/render.py --fresh
```

Backgrounding with `nohup ... &` returns exit 0 immediately - that is the shell
forking, not the render finishing. Do not read it as success.

## Standard deviation is a bad blank-frame detector

**Symptom:** QA flags a perfectly good frame as blank.

**Cause:** a white-heavy admin UI has low pixel variance, just like an empty page.

**Fix:** count non-background pixels (see SCREEN-CAPTURE.md). Then *look* at the
frame before acting on the metric.

## Clicking coordinates that are off screen

**Symptom:** the tour clicks nothing and the subsequent wait times out.

**Cause:** a driver that clicks raw coordinates from `bounding_box()` does not
auto-scroll the way Playwright's own `.click()` does. At a shorter viewport the
target sits below the fold with coordinates outside the viewport.

**Fix:** `locator.scroll_into_view_if_needed()` before reading the box.

## `global` after first use

```python
def main():
    ap.add_argument("--clip-len", default=CLIP_LEN)   # reads the global
    global CLIP_LEN                                    # SyntaxError
```

Python requires the declaration before any use in the function. Put `global` on the
first line of the body.

## The music that is present and inaudible

Covered in AUDIO.md. Worth repeating because the mux reports success and the file
looks correct: a fixed dB attenuation on an already-quiet generated bed lands
around -52 dB. Normalise to a loudness target, then measure a narration gap.

## Scratch directories are not durable

Session scratch space can be cleared between sessions. A pipeline script vanished
mid-project while the rendered intermediates survived. Keep anything you would mind
rewriting in a real repository.

## Things that are not bugs

- **A blank first frame** at `t=0` before the first animation starts. Expected.
- **A 1px offset** between a declared overlay rect and the painted one, caused by a
  border. Measure the DOM instead of hardcoding and it stops mattering.
- **Different transcriptions** of the same audio (`Skeduler` / `Skedjuler`). Homophones;
  the pronunciation is identical.
