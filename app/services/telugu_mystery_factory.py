"""Telugu Mystery Shorts planning helpers for MoneyPrinterTurbo.

Adds a retention-focused five-scene planning layer for Indian mystery/history
Shorts while leaving the core MoneyPrinterTurbo renderer untouched.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from app.services import llm
from app.utils import utils

CHANNEL_SYSTEM_PROMPT = r"""
You are the senior writer for an Indian YouTube Shorts channel about real Indian mysteries,
strange history, unexplained events and forgotten places.

Write ONLY narration in clean, natural spoken Telugu suitable for viewers in India.
The narrator is a professional documentary storyteller, not a horror actor.

Hard rules:
- Exactly 5 paragraphs.
- Each paragraph should be speakable in roughly 8.5 to 10 seconds at a brisk natural pace.
- Total target runtime: about 45 to 50 seconds.
- Start the hook immediately in the first words; no greeting or channel intro.
- Maintain one continuous story. Each paragraph must naturally lead into the next.
- Paragraph 1: immediate curiosity hook + identify the place/event.
- Paragraph 2: establish the verified historical situation.
- Paragraph 3: introduce the best-known account/legend and label it as an account/legend.
- Paragraph 4: escalate with the unresolved question or competing explanation.
- Paragraph 5: concise payoff + one natural comment question.
- Never state folklore, rumours, curses, paranormal claims, or disputed stories as proven fact.
- Prefer historically defensible phrasing such as “స్థానిక కథనం ప్రకారం”, “చెబుతారు”,
  “చరిత్రకారుల అభిప్రాయం ప్రకారం” when certainty is limited.
- No English filler unless a proper noun genuinely needs it.
- No labels such as Scene 1, Hook, Narrator, or CTA in the output.
- No markdown.
""".strip()

SCRIPT_REQUIREMENTS = r"""
Make this especially retention-focused for a vertical Short: short clauses, concrete imagery,
no dead air, no repeated facts, and a new piece of information every few seconds.
The final question should invite genuine discussion, not sound like clickbait.
""".strip()

MASTER_VISUAL_BIBLE = r"""
FORMAT: 9:16 vertical, exactly 10 seconds, 24fps cinematic motion blur, photorealistic Indian
historical documentary thriller. Fast-paced but physically believable camera motion.
No blank frames, no logos, no subtitles baked into the generated footage, no watermarks.

LOOK: full-frame cinema camera, mostly 24mm and 35mm lenses, realistic depth of field,
high dynamic range, natural textures, restrained film grain. Grounded realism, not fantasy.
For Rajasthan/desert subjects use warm amber highlights with teal-blue shadow separation;
for other Indian locations preserve the same cinematic contrast while matching local climate.

CONTINUITY: every generated clip is part of ONE 50-second film. Preserve location geography,
time of day, weather, architecture, wardrobe period, lens language, movement direction,
color grade and dust/haze density. Never introduce a new visual style between clips.

HISTORICAL SAFETY: authentic Indian architecture, clothing and props appropriate to the
period. No modern objects in historical reconstructions. No ghosts, monsters, glowing eyes,
cheap horror imagery or Bollywood-style exaggeration unless the story itself explicitly
requires a clearly-labeled dramatization.

CAMERA RHYTHM: visually meaningful change about every 1.5–2.0 seconds, connected by
motivated movement or match cuts. Avoid random montage editing.

