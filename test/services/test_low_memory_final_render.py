"""Regression coverage for low-memory final Shorts rendering."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.models.schema import VideoParams
from app.services import video as vd


class TestLowMemoryFinalRender(unittest.TestCase):
    def _inputs(self, root: Path):
        paths = {
            "video": root / "combined-1.mp4",
            "audio": root / "audio.mp3",
            "subtitle": root / "subtitle.srt",
            "font": root / "NotoSansTelugu-Regular.ttf",
            "bgm": root / "bgm.mp3",
            "output": root / "final.mp4",
        }
        for name, path in paths.items():
            if name != "output":
                path.write_bytes(b"fixture")
        params = VideoParams(
            video_subject="Kuldhara",
            video_aspect="9:16",
            subtitle_enabled=True,
            subtitle_position="bottom",
            subtitle_display_mode="sentence",
            subtitle_animation="none",
            font_name=paths["font"].name,
            font_size=54,
            text_fore_color="#FFFFFF",
            stroke_color="#000000",
            stroke_width=2.0,
            voice_volume=1.0,
            bgm_type="custom",
            bgm_file=str(paths["bgm"]),
            bgm_volume=0.15,
        )
        return paths, params

    def test_factory_style_uses_single_thread_ffmpeg_subtitle_and_audio_mix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, params = self._inputs(Path(temp_dir))
            with (
                patch.object(vd.utils, "get_ffmpeg_binary", return_value="/usr/bin/ffmpeg"),
                patch.object(vd, "get_bgm_file", return_value=str(paths["bgm"])),
                patch.object(
                    vd.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, "", ""),
                ) as run,
            ):
                result = vd._try_generate_video_with_low_memory_ffmpeg(
                    video_path=str(paths["video"]),
                    audio_path=str(paths["audio"]),
                    subtitle_path=str(paths["subtitle"]),
                    output_file=str(paths["output"]),
                    params=params,
                    font_path=str(paths["font"]),
                )

            self.assertTrue(result)
            command = run.call_args.args[0]
            graph = command[command.index("-filter_complex") + 1]
            self.assertIn("subtitles=", graph)
            self.assertIn("FontSize=19", graph)
            self.assertIn("MarginV=14", graph)
            self.assertIn("amix=inputs=2", graph)
            self.assertIn("-threads:v", command)
            self.assertTrue(paths["output"].is_file())

    def test_unsupported_subtitle_animation_keeps_existing_renderer_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, params = self._inputs(Path(temp_dir))
            params.subtitle_animation = "pop_spring"
            with patch.object(vd.subprocess, "run") as run:
                result = vd._try_generate_video_with_low_memory_ffmpeg(
                    video_path=str(paths["video"]),
                    audio_path=str(paths["audio"]),
                    subtitle_path=str(paths["subtitle"]),
                    output_file=str(paths["output"]),
                    params=params,
                    font_path=str(paths["font"]),
                )

            self.assertIsNone(result)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
