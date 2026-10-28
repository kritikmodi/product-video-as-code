# Product video as code

[![skills.sh](https://skills.sh/b/kritikmodi/product-video-as-code)](https://skills.sh/kritikmodi/product-video-as-code)

**Build product videos from your IDE instead of a video editor.**

Ask your coding agent for a demo, launch video or explainer. It writes the
script, the slides and the voiceover, and renders an MP4.

![The bundled starter deck, rendered by the pipeline](docs/demo.gif)

## Install

In Claude Code:

```
/plugin install product-video-as-code --marketplace kritikmodi/product-video-as-code
```

Any other agent (Codex, Cursor, Copilot and more):

```bash
npx skills add kritikmodi/product-video-as-code
```

You also need `ffmpeg` on your PATH.

## Use it

Just ask:

> Make a 60-second launch video for our new dashboard, with a voiceover.

Or render the starter video yourself:

```bash
pip install -r requirements.txt
playwright install chromium
cp templates/deck.html .
python3 scripts/render.py          # -> out/silent.mp4
```

The install downloads Playwright from PyPI and a headless Chromium. Rendering
makes no network calls. Narration goes to the text-to-speech service you choose.

## Why

- **Edit a line, not a timeline.** Reword a scene and re-render. No editor to
  reopen.
- **Voice first, then timing.** Slides land on the words that describe them.
- **Real product footage.** Screen recordings drop straight into the frame.
- **Same output every time.** Renders don't change with machine speed.

More in [SKILL.md](SKILL.md). Same idea for slides:
[Deckloom](https://github.com/kritikmodi/deckloom).

MIT licensed.