GOOGLE FLOW AUDIO POLICY: VISUALS ONLY. Do not generate dialogue, narration, music or sound
effects in Flow. MoneyPrinterTurbo will add ONE continuous Telugu voice track, ONE continuous
BGM bed and final audio mix after all five clips are assembled.
""".strip()

BGM_PROMPT = (
    "Indian cinematic historical mystery documentary score, 92 BPM, D minor, restrained "
    "low tanpura-like atmospheric drone, subtle cello and bass texture, light heartbeat-style "
    "percussion, sparse metallic ambience, suspenseful but not horror, no vocals, continuous "
    "slow build for a 50-second vertical short, leave space for clear Telugu narration"
)

FLOW_BRIDGES = [
    "OPEN on a strong location-defining shot already in motion. End on a distinctive physical story object or doorway filling much of frame, with the camera still moving toward it. That exact object is the continuity anchor for the next clip.",
    "OPEN as if the camera has just continued through/past the exact physical anchor from the previous clip. Preserve movement direction and lens height. End on a close-up of a practical light source, reflective object, document, symbol, or textured detail that can support a match cut into a historical reconstruction.",
    "OPEN on the exact close-up/match-cut anchor from the previous clip and transition into a restrained historical reconstruction. End on one simple physical trace—footprints, dust, a document edge, stone texture, or another grounded detail—with motion continuing.",
    "OPEN on that exact physical trace and use it to transition back to the present-day location. Escalate scale and tension without supernatural imagery. End while the camera has clearly begun a slow upward crane/drone rise. Do not complete the rise.",
    "OPEN already continuing the same upward crane/drone rise from the previous clip. Reveal the full location, then finish on a memorable wide composition with subtle continued movement and clean visual space for an editor-added final caption. No fade to black.",
]

KULDHARA_SCENE_NOTES = [
    "Kuldhara village, Rajasthan, authentic abandoned sandstone ruins at late sunset; dry Thar Desert wind and fine sand crossing the lane.",
    "Continue inside the same abandoned Kuldhara sandstone structures; empty lanes, cracked walls, clay vessels and weathered wooden doorways; no present-day people.",
    "Historically plausible early-19th-century Rajasthan reconstruction; Paliwal Brahmin families in restrained earth-tone period clothing leaving quietly at night with small cloth bundles; no fantasy costumes.",
    "Return seamlessly to present-day Kuldhara at blue hour/nightfall; empty lanes and ruins, wind-blown sand, no ghosts; emphasize uncertainty around the curse legend rather than depicting it as real.",
    "Continue the same rising camera over Kuldhara; reveal the scale of the abandoned sandstone settlement surrounded by desert; finish on a grounded documentary-wide view.",
]

KULDHARA_CLIP_CONTINUITY = [
    (
        "Exact opening frame: a shoulder-height 35mm view moving forward down a narrow, empty lane of authentic Kuldhara sandstone ruins at late sunset. The dark, distinctive sandstone doorway is already visible straight ahead.",
        "0–2s: immediate forward move through the empty lane, wind lifting a thin veil of sand. 2–5s: pass close to cracked honey-gold sandstone walls and one weathered carved lintel. 5–8s: the camera centers the same dark rectangular doorway; no people, signs, lights or modern objects. 8–10s: continue the push until the doorway fills frame and the lens crosses its threshold.",
        "Exact ending frame: camera halfway through the dark sandstone doorway, same forward motion, warm sunset edge light behind and cool shadow inside.",
        "Next-scene anchor: this exact dark doorway and forward camera movement; Scene 2 must begin at this threshold and continue inside.",
    ),
    (
        "Exact opening frame: match Scene 1's final frame—the same dark rectangular Kuldhara sandstone doorway, same shoulder-height 35mm lens, same forward movement crossing into the dim interior at late sunset.",
        "0–2s: finish crossing the threshold without a cut in direction. 2–5s: reveal one small, empty sandstone room with rough walls and dust in the same amber edge light. 5–8s: drift past a single old clay oil lamp on a low stone ledge; no other props are introduced. 8–10s: push into a close-up of the lamp and its small natural flame.",
        "Exact ending frame: tight close-up of the clay oil lamp wick and steady flame, the wick centered, shallow depth of field, no visible people.",
        "Next-scene anchor: the centered lamp wick/flame; Scene 3 must open on the same composition and match-cut from this lamp into a clearly illustrative historical reconstruction.",
    ),
    (
        "Exact opening frame: reproduce Scene 2's final close-up—the same clay lamp, centered wick and small flame, same warm light and shallow focus. No new location or prop appears in the first frame.",
        "0–2s: hold the same lamp composition, then use a motivated match cut from its flame to a practical oil lamp in an early-19th-century Kuldhara home. 2–5s: reveal a historically restrained, clearly illustrative reconstruction of Paliwal Brahmin families in period-appropriate earth-tone Rajasthani clothing preparing small cloth bundles at dusk. 5–8s: follow them quietly along a sandstone lane; do not depict the disputed minister story as fact. 8–10s: tilt down to their fresh footprints in desert sand, ending with footprints filling the lower center of frame.",
        "Exact ending frame: close view of several fresh footprints crossing fine desert sand, low camera, the last footprint centered, a light breeze just beginning to move grains.",
        "Next-scene anchor: these exact footprints, their direction and low camera height; Scene 4 must start on the same prints as wind begins covering them.",
    ),
    (
        "Exact opening frame: match Scene 3's final frame—the same footprints crossing fine sand, same low camera height and direction. Wind is already moving a few grains across the centered print.",
        "0–2s: continue the same footprints while wind gradually softens their edges. 2–4s: let blowing sand fill the frame for a natural match transition. 4–7s: reveal the present-day Kuldhara lane at the same late-sunset-to-blue-hour moment, with the same sandstone ruins, haze and color grade; no ghosts or people. 7–10s: begin a slow, physically plausible crane rise above the lane, moving forward in the same direction; stop before the full village is revealed.",
        "Exact ending frame: camera has risen only a little above the lane and is still moving upward and forward; the Kuldhara roofs and ruin walls are beginning to drop lower in frame.",
        "Next-scene anchor: the same upward-and-forward crane movement, heading and dusk sky; Scene 5 must begin mid-rise without restarting or changing lens direction.",
    ),
    (
        "Exact opening frame: continue Scene 4's final image and motion—the same low aerial/crane position over Kuldhara, already rising and moving forward, same 24mm lens, same late-sunset blue-hour sky and dust haze.",
        "0–2s: continue the rise without a jump in height or direction. 2–5s: clear the roofline and reveal more of the authentic sandstone settlement in one continuous move. 5–8s: widen to show the abandoned village and surrounding Thar Desert, grounded in real geography and natural scale. 8–10s: settle into a memorable documentary-wide composition with subtle camera drift and uncluttered sky/ground for an editor-added Telugu question.",
        "Exact ending frame: wide, photorealistic view of Kuldhara's sandstone ruins against the desert at dusk; camera still drifting gently, no fade to black, no text.",
        "Final handoff: hold this same wide reveal with clean visual space for the editor's final question/CTA caption; there is no next clip.",
    ),
]

TELUGU_FONT_CANDIDATES = (
    "NotoSansTelugu-Bold.ttf",
    "NotoSansTelugu-Regular.ttf",
    "NotoSansTeluguUI-Bold.ttf",
    "NotoSansTeluguUI-Regular.ttf",
    "Gautami.ttf",
)


@dataclass
class MysteryPlan:
    topic: str
    narration: str
    narration_parts: list[str]
    master_visual_bible: str
    bgm_prompt: str
    flow_prompts: list[str]
    recommended_voice: str = "te-IN-MohanNeural"
    video_language: str = "te-IN"
    aspect_ratio: str = "9:16"
    clip_seconds: int = 10


def _clean_text(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def split_into_five(text: str) -> list[str]:
    text = _clean_text(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    if len(paragraphs) == 5:
        return paragraphs

    sentences = _split_sentences(text)
    if len(sentences) < 5:
        words = text.split()
        if len(words) < 10:
            raise ValueError("Narration is too short to split into five scenes")
        boundaries = [round(len(words) * i / 5) for i in range(6)]
        return [
            " ".join(words[boundaries[i] : boundaries[i + 1]]).strip()
            for i in range(5)
        ]

    groups: list[list[str]] = [[] for _ in range(5)]
    total_chars = sum(len(sentence) for sentence in sentences)
    target = max(1, total_chars / 5)
    group_index = 0
    current_chars = 0
    for index, sentence in enumerate(sentences):
        remaining_sentences = len(sentences) - index
        remaining_groups = 5 - group_index
        if (
            group_index < 4
            and groups[group_index]
            and current_chars >= target
            and remaining_sentences >= remaining_groups
        ):
            group_index += 1
            current_chars = 0
        groups[group_index].append(sentence)
        current_chars += len(sentence)

    for index in range(4, -1, -1):
        if groups[index]:
            continue
        donor = next(
            (j for j in range(index - 1, -1, -1) if len(groups[j]) > 1),
            None,
        )
        if donor is None:
            raise ValueError("Could not split narration into five non-empty scenes")
        groups[index].insert(0, groups[donor].pop())

    return [" ".join(group).strip() for group in groups]


def generate_telugu_narration(topic: str) -> str:
    script = llm.generate_script(
        video_subject=topic,
        language="te-IN",
        paragraph_number=5,
        video_script_prompt=SCRIPT_REQUIREMENTS,
        custom_system_prompt=CHANNEL_SYSTEM_PROMPT,
    )
    script = _clean_text(script)
    if not script or script.startswith("Error: "):
        raise RuntimeError(script or "The configured LLM did not return narration")
    return script


def _scene_notes(topic: str) -> list[str]:
    normalized = topic.casefold()
    if "kuldhara" in normalized or "కుల్ధర" in topic:
        return KULDHARA_SCENE_NOTES
    return [
        f"Establish the real Indian location/event for '{topic}' with a visually immediate, factual documentary hook.",
        f"Show grounded environmental or archival details that visually explain the verified setup of '{topic}'.",
        f"Create a restrained period reconstruction or evidence-focused visualization for the account described in the narration about '{topic}'.",
        f"Return to present-day/evidence imagery for '{topic}' and visually contrast the competing explanation or unresolved question.",
        f"Reveal the broader location/context of '{topic}' and finish with a strong documentary-wide payoff rather than a horror cliché.",
    ]


def build_scene_prompts(topic: str, narration_parts: Iterable[str]) -> list[str]:
    parts = list(narration_parts)
    if len(parts) != 5:
        raise ValueError("Exactly five narration parts are required")

    notes = _scene_notes(topic)
    prompts = []
    kuldhara = "kuldhara" in topic.casefold() or "కుల్ధర" in topic
    for index, (narration, note, bridge) in enumerate(
        zip(parts, notes, FLOW_BRIDGES), start=1
    ):
        if kuldhara:
            opening, timeline, ending, next_anchor = KULDHARA_CLIP_CONTINUITY[index - 1]
        else:
            opening = "Exact opening frame: begin on the visual anchor described for this story and continue the previous scene's camera direction, lens height, time of day, color grade and weather."
            timeline = "0–2s: establish the immediate story detail. 2–5s: move closer with one motivated camera move. 5–8s: reveal the next factual visual clue. 8–10s: finish on the stated continuity anchor, with motion still motivated."
            ending = "Exact ending frame: a clear, physically plausible view of the scene-specific story anchor, with no text and no fade."
            next_anchor = "Next-scene anchor: preserve this exact object/composition and the same camera direction as the next clip's first frame."
        prompts.append(
            f"""GOOGLE FLOW CLIP {index}/5 — EXACTLY 10 SECONDS

