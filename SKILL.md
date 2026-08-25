---
name: product-video
description: Produce product videos end to end - product demos, feature launches, explainers, walkthroughs, tutorials, release notes, onboarding and social cuts - from a script, an AI voiceover, animated HTML slides and real screen recordings, rendered deterministically to MP4 with ffmpeg. Use when asked to create, edit, re-cut, re-voice, shorten or re-brand any video about software.
---

# Product video as code

Build product videos as **code**: an HTML deck driven by a deterministic
timeline, an AI voiceover, real screen recordings of the product, and an ffmpeg
audio master. Everything is reproducible, diffable and re-renderable, so revisions
cost minutes instead of a rebuild.

This is not a video editor. It is a pipeline. The output is an MP4.

## The one idea that matters

**Audio first, then timing, then picture.**

Generate the narration before deciding how long anything is on screen. Measure each
clip, derive scene durations from those measurements, and only then render frames.
The alternatives - guessing durations, or writing narration to fit a fixed
storyboard - produce visuals that drift out of sync with the voice and force a
re-render every time a line is reworded.

```
script.json ──► TTS ──► measure ──► timings.json ──► render ──► composite ──► mux ──► MP4
                              ▲                          ▲            ▲
                        assemble.py                 render.py    composite.py
```

For a video with no narration (a title sting, a silent loop, a muted social clip),
skip stage 1 and write `timings.json` by hand. Everything downstream is unchanged.

## Pipeline

| Stage | Script | Produces |
|---|---|---|
| 1. Narration | your TTS tool of choice | `audio/vo_NN.mp3`, one per scene |
| 2. Timing + voice track | `scripts/assemble.py` | `timings.json`, `out/voice.wav` |
| 3. Picture | `scripts/render.py` | `out/silent.mp4` |
| 4. Screen footage *(optional)* | `scripts/capture/tour.py` | `capture/clips/*.mp4` |
| 5. Compositing *(optional)* | `scripts/composite.py` | `out/composited.mp4` |
| 6. Audio master | `scripts/mux.py` | final MP4 |

Read `references/PIPELINE.md` for the walkthrough, `references/AUDIO.md` for voice
and music, `references/SCREEN-CAPTURE.md` for product footage, and
`references/PITFALLS.md` before debugging anything - it lists the failures this
pipeline has actually hit.

## Kinds of video

Same pipeline throughout; what changes is structure, pacing and how much of the
frame is real product. Establish which of these you are making before writing a
line, because it decides everything else.

| Kind | Typical length | Shape | Footage |
|---|---|---|---|
| **Product explainer** | 1-3 min | problem → turn → how it works → proof → close | a little, as proof |
| **Feature launch** | 30-90s | what changed → why it matters → see it → how to get it | medium |
| **Demo / walkthrough** | 2-5 min | one real task, start to finish | dominant |
| **Tutorial** | 3-10 min | step by step, chaptered, pauses to follow along | dominant |
| **Release notes** | 30-90s | one item per beat, dense | screenshots or short clips |
| **Onboarding** | 1-3 min | the first-run path, as the user meets it | dominant |
| **Title sting / loop** | 5-20s | one idea, often silent | none |
| **Social cut** | under 60s | hook first, derived from a longer cut | short, punchy |

Rules of thumb that follow from the type:

- **Demos and tutorials are footage-first.** The deck is chrome around the product -
  title cards, callouts, chapter breaks. Do not narrate what the screen already says.
- **Explainers and launches are narration-first.** Footage appears as evidence for a
  claim you just made; that adjacency is what makes it land.
- **Tutorials need air.** Leave a beat after each step. Use `--tail` generously; a
  viewer is following along, not watching.
- **Release notes are dense.** On-screen text carries, narration summarises. One item
  per beat, no lingering.
- **Social cuts are derived, never written twice.** Build them as a scene subset of
  the long cut so they cannot drift (see PIPELINE.md).

## Quick start

Setup, once: `pip install -r requirements.txt && playwright install chromium`.
ffmpeg and ffprobe must also be on PATH.

Silent first, to check the deck renders at all:

```bash
cp templates/deck.html .
python3 scripts/render.py --preview 2 8 18   # stills
python3 scripts/render.py                    # -> out/silent.mp4
```

Then the full pipeline once narration exists:

```bash
cp templates/script.example.json script.json
# generate audio/vo_01.mp3 ... one per scene, then:
python3 scripts/assemble.py                    # timings.json + out/voice.wav
python3 scripts/render.py                      # out/silent.mp4
python3 scripts/mux.py --final out/final.mp4   # add voice (+ music if audio/bed.mp3 exists)
```

`assemble.py` is the only stage that needs audio; without it `render.py` uses the
durations declared in the deck.

## Rules that keep this working

**Never drive the timeline from wall-clock time.** The renderer seeks to an explicit
`t` and screenshots. `render.py` calls `window.__seek(t)` for each frame, so a slow
machine produces an identical file to a fast one. Anything using
`requestAnimationFrame` or CSS animation playback will tear or drop frames under a
screenshot loop.

**Pin every animation to a narration beat.** If the voice says "three things" at
4.2s, the third card appears at 4.2s. After any rewrite, re-check the beats - a line
that comes back 3s shorter will strand its visuals. This is the single biggest driver
of whether the result looks directed or generic.

**Render in resumable chunks.** `render.py` writes `out/parts/part_NNN.mp4` and skips
completed parts on re-run. A stalled screenshot costs one chunk, not the whole pass.
Never run two renders against the same parts directory.

**Measure, don't assume.** Verify with numbers, not vibes:
- blank-frame detection: count dark pixels (`(pixels < 200).mean()`), not standard
  deviation - a legitimately white-heavy UI page has low deviation too
- pronunciation: run the generated audio back through speech-to-text and read it
- levels: `ffmpeg -af volumedetect` on the final file, every time
- geometry: read `getBoundingClientRect()` out of the DOM rather than hardcoding

**One source, many cuts.** Select scene subsets from a single deck with a query
parameter (`deck.html?cut=short`) so a long demo and a 40-second social cut cannot
drift apart. See `references/PIPELINE.md`.

## Match the product's brand from its code

If the product has a codebase, read the brand out of it rather than asking for
hex codes:

```bash
python3 scripts/detect_brand.py ../their-product --css
```

It reads design token files, tailwind configs, CSS custom properties, SCSS and
Less variables, JS/TS theme objects and the web manifest, and reports the fonts,
icon library and logo files it found. Paste the `:root` block it prints into
`deck.html`.

Build output is skipped, since a `dist/` folder is full of vendored
component-library CSS that is not the brand. The palette is also checked for
coherence rather than trusted from name matches alone: a repo defining
`--surface` for its light theme and `--bg` for its dark one would otherwise give
a white card on a black frame. Rejections are printed, never applied silently.

Show the user what was detected and what was rejected before rendering.

## Design guidance

The deck is HTML/CSS, so the design is entirely yours. Two things are worth knowing:

Social and autoplay contexts run **muted**. The on-screen headline must carry each
beat on its own, and the hook has to land in the first second or two. Treat the
voiceover as enhancement, not as the delivery mechanism.

If asked for something visually distinctive, ground it in the subject's own world -
its artifacts, instruments and vernacular - rather than reaching for a dark
background with one bright accent colour, which is where generic output clusters.
Anthropic's `frontend-design` skill covers this well and composes cleanly with this
one.
