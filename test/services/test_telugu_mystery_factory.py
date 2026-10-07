from app.services.telugu_mystery_factory import (
    BGM_PROMPT,
    MASTER_VISUAL_BIBLE,
    build_plan,
    build_scene_prompts,
    split_into_five,
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