{MASTER_VISUAL_BIBLE}

STORY TOPIC:
{topic}

THE NARRATION THAT WILL PLAY OVER THIS CLIP IN THE FINAL EDIT (DO NOT GENERATE IT IN FLOW):
{narration}

SCENE-SPECIFIC VISUAL DIRECTION:
{note}

EXACT OPENING FRAME:
{opening}

10-SECOND TIMELINE:
{timeline}

EXACT ENDING FRAME:
{ending}

NEXT-SCENE TRANSITION ANCHOR:
{next_anchor}

CONTINUITY BRIDGE:
{bridge}

ABSOLUTE REQUIREMENTS:
- Begin useful visual storytelling at frame 1; no title card or lead-in.
- The image must look like live-action documentary footage, not AI art.
- Keep Indian geography, architecture, clothing, skin tones, props and weather plausible.
- Do not burn any text into the generated video.
- Do not create narration/BGM/SFX; output clean visuals so a single continuous master audio mix can span all 5 clips.
""".strip()
        )
    return prompts


def build_plan(topic: str, narration: str | None = None) -> MysteryPlan:
    narration = _clean_text(narration) if narration else generate_telugu_narration(topic)
    parts = split_into_five(narration)
    return MysteryPlan(
        topic=topic,
        narration="\n\n".join(parts),
        narration_parts=parts,
        master_visual_bible=MASTER_VISUAL_BIBLE,
        bgm_prompt=BGM_PROMPT,
        flow_prompts=build_scene_prompts(topic, parts),
    )


def plan_json_bytes(plan: MysteryPlan) -> bytes:
    return json.dumps(asdict(plan), ensure_ascii=False, indent=2).encode("utf-8")


def flow_prompt_text(plan: MysteryPlan) -> str:
    blocks = [
        "TELUGU NARRATION — ONE CONTINUOUS MASTER VOICE TRACK\n" + plan.narration,
        "\nBGM PROMPT — ONE CONTINUOUS MASTER MUSIC TRACK\n" + plan.bgm_prompt,
    ]
    for index, prompt in enumerate(plan.flow_prompts, start=1):
        blocks.append(
            f"\n{'=' * 80}\nFLOW PROMPT {index}/5\n{'=' * 80}\n{prompt}"
        )
    return "\n".join(blocks)


def find_telugu_font(font_dir: str | Path) -> str | None:
    font_dir = Path(font_dir)
    for name in TELUGU_FONT_CANDIDATES:
        if (font_dir / name).is_file():
            return name
    return None


def strip_video_audio(source_path: str, output_path: str) -> str:
    """Create a video-only copy so Flow audio cannot leak into the final mix."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    command = [
        utils.get_ffmpeg_binary(),
        "-y",
        "-nostdin",
        "-v",
        "error",
        "-i",
        source_path,
        "-map",
        "0:v:0",
        "-c:v",
        "copy",
        "-an",
        "-movflags",
        "+faststart",
        output_path,
    ]
    completed = subprocess.run(command, capture_output=True, check=False, timeout=120)
    if completed.returncode != 0:
        command = [
            utils.get_ffmpeg_binary(),
            "-y",
            "-nostdin",
            "-v",
            "error",
            "-i",
            source_path,
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-an",
            "-movflags",
            "+faststart",
            output_path,
        ]
        completed = subprocess.run(command, capture_output=True, check=False, timeout=240)

    if completed.returncode != 0 or not os.path.isfile(output_path):
        detail = completed.stderr.decode("utf-8", errors="replace")[-1000:]
        raise RuntimeError(f"Could not remove source audio from Flow clip: {detail}")
    return output_path
