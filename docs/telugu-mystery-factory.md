# Telugu Mystery Shorts Factory

This optional MoneyPrinterTurbo workflow is designed for a Telugu YouTube Shorts channel about Indian mysteries, strange true history, unexplained events and forgotten places.

## Production model

The workflow separates visual generation from final audio while supporting two visual paths:

1. Enter an Indian mystery/history topic.
2. Generate a clean Telugu narration split into five connected ~10-second story blocks.
3. Export five continuity-locked visual prompts.
4. Choose either:
   - **FreeVideo (automatic):** generate all five 9:16 clips through a local FreeVideo CLI or a remote GPU worker.
   - **Google Flow (manual):** generate five clips in Flow and upload Scene 1 through Scene 5.
5. The page prepares the five visuals as clean video-only inputs.
6. MoneyPrinterTurbo creates one continuous Telugu narration track, optional BGM, subtitles when a Telugu-capable font is installed, and the final 9:16 Short.

This avoids the most common continuity problem with independent AI-video generations: five different voices, five different music cues and audio restarts at every cut.

## FreeVideo automatic generation

FreeVideo is the preferred zero-per-clip-cost path when a suitable GPU machine is available. The Streamlit page does not load the model itself. It calls `app/services/freevideo_backend.py`, which supports:

- **Local mode** — MoneyPrinterTurbo and FreeVideo run on the same GPU machine.
- **Remote mode** — the Render-hosted MoneyPrinterTurbo UI calls a separate GPU machine running `tools/freevideo_worker.py`.

The generated clips default to `768x1344`, 10 seconds each, with a unique deterministic seed per scene.

For setup, environment variables and worker commands, see `docs/freevideo-integration.md`.

## Continuity strategy

Every visual prompt repeats the same master visual bible. Each scene also ends on a visual anchor that the next scene is instructed to continue:

- Scene 1: location → distinctive physical anchor / doorway
- Scene 2: same anchor → practical light/object/detail
- Scene 3: matching detail → historical reconstruction → physical trace
- Scene 4: same trace → present day → upward crane/drone move begins
- Scene 5: continue that same rise → final wide reveal

The Kuldhara preset includes scene-specific Rajasthan and historical reconstruction guidance. Other topics use the same continuity structure with general Indian documentary direction.

## Telugu narration

Default Edge TTS voice:

`te-IN-MohanNeural`

Alternative:

`te-IN-ShrutiNeural`

The script prompt asks for natural spoken Telugu, immediate narration from the first second, five connected paragraphs, and careful labeling of folklore or disputed claims instead of presenting them as proven facts.

## Telugu subtitles

The repository's default fonts are not guaranteed to contain Telugu glyphs. The Factory checks for:

- `NotoSansTelugu-Bold.ttf`
- `NotoSansTelugu-Regular.ttf`
- `NotoSansTeluguUI-Bold.ttf`
- `NotoSansTeluguUI-Regular.ttf`
- `Gautami.ttf`

Place a compatible font in `resource/fonts/`.

If none is found, Telugu subtitles are disabled automatically rather than rendering missing-glyph boxes.

## Background music

The page defaults to **no BGM** until a music source you are comfortable monetizing is configured.

Supported page choices are:

- Upload one continuous BGM track
- Sonilo AI
- ElevenLabs AI
- Random bundled music

Always verify that the music you publish is licensed/eligible for your intended YouTube use. The bundled music option is explicitly labeled for copyright review.

## Files

- `app/services/telugu_mystery_factory.py` — planning, continuity prompts, Telugu font detection and video preparation
- `app/services/freevideo_backend.py` — local/remote FreeVideo client
- `tools/freevideo_worker.py` — lightweight GPU-worker HTTP API
- `webui/pages/Telugu_Mystery_Factory.py` — Streamlit workflow
- `test/services/test_telugu_mystery_factory.py` — planning and FreeVideo regression tests
- `docs/freevideo-integration.md` — FreeVideo setup guide

## First suggested topic

The page opens with:

`Kuldhara Village mystery, Rajasthan`

The preset is designed as a first-channel-video example and can be replaced with any India-focused mystery/history topic.