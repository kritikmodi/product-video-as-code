# AGENTS.md

Instructions for any coding agent working in this repository.

This repo is a **pipeline for making software videos**: product demos, feature
launches, explainers, walkthroughs, tutorials, release notes, onboarding and
social cuts. Slides are HTML, timing is derived from the narration audio, and
ffmpeg renders the MP4.

`SKILL.md` is the full brief and is worth reading in full before you start. It is
written in Anthropic's Claude Skill format, but it is plain Markdown and applies
to any agent.

## The one rule that matters

**Audio first, then timing, then picture.**

Generate the narration before deciding how long anything is on screen. Measure
each clip, derive scene durations from those measurements, then render. Do not
guess durations and do not write narration to fit a fixed storyboard; both cause
the visuals to drift out of sync with the voice.

## Commands

```bash
# setup (once)
pip install -r requirements.txt && playwright install chromium
# ffmpeg and ffprobe must also be on PATH

# see it work, no narration or API keys needed
cp templates/deck.html .
python3 scripts/render.py --preview 2 8 18     # stills, fastest check
python3 scripts/render.py                      # -> out/silent.mp4

# full pipeline
cp templates/script.example.json script.json
# generate audio/vo_01.mp3 ... one clip per scene with any TTS provider
python3 scripts/assemble.py                    # timings.json + out/voice.wav
python3 scripts/render.py                      # out/silent.mp4
python3 scripts/mux.py --final out/final.mp4   # adds voice, and music if audio/bed.mp3 exists
```

Every script supports `--help`.

## Match the product's brand from its code

```bash
python3 scripts/detect_brand.py ../their-product --css
```

Reads tokens, tailwind, CSS variables, JS theme objects and the manifest; also
reports fonts, icon library and logos. Skips build output and rejects colours
that do not cohere, printing what it rejected. Paste the `:root` block into
`deck.html`. Show the user the result before rendering.

## Where things live

| Path | Purpose |
|---|---|
| `SKILL.md` | full brief: pipeline, kinds of video, working rules |
| `references/PIPELINE.md` | stage-by-stage walkthrough, multi-cut technique |
| `references/AUDIO.md` | voice settings, pronunciation, music levels |
| `references/SCREEN-CAPTURE.md` | recording product footage, compositing |
| `references/PITFALLS.md` | **read before debugging**: real failures and fixes |
| `scripts/` | the pipeline |
| `templates/deck.html` | starter deck and the animation engine |

## Conventions

- **Never drive the timeline from wall-clock time.** The renderer seeks to an
  explicit `t` and screenshots. Do not use `requestAnimationFrame` or CSS
  animation playback for anything that must appear in the render; it will tear
  or drop frames under a screenshot loop.
- **Pin animations to narration beats.** If the voice names the third item at
  4.2s, the third element appears at 4.2s. Re-check after any rewrite; a line
  that comes back shorter will strand its visuals.
- **Never run two renders against the same parts directory.** Check first:
  `pgrep -f render.py`.
- **Measure, do not assume.** Detect blank frames by ink coverage rather than
  variance, confirm pronunciation by transcribing generated audio back, and run
  `ffmpeg -af volumedetect` on the final file before calling it done.
- **Do not handle user credentials.** `scripts/capture/login.py` opens a browser
  so a human can sign in; the session persists in a local profile that later
  recordings reuse. Never type a password on someone's behalf.

## Do not commit

- `out/`, `preview/`, generated `.mp4` and `.wav` files
- `audio/` and `audio_*/` (generated narration and music)
- `capture/` at the repo root. It holds raw takes and a **live browser session**
  in `capture/profile/`. Note the leading slash in `.gitignore`; without it the
  rule would also exclude `scripts/capture/`, which is source.

## Style

Plain ASCII in docs and code comments. No em dashes.
