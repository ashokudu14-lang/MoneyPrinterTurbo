from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import streamlit as st

root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.models.schema import MaterialInfo, VideoParams
from app.services import bgm as bgm_service
from app.services import material_upload as material_upload_service
from app.services import state as sm
from app.services import webui_task
from app.services.telugu_mystery_factory import (
    BGM_PROMPT,
    MysteryPlan,
    build_plan,
    find_telugu_font,
    flow_prompt_text,
    plan_json_bytes,
    strip_video_audio,
)

st.set_page_config(page_title="Telugu Mystery Factory", page_icon="🎬", layout="centered")
st.markdown(
    """<style>
    @media (max-width: 700px) {
      .stMainBlockContainer { padding-left: 1rem !important; padding-right: 1rem !important; }
      [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: .5rem !important; }
      [data-testid="column"] { min-width: 100% !important; flex: 1 1 100% !important; }
      [data-testid="stButton"] button, [data-testid="stDownloadButton"] button { min-height: 2.8rem; }
      textarea, input { font-size: 16px !important; }
    }
    </style>""",
    unsafe_allow_html=True,
)
st.title("🎬 Telugu Mystery Shorts Factory")
st.caption(
    "Google Flow visuals → one continuous Telugu voice/BGM/subtitle mix in MoneyPrinterTurbo"
)

font_dir = root_dir / "resource" / "fonts"


def _get_plan() -> MysteryPlan | None:
    payload = st.session_state.get("telugu_mystery_plan")
    return payload if isinstance(payload, MysteryPlan) else None


def _save_uploaded_clip(uploaded_file, index: int) -> str:
    stored_name = material_upload_service.save_material_upload(
        uploaded_file.name, uploaded_file
    )
    source_path = os.path.join(
        material_upload_service.uploaded_material_dir(), stored_name
    )
    extension = Path(stored_name).suffix or ".mp4"
    muted_name = f"flow-scene-{index}-{uuid4().hex}{extension}"
    muted_path = os.path.join(
        material_upload_service.uploaded_material_dir(), muted_name
    )
    strip_video_audio(source_path, muted_path)
    try:
        os.remove(source_path)
    except OSError:
        pass
    return muted_path


with st.sidebar:
    st.subheader("Channel preset")
    st.markdown("**Niche:** Indian mysteries & strange true history")
    st.markdown("**Language:** Telugu (India)")
    st.markdown("**Default narrator:** `te-IN-MohanNeural`")
    st.markdown("**Format:** 9:16 · 5 × 10-second Flow clips")
    st.info(
        "Flow is used for visuals only. The final audio is generated once across the complete Short."
    )

col_left, col_right = st.columns([1, 1])
with col_left:
    topic = st.text_input(
        "Indian mystery/history topic",
        value=st.session_state.get(
            "telugu_mystery_topic", "Kuldhara Village mystery, Rajasthan"
        ),
        placeholder="Example: Kuldhara Village mystery, Rajasthan",
    )
with col_right:
    st.write("")
    st.write("")
    generate_clicked = st.button(
        "✨ Generate Telugu story + 5 Flow prompts",
        type="primary",
        use_container_width=True,
    )

if generate_clicked:
    if not topic.strip():
        st.error("Enter a topic first.")
    else:
        with st.spinner("Writing a retention-focused Telugu story and continuity plan…"):
            try:
                plan = build_plan(topic.strip())
            except Exception as exc:
                st.error(f"Could not generate the plan: {exc}")
            else:
                st.session_state["telugu_mystery_topic"] = topic.strip()
                st.session_state["telugu_mystery_plan"] = plan
                st.success(
                    "Plan ready. Generate the five visuals in Google Flow using the prompts below."
                )

