# Product video as Code

Build product videos from code instead of a video editor: an animated HTML deck,
an AI voiceover, real screen recordings, and a mastered audio mix, rendered
deterministically to MP4 with ffmpeg.

Product demos, feature launches, explainers, walkthroughs, tutorials, release
notes, onboarding, title stings, social cuts - one pipeline, different shapes.

```
script.json ──► TTS ──► measure ──► timings.json ──► render ──► composite ──► mux ──► MP4
```

![The bundled starter deck, rendered by the pipeline](docs/demo.gif)

The clip above is `templates/deck.html` rendered straight through `scripts/render.py`
with no narration, no API keys and no editing - exactly what a clean clone produces
in about a minute. [Full quality MP4](https://github.com/kritikmodi/product-video-as-code/releases/download/v0.1.0/demo.mp4)
(1080p, 30fps).

## Why this exists

Video is usually the one asset an AI assistant cannot iterate on. Every revision
means reopening an editor and redoing the work by hand - so software videos go
stale the moment the product moves.

Treating video as **code** changes that. The deck is HTML, the timeline is a pure
function of `t`, and the audio is measured rather than guessed. "Reword scene 4,
add banks to the segment list, and cut it under a minute" becomes a two-minute
change instead of an afternoon. Re-shooting a demo after a UI change is a script
run, not a reshoot.

## The core idea

**Audio first, then timing, then picture.**

Generate the narration before deciding how long anything is on screen. Measure each
clip, derive scene durations from those measurements, then render. Guessing
durations - or writing narration to fit a fixed storyboard - produces visuals that
drift out of sync and forces a rebuild every time a line changes.

## Install

```bash
git clone https://github.com/kritikmodi/product-video-as-code.git
```

**Any agent.** `AGENTS.md` at the repo root is read natively by Codex, Cursor,
Copilot, Gemini CLI, Aider, Windsurf, Zed and others, so cloning it into your
project is enough.

**Claude Code / claude.ai.** Install it as a skill so it loads on demand:

```bash
cp -r product-video-as-code ~/.claude/skills/product-video
```

**No agent at all.** The scripts are plain Python calling ffmpeg and Playwright.
Nothing here imports a vendor SDK or calls a model API, so you can run the whole
pipeline by hand.

**Requirements:** Python 3.9+, `ffmpeg`/`ffprobe` on PATH, Playwright with Chromium
(`pip install playwright && playwright install chromium`), and any text-to-speech
provider.

## Try it in a minute

No narration, no API keys, no accounts. This renders the bundled starter deck to a
real 23s 1080p MP4:

```bash
pip install -r requirements.txt && playwright install chromium
cp templates/deck.html .
python3 scripts/render.py            # -> out/silent.mp4
```

Stills are faster still, if you just want to see the deck:

```bash
python3 scripts/render.py --preview 2 8 18
```

## Full pipeline, with narration

```bash
cp templates/script.example.json script.json
# edit script.json, then generate audio/vo_01.mp3 ... one clip per scene with the
# text-to-speech provider of your choice
python3 scripts/assemble.py                    # timings.json + out/voice.wav
python3 scripts/render.py                      # out/silent.mp4
python3 scripts/mux.py --final out/final.mp4   # + music if audio/bed.mp3 exists
```

`assemble.py` is the only stage that needs audio. Without it, `render.py` falls back
to the durations declared in the deck, so silent videos need no extra work.

## Kinds of video

The pipeline is the same; structure, pacing and how much of the frame is real
product are what change.

| Kind | Length | Shape | Footage |
|---|---|---|---|
| Product explainer | 1-3 min | problem → turn → how → proof → close | a little, as proof |
| Feature launch | 30-90s | what changed → why → see it → get it | medium |
| Demo / walkthrough | 2-5 min | one real task, start to finish | dominant |
| Tutorial | 3-10 min | step by step, chaptered, room to follow | dominant |
| Release notes | 30-90s | one item per beat, dense | clips or stills |
| Onboarding | 1-3 min | the first-run path | dominant |
| Title sting / loop | 5-20s | one idea, often silent | none |
| Social cut | under 60s | hook first, derived from a longer cut | short |

Demos and tutorials are footage-first - the deck is chrome around the product.
Explainers and launches are narration-first, with footage as evidence for the claim
just made. `SKILL.md` has the full guidance.

## What's here

| Path | |
|---|---|
| `SKILL.md` | the skill itself - what Claude reads |
| `scripts/assemble.py` | measure narration → scene timings + voice track |
| `scripts/render.py` | deterministic, resumable frame renderer |
| `scripts/composite.py` | overlay screen recordings into a measured DOM rect |
| `scripts/mux.py` | ducked music bed + broadcast-level master |
| `scripts/detect_brand.py` | read colours, fonts, icons and logos out of a codebase |
| `scripts/capture/` | log in by hand, then record the product with a synthetic cursor |
| `templates/deck.html` | starter deck with the animation engine |
| `references/` | pipeline, audio, screen capture, and pitfalls |

## Techniques

**Deterministic rendering.** The renderer seeks to an explicit `t` and screenshots.
No wall-clock, no `requestAnimationFrame` - a slow machine produces the same file as
a fast one.

**Resumable chunks.** Frames render in parts; a stall costs one chunk, not the pass.

**Beat-matched animation.** Elements land on the words that describe them. This is
most of the difference between a directed video and a slideshow.

**One source, many cuts.** A long demo and a social cut share a deck and are selected
with `?cut=short`, so they cannot drift apart.

**Screen recordings that read as real.** Playwright captures no cursor, so one is
injected. Record at the exact pixel size of the frame it will occupy - scaling a
1920 capture into a smaller frame destroys UI text.

**Audio that is actually audible.** Normalise the music bed to a loudness target
before ducking. A fixed dB attenuation on a quiet generated bed produces a track
that is present in the file and inaudible in the room.

**Brand detected, not guessed.** `detect_brand.py` reads the palette, fonts,
icon library and logos out of the product's own codebase, skips build output, and
rejects colours that do not cohere rather than silently producing a white card on
a black frame.

**Verify, don't assume.** Detect blank frames by ink coverage, not variance. Confirm
pronunciation by transcribing the generated audio back. Measure levels on the file
you are about to ship.

`references/PITFALLS.md` documents the failures behind each of these, including a
keyframe-engine bug that makes elements appear from frame zero, and why a
double-escaped apostrophe silently breaks a whole deck.

## Composing with other skills

Pairs well with Anthropic's [`frontend-design`](https://github.com/anthropics/skills/tree/main/skills/frontend-design)
for visual direction - the deck is plain HTML/CSS, so design guidance applies
directly.

If you want React composition and faster renders, the
[claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit)
covers Remotion and generative assets. This skill deliberately stays
dependency-light: plain HTML means anyone can open the deck and edit copy without a
toolchain, which matters for brand work where exact assets and colours are
non-negotiable.

## Related

The same idea applied to slides: [Deckloom](https://github.com/kritikmodi/deckloom)
builds pitch decks, one-pagers and sales decks from a JSON content file and one
HTML design file, rendered to PDF and PPTX.

## License

MIT (c) 2026 Kritik Modi - see [LICENSE](LICENSE).

<!--
GitHub repo description (About field, set in repo settings):
Product videos from code, not a video editor. HTML slides, AI voiceover and screen
recordings, rendered to MP4.

Suggested topics: claude-skill, claude-code, video, ffmpeg, playwright,
text-to-speech, screen-recording, devrel, developer-marketing, video-as-code
-->
