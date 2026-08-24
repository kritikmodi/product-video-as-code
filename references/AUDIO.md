# Voice and music

## Voice

One clip per scene, not one long take. Per-scene clips let you regenerate a single
reworded line without disturbing anything else, and they are what makes
measurement-driven timing possible.

Settings that hold up for corporate narration (ElevenLabs naming, but the ideas
carry across providers):

| Setting | Value | Why |
|---|---|---|
| stability | ~0.55 | consistent across many separate clips |
| similarity | ~0.8 | keeps the voice identity stable |
| style | ~0.1 | small amount of colour, no theatrics |
| speed | ~0.98 | slightly under 1.0 reads as considered |

Target roughly 150-160 words per minute. Much faster and it stops sounding
deliberate.

### Pronunciation

TTS reads spelling, so invented or compressed product names get mangled. Fix it
in the input, not the display: write `Sked-uler` for the model while the screen
still shows `Skedulr`.

**Verify rather than assume** - especially if you cannot listen. Run the generated
clip back through speech-to-text and read the transcript:

```
input "Skedulr"    -> transcript "Skedullr"   (wrong, one slurred word)
input "Sked-uler"  -> transcript "Skeduler"   (correct)
```

Homophones in the transcript (`Skeduler` vs `Skedjuler`) are the transcriber choosing a
spelling; both represent the same sound and both are fine. What matters is that the
name is no longer read as a single mangled token.

### Batching

If your tool derives filenames from the first words of the text, two clips opening
with the same word will collide. Generate those in separate batches and rename
between them, or you will silently ship scene 7's audio as scene 12.

## Music

### The mistake worth avoiding

Applying a fixed attenuation - `volume=-23dB` - assumes you know how loud the
source is. AI-generated beds vary enormously. One that is already quiet at source
(-27 dB), attenuated another 23 dB, then sidechain-ducked, lands around **-52 dB**:
present in the file, completely inaudible, and it will ship that way unless
someone measures it.

**Normalise the bed to a target loudness first.** Then the balance is a property of
the mix rather than of whatever the generator happened to produce.

```
bed -> loudnorm=I=<target> -> sidechain duck -> mix with voice -> final loudnorm
```

With the voice at -16 LUFS:

| Bed target | Level in gaps | Verdict |
|---|---|---|
| -26 LUFS | ~-34 dB | too shy, easy to miss |
| **-23 LUFS** | **~-31 dB** | **present, never competing** |
| -20 LUFS | ~-28 dB | starts fighting the voice |

```bash
python3 scripts/mux.py --music-lufs -23 --final out/final.mp4
```

Go quieter for a dense script with little breathing room, louder for a sparse one.

### Ducking

`sidechaincompress=threshold=0.05:ratio=4:attack=15:release=320`

Ratio 6:1 with a low threshold crushes the bed out entirely and produces audible
pumping. 4:1 dips it politely under each line and lets it return in the gaps,
which is the point of having it.

### Length

Generate a bed longer than the film so it never loops - a seam is audible even at
low level. If you must loop, `-stream_loop -1` handles it, but prefer not to.

The tail fade (`afade` reversed onto the end) is what stops the film ending on a
hard audio cut. Two seconds is usually right.

## Verifying the mix

Never ship on the assumption that it sounds right:

```bash
# whole file
ffmpeg -nostats -i out/final.mp4 -af volumedetect -f null /dev/null

# a specific window - e.g. a gap between lines, to hear whether music is there
ffmpeg -nostats -ss 12.5 -t 1.5 -i out/final.mp4 -af volumedetect -f null /dev/null
```

Peak near -1.5 dB, mean around -19 to -20 dB. If a narration gap measures below
about -40 dB, your music bed is not audible no matter what the mux reported.
