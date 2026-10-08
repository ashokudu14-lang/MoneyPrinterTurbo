import subprocess

from moviepy import VideoFileClip

from app.services import freevideo_backend
from app.services.freevideo_backend import FreeVideoSettings, adapt_prompt_for_freevideo
from app.utils import utils
from app.services.telugu_mystery_factory import (
    BGM_PROMPT,
    MASTER_VISUAL_BIBLE,
    build_plan,
    build_scene_prompts,
    split_into_five,
    strip_video_audio,
)


def test_split_into_five_preserves_five_paragraphs():
    narration = "ఒకటి\nరెండు\nమూడు\nనాలుగు\nఐదు"
    assert split_into_five(narration) == ["ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు"]


def test_scene_prompts_are_five_continuity_locked_ten_second_clips():
    parts = [
        "మొదటి భాగం",
        "రెండో భాగం",
        "మూడో భాగం",
        "నాలుగో భాగం",
        "ఐదో భాగం",
    ]
    prompts = build_scene_prompts("Kuldhara Village mystery, Rajasthan", parts)

    assert len(prompts) == 5
    assert all("EXACTLY 10 SECONDS" in prompt for prompt in prompts)
    assert all("VISUALS ONLY" in prompt for prompt in prompts)
    assert all("Do not create narration/BGM/SFX" in prompt for prompt in prompts)
    assert "same upward crane/drone rise" in prompts[-1]
    assert all("EXACT OPENING FRAME" in prompt for prompt in prompts)
    assert all("10-SECOND TIMELINE" in prompt for prompt in prompts)
    assert all("EXACT ENDING FRAME" in prompt for prompt in prompts)
    assert all("NEXT-SCENE TRANSITION ANCHOR" in prompt for prompt in prompts)
    assert "same dark rectangular Kuldhara sandstone doorway" in prompts[1]
    assert "centered lamp wick/flame" in prompts[1]
    assert "same clay lamp, centered wick" in prompts[2]
    assert "same footprints" in prompts[3]
    assert "already rising and moving forward" in prompts[4]


def test_strip_video_audio_upscales_360p_flow_clip(tmp_path):
    source_path = tmp_path / "flow-360p.mp4"
    output_path = tmp_path / "flow-360p-video-only.mp4"
    subprocess.run(
        [
            utils.get_ffmpeg_binary(),
            "-y",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=360x640:r=24:d=0.5",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=0.5",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source_path),
        ],
        check=True,
        timeout=60,
    )

    strip_video_audio(str(source_path), str(output_path))

    with VideoFileClip(str(output_path)) as clip:
        assert min(clip.size) >= 480
        assert clip.audio is None


def test_build_plan_with_existing_narration_does_not_need_llm():
    narration = "\n\n".join(
        [
            "మొదటి కథ భాగం",
            "రెండో కథ భాగం",
            "మూడో కథ భాగం",
            "నాలుగో కథ భాగం",
            "ఐదో కథ భాగం",
        ]
    )
    plan = build_plan("Kuldhara Village mystery, Rajasthan", narration=narration)

    assert len(plan.narration_parts) == 5
    assert len(plan.flow_prompts) == 5
    assert plan.recommended_voice == "te-IN-MohanNeural"
    assert plan.video_language == "te-IN"
    assert plan.aspect_ratio == "9:16"
    assert plan.clip_seconds == 10
    assert plan.master_visual_bible == MASTER_VISUAL_BIBLE
    assert plan.bgm_prompt == BGM_PROMPT


def test_freevideo_prompt_adapter_removes_flow_specific_heading():
    prompt = "GOOGLE FLOW CLIP 1/5\nGOOGLE FLOW AUDIO POLICY: visuals only in Flow"
    adapted = adapt_prompt_for_freevideo(prompt)

    assert "FREEVIDEO CLIP 1/5" in adapted
    assert "FREEVIDEO AUDIO POLICY" in adapted
    assert "in the generated clip" in adapted
    assert "GOOGLE FLOW" not in adapted


def test_remote_freevideo_generation_writes_returned_video(monkeypatch, tmp_path):
    class FakeResponse:
        status_code = 200
        content = b"fake-mp4-bytes"
        text = ""

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(
            url=url,
            headers=headers,
            json=json,
            timeout=timeout,
        )
        return FakeResponse()

    monkeypatch.setattr(freevideo_backend.requests, "post", fake_post)
    settings = FreeVideoSettings(
        mode="remote",
        base_url="https://gpu.example.test",
        api_token="secret-token",
        cli="",
        root="",
        timeout_seconds=123,
    )
    output = tmp_path / "scene.mp4"

    result = freevideo_backend.generate_freevideo_clip(
        "GOOGLE FLOW CLIP 1/5\nA cinematic Indian village",
        output,
        width=768,
        height=1344,
        seconds=10,
        seed=42,
        settings=settings,
    )

    assert result == str(output)
    assert output.read_bytes() == b"fake-mp4-bytes"
    assert captured["url"] == "https://gpu.example.test/generate"
    assert captured["headers"] == {"Authorization": "Bearer secret-token"}
    assert captured["timeout"] == 123
    assert captured["json"]["width"] == 768
    assert captured["json"]["height"] == 1344
    assert captured["json"]["seconds"] == 10
    assert captured["json"]["seed"] == 42
    assert "FREEVIDEO CLIP 1/5" in captured["json"]["prompt"]
