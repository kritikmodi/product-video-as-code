# Recording product footage

Real UI footage is what turns a claim into evidence. A mock code sample says the
product works; the actual job running says it does.

How much of the frame it occupies depends on what you are making. In a demo,
tutorial or onboarding video the footage *is* the content and the deck is chrome
around it - title cards, callouts, chapter breaks. In an explainer or launch it
appears in short bursts as proof of a claim just made. Record accordingly: a
walkthrough wants long continuous takes of a real task; an explainer wants several
3-4s clips of specific moments.

## Credentials

**Do not type someone's password.** An assistant driving this pipeline should not
be handling credentials, and does not need to. `capture/login.py` opens a real
browser, the human signs in, and the session persists in a local Chromium profile
that every later recording reuses.

```bash
python3 scripts/capture/login.py https://app.example.com/login
python3 scripts/capture/tour.py
```

`capture/profile/` contains a live session. It is gitignored. Keep it that way.
Sessions expire; re-run `login.py` when they do.

## Record at the size it will be displayed

The single most consequential choice here.

If the footage sits in a 1440x810 frame in the deck, **record at 1440x810**. A
1920-wide capture scaled down to fit loses 44% of its horizontal resolution and
table text turns to mush. Recording at native frame size gives 1:1 pixel mapping
and stays crisp.

This also means the aspect ratio of the deliverable constrains the footage. Square
or vertical social crops cost horizontal resolution, which is exactly what UI
screenshots cannot spare - so a 16:9 cut is often the right call *because* it keeps
the product legible, not out of laziness.

## Making it read as a recording

Playwright's screencast captures no pointer. Without one, clips read as abrupt page
transitions rather than someone using the product. `tour.py` injects a synthetic
cursor driven by the same mouse events, plus a click ripple.

Movement should be unhurried: glide, pause on the thing worth noticing, glide on.
`steps=26` on a move and a 700-1600ms hold is a good baseline.

## Cut the dead air

Never record straight through a page load. The pattern is:

1. navigate
2. **wait for real content** - a specific string that only exists once the page has
   painted, not a fixed sleep
3. settle briefly
4. mark the time, then perform
5. keep only the performed tail (`ffmpeg -sseof -<seconds>`)

Waiting on a fixed timeout instead of on content is how a clip ends up with several
seconds of blank white page in the middle of the film.

Prefer several short single-page clips over one long multi-page tour. Short clips
give exact control over length, and a slow navigation in the middle of a long take
ruins the whole recording rather than one clip.

## Compositing

`composite.py` overlays clips into a frame drawn by the deck, reading the target
rect out of the live DOM rather than trusting a hardcoded number.

Two rules:

**The frame must not move.** A scene carrying an overlay gets `noDrift`, disabling
the subtle scale drift other scenes use, because an ffmpeg overlay is fixed in
absolute pixels and would slide off a moving frame.

**Fade to the screen colour.** The deck paints the screen area black and clips fade
in and out to black, so the transition is invisible.

Why ffmpeg rather than a `<video>` element in the deck: seeking a video element per
screenshot is unreliable across thousands of frames and produces torn or duplicated
frames. Compositing afterwards keeps the frame-by-frame render deterministic.

## Check what you actually recorded

Detect blank frames by **ink coverage**, not standard deviation:

```python
a = np.array(Image.open(f).convert('L'))
ink = (a < 200).mean() * 100     # % non-background pixels
```

A legitimately white-heavy admin page has low standard deviation, so a
deviation-based check flags it as blank and sends you chasing a bug that is not
there. Ink coverage distinguishes a white page with content from an empty one.

## Before it goes public

Recordings of a shared environment show whatever is in it - colleagues' names,
internal project names, real costs. Fine for an internal demo; worth a cleaned-up
environment before a named prospect sees it. Check the frames, not just the flow.
