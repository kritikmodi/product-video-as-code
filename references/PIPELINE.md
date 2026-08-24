# Pipeline

## Why it is shaped this way

A video is a function of time. If every visual state is derived from an explicit
`t`, the render is reproducible, resumable and diffable, and a revision costs a
re-render rather than a rebuild. Everything here follows from that.

## 1. Script

`script.json` holds one entry per scene: what is on screen, and the exact words.

```json
{
  "voice": "which voice / model you used",
  "scenes": [
    { "i": 1, "slide": "Headline on screen", "vo": "The words that are spoken." }
  ]
}
```

Keep the spoken line in the same file as the slide it belongs to. When someone
asks for a rewrite you change one field, regenerate one audio clip, and re-run -
rather than hunting for which clip matched which slide.

**Write for muted playback** if this is going to social or an autoplay context. The
headline has to carry the beat alone; the voiceover is enhancement.

**Do not narrate what the screen already says.** In a demo or tutorial the footage is
the content; narration should add intent ("now we promote it to production"), not
read the UI aloud. In an explainer or launch the reverse holds - narration leads and
footage arrives as evidence.

**Spell for the ear, not the eye.** TTS reads what you write. Product names that
are compressed or invented get mangled - `Skedulr` came out as one slurred word
until it was written `Sked-uler` in the TTS input. The on-screen spelling stays
correct; only the input to the model changes. Verify by transcribing the result
(see AUDIO.md).

## 2. Narration and timing

Generate one clip per scene into `audio/vo_NN.mp3`, then:

```bash
python3 scripts/assemble.py
```

This measures every clip and computes each scene's duration:

```
duration = max(LEAD + narration + TAIL, MIN[scene]) + EXTRA[scene]
```

| Knob | Purpose | Sensible default |
|---|---|---|
| `--lead` | beat before the voice starts | 0.35 - 0.45s |
| `--tail` | beat after it ends | 0.55 - 0.85s |
| `--tail-last` | hold on the closing card | 1.4 - 2.6s |

Pacing differs by kind of video. A tutorial viewer is following along and needs room;
a release-notes reel should not linger:

| Kind | `--lead` | `--tail` |
|---|---|---|
| Release notes, social cut | 0.30 | 0.45 |
| Explainer, feature launch | 0.38 | 0.60 |
| Demo / walkthrough | 0.40 | 0.80 |
| Tutorial | 0.45 | 1.20 |
| `--min "3:3.3"` | floor for a scene whose line is very short | as needed |
| `--extra "6:6.3"` | hold beyond the narration, e.g. on screen footage | as needed |

It writes `timings.json` and a loudness-normalised `out/voice.wav` with each line
placed in its own slot.

**To shorten a film, tighten these first.** Trimming `--tail` from 0.85 to 0.60
across fourteen scenes recovers ~4s without touching a single word, and without
speeding up the read - a rushed narrator undoes a professional tone faster than
almost anything else.

## 3. Picture

```bash
python3 scripts/render.py
```

The deck exposes `window.__seek(t)`; the renderer calls it once per frame and
screenshots. Output goes to `out/parts/part_NNN.mp4`, then concatenates.

Re-running skips completed chunks. **Never run two renders against the same parts
directory** - deleting it while another render is mid-write corrupts both.

Check layout cheaply before committing to a full pass:

```bash
python3 scripts/render.py --preview 2 8 18 24
```

## 4. Pinning animation to narration

This is what separates a directed film from a slideshow. If the voice says
"three things" and the three cards appear in the first second, it reads as
generic; if each card lands as it is named, it reads as intentional.

Work out where each beat falls inside the line, then set `at` and `stagger` to
match. After any rewording, re-check - a line that comes back 3s shorter will
strand its visuals past the end of the scene.

Symptoms that the timing has drifted:
- elements still animating in after the narration for that scene has finished
- a scene whose last element appears after `duration`, so it never shows at all
- long silent stretches where nothing moves

## 5. Multiple cuts from one source

A 3-minute film and a 40-second social cut should not be two files that drift
apart. Keep one deck, define both scene lists, and select with a query parameter:

```js
const MAIN_END = SCENES.length;
/* ... define the short cut's scenes ... */
const cut = new URLSearchParams(location.search).get('cut') || 'main';
const RANGES = {main:[0,MAIN_END], short:[MAIN_END,SCENES.length]};
const [a,b] = RANGES[cut] || RANGES.main;
const keep = SCENES.slice(a,b);
SCENES.length = 0; keep.forEach(x => SCENES.push(x));
```

Splice before any DOM is built, so only the selected scenes are constructed. Then
give each cut its own script, audio directory, timings and parts directory:

```bash
python3 scripts/assemble.py --script script_short.json --audio audio_short \
    --timings timings_short.json --voice voice_short.wav
python3 scripts/render.py --cut short --parts _short \
    --timings timings_short.json --video out/silent_short.mp4
```

## 6. Delivery

`mux.py` produces the final file. Always verify what you shipped:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 out/final.mp4
ffmpeg -nostats -i out/final.mp4 -af volumedetect -f null /dev/null
```

Peak should land near -1.5 dB. Silence where narration belongs, or a peak below
-4 dB, means something upstream went wrong.