plan = _get_plan()
if plan:
    st.divider()
    st.subheader("1. Telugu master narration")
    edited_narration = st.text_area(
        "Edit narration if needed",
        value=plan.narration,
        height=220,
        key="telugu_mystery_narration_editor",
    )
    if st.button("🔄 Rebuild 5 scene prompts from edited narration"):
        try:
            plan = build_plan(plan.topic, narration=edited_narration)
            st.session_state["telugu_mystery_plan"] = plan
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    download_a, download_b = st.columns(2)
    with download_a:
        st.download_button(
            "⬇️ Download all Flow prompts (.txt)",
            data=flow_prompt_text(plan).encode("utf-8"),
            file_name="telugu-mystery-flow-prompts.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with download_b:
        st.download_button(
            "⬇️ Download plan (.json)",
            data=plan_json_bytes(plan),
            file_name="telugu-mystery-plan.json",
            mime="application/json",
            use_container_width=True,
        )

    st.subheader("2. Generate these 5 clips in Google Flow")
    st.caption(
        "Generate each clip separately. Download the best result for each scene. Do not add speech/music in Flow."
    )
    for index, prompt in enumerate(plan.flow_prompts, start=1):
        with st.expander(
            f"Flow Scene {index}/5 — 10 seconds", expanded=(index == 1)
        ):
            st.code(prompt, language=None)

    st.divider()
    st.subheader("3. Upload the 5 Flow clips")
    uploads = st.file_uploader(
        "Select exactly five clips in Scene 1 → Scene 5 order",
        type=["mp4", "mov", "mkv", "webm", "avi", "flv"],
        accept_multiple_files=True,
        key="telugu_flow_uploads",
    )
    if uploads and len(uploads) != 5:
        st.warning(f"You selected {len(uploads)} files. Select exactly 5 clips.")

    font_name = find_telugu_font(font_dir)
    subtitle_enabled = font_name is not None
    if font_name:
        st.success(f"Telugu subtitle font detected: {font_name}")
    else:
        st.warning(
            "No Telugu-capable font was found in resource/fonts. The final video can still be generated, "
            "but Telugu subtitles will stay OFF to avoid square-box characters. Add "
            "NotoSansTelugu-Regular.ttf or NotoSansTelugu-Bold.ttf to resource/fonts, then refresh this page."
        )

    st.subheader("4. Master audio settings")
    voice_col, speed_col, music_col = st.columns(3)
    with voice_col:
        voice_name = st.selectbox(
            "Telugu narrator",
            ["te-IN-MohanNeural", "te-IN-ShrutiNeural"],
            index=0,
        )
    with speed_col:
        voice_rate = st.slider("Narration speed", 0.90, 1.20, 1.06, 0.01)
    with music_col:
        bgm_choice = st.selectbox(
            "Background music",
            [
                "None (safest until licensed AI music is configured)",
                "Upload one continuous BGM track (no API key)",
                "Sonilo AI",
                "ElevenLabs AI",
                "Random bundled music (copyright check required)",
            ],
            index=0,
        )

    bgm_type = {
        "None (safest until licensed AI music is configured)": "",
        "Upload one continuous BGM track (no API key)": "custom",
        "Sonilo AI": "sonilo",
        "ElevenLabs AI": "elevenlabs",
        "Random bundled music (copyright check required)": "random",
    }[bgm_choice]
    bgm_upload = None
    if bgm_type == "custom":
        bgm_upload = st.file_uploader(
            "Upload one continuous background track",
            type=[extension.removeprefix(".") for extension in bgm_service.SUPPORTED_BGM_EXTENSIONS],
            accept_multiple_files=False,
            key="telugu_mystery_bgm_upload",
            max_upload_size=bgm_service.MAX_BGM_UPLOAD_BYTES // (1024 * 1024),
            help="Use the prepared 50-second BGM + wind track. The upload is validated before rendering.",
        )
        if bgm_upload is not None:
            st.audio(bgm_upload)
        else:
            st.info("Select one continuous BGM track before rendering.")

    bgm_volume = st.slider("BGM volume (leave narration clear)", 0.05, 0.30, 0.15, 0.01)
    st.text_area("AI music prompt", value=BGM_PROMPT, height=110, disabled=True)

    ready = bool(
        uploads and len(uploads) == 5 and (bgm_type != "custom" or bgm_upload is not None)
    )
    if st.button(
        "🚀 Assemble final Telugu Short",
        type="primary",
        disabled=not ready,
        use_container_width=True,
    ):
        with st.spinner(
            "Validating clips, stripping Flow audio, and starting the final render…"
        ):
            try:
                material_paths = [
                    _save_uploaded_clip(item, index)
                    for index, item in enumerate(uploads, start=1)
                ]
                materials = [
                    MaterialInfo(provider="local", url=file_path, duration=10)
                    for file_path in material_paths
                ]
                bgm_file = ""
                if bgm_type == "custom":
                    if bgm_upload is None:
                        raise ValueError("Upload one continuous BGM track first.")
                    bgm_file = bgm_service.save_bgm_upload(
                        bgm_upload.name, bgm_upload
                    )
                params = VideoParams(
                    video_subject=plan.topic,
                    video_script=plan.narration,
                    video_aspect="9:16",
                    video_fit_mode="cover",
                    video_concat_mode="sequential",
                    video_transition_mode=None,
                    video_clip_duration=10,
                    video_clip_speed=1.0,
                    match_materials_to_script=False,
                    video_count=1,
                    video_source="local",
                    video_materials=materials,
                    video_language="te-IN",
                    voice_name=voice_name,
                    voice_volume=1.0,
                    voice_rate=voice_rate,
                    bgm_type=bgm_type,
                    bgm_file=bgm_file,
                    bgm_volume=bgm_volume,
                    video_music_prompt=plan.bgm_prompt,
                    subtitle_enabled=subtitle_enabled,
                    subtitle_position="bottom",
                    subtitle_display_mode="sentence",
                    subtitle_animation="none",
                    font_name=font_name or "STHeitiMedium.ttc",
                    font_size=54,
                    stroke_color="#000000",
                    stroke_width=2.0,
                    paragraph_number=5,
                )
                task_id = str(uuid4())
                webui_task.submit_generation(task_id, params, capture_logs=True)
                st.session_state["telugu_mystery_task_id"] = task_id
                st.success(f"Render submitted. Task ID: {task_id}")
            except Exception as exc:
                st.error(f"Could not start the render: {exc}")

    task_id = st.session_state.get("telugu_mystery_task_id")
    if task_id:
        st.divider()
        st.subheader("5. Render status")
        task_state = sm.state.get_task(task_id)
        if task_state:
            progress = int(task_state.get("progress", 0) or 0)
            st.progress(max(0, min(100, progress)) / 100)
            st.write(f"Task: `{task_id}` · Progress: {progress}%")
            if task_state.get("error"):
                st.error(task_state.get("error"))
            videos = task_state.get("videos") or []
            for index, video_path in enumerate(videos, start=1):
                if video_path and os.path.isfile(video_path):
                    st.video(video_path)
                    with open(video_path, "rb") as handle:
                        st.download_button(
                            f"⬇️ Download final Short {index}",
                            data=handle.read(),
                            file_name=f"telugu-mystery-short-{index}.mp4",
                            mime="video/mp4",
                            key=f"download-final-{task_id}-{index}",
                        )
        else:
            st.info("Task state is not available yet. Refresh the page in a moment.")
else:
    st.info(
        "Start by generating a story plan. Kuldhara is pre-filled as the first channel video."
    )
