# Telugu Mystery Shorts Factory

This optional MoneyPrinterTurbo workflow is designed for a Telugu YouTube Shorts channel about Indian mysteries, strange true history, unexplained events and forgotten places.

## Production model

The workflow intentionally separates visual generation from final audio:

1. Enter an Indian mystery/history topic.
2. Generate a clean Telugu narration split into five connected ~10-second story blocks.
3. Export five continuity-locked prompts for Google Flow.
4. Generate the five 10-second visual clips separately in Flow.
5. Upload Scene 1 through Scene 5 in order.
6. The page strips any audio that Flow included in those clips.
7. MoneyPrinterTurbo creates one continuous Telugu narration track, optional BGM, subtitles when a Telugu-capable font is installed, and the final 9:16 Short.

This avoids the most common continuity problem with independent AI-video generations: five different voices, five different music cues and audio restarts at every cut.

## Continuity strategy

Every Flow prompt repeats the same master visual bible. Each scene also ends on a visual anchor that the next scene is instructed to continue:

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

The script prompt asks for natural spoken Telugu, immediate dialogue from the first second, five connected paragraphs, and careful labeling of folklore or disputed claims instead of presenting them as proven facts.

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

- Sonilo AI
- ElevenLabs AI
- Random bundled music

Always verify that the music you publish is licensed/eligible for your intended YouTube use. The bundled music option is explicitly labeled for copyright review.

## Files

- `app/services/telugu_mystery_factory.py` — planning, Flow prompts, Telugu font detection, Flow-audio stripping
- `webui/pages/Telugu_Mystery_Factory.py` — Streamlit workflow
- `test/services/test_telugu_mystery_factory.py` — planning regression tests

## First suggested topic

The page opens with:

`Kuldhara Village mystery, Rajasthan`

The preset is designed as a first-channel-video example and can be replaced with any India-focused mystery/history topic.
