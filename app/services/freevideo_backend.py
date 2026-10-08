from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import requests


@dataclass(frozen=True)
class FreeVideoSettings:
    mode: str
    base_url: str
    api_token: str
    cli: str
    root: str
    timeout_seconds: int


def get_settings() -> FreeVideoSettings:
    base_url = os.getenv("FREEVIDEO_BASE_URL", "").strip().rstrip("/")
    cli = os.getenv("FREEVIDEO_CLI", "").strip()
    root = os.getenv("FREEVIDEO_ROOT", "").strip()
    mode = os.getenv("FREEVIDEO_MODE", "").strip().lower()
    if not mode:
        if base_url:
            mode = "remote"
        elif cli or root:
            mode = "local"
        else:
            mode = "disabled"
    if mode not in {"disabled", "local", "remote"}:
        raise ValueError("FREEVIDEO_MODE must be one of: disabled, local, remote")
    return FreeVideoSettings(
        mode=mode,
        base_url=base_url,
        api_token=os.getenv("FREEVIDEO_API_TOKEN", "").strip(),
        cli=cli,
        root=root,
        timeout_seconds=max(60, int(os.getenv("FREEVIDEO_TIMEOUT_SECONDS", "3600"))),
    )


def adapt_prompt_for_freevideo(prompt: str) -> str:
    """Reuse the factory's continuity prompts without Flow-specific wording."""
    text = str(prompt or "").strip()
    text = text.replace("GOOGLE FLOW CLIP", "FREEVIDEO CLIP")
    text = text.replace("GOOGLE FLOW AUDIO POLICY", "FREEVIDEO AUDIO POLICY")
    text = text.replace("in Flow", "in the generated clip")
    text = text.replace("Flow's", "FreeVideo's")
    return text


def _auth_headers(settings: FreeVideoSettings) -> dict[str, str]:
    if not settings.api_token:
        return {}
    return {"Authorization": f"Bearer {settings.api_token}"}


def _local_command(settings: FreeVideoSettings) -> list[str]:
    if settings.cli:
        return shlex.split(settings.cli, posix=os.name != "nt")
    if settings.root:
        root = Path(settings.root)
        if os.name == "nt":
            ps1 = root / "freevideo.ps1"
            if ps1.is_file():
                return [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ps1),
                ]
        launcher = root / "freevideo"
        if launcher.is_file():
            return [str(launcher)]
    return ["freevideo"]


def freevideo_status(settings: FreeVideoSettings | None = None) -> dict:
    settings = settings or get_settings()
    if settings.mode == "disabled":
        return {
            "ready": False,
            "mode": "disabled",
            "detail": "Set FREEVIDEO_BASE_URL for a GPU worker or FREEVIDEO_ROOT/FREEVIDEO_CLI for local generation.",
        }

    if settings.mode == "remote":
        if not settings.base_url:
            return {
                "ready": False,
                "mode": "remote",
                "detail": "FREEVIDEO_BASE_URL is not configured.",
            }
        try:
            response = requests.get(
                f"{settings.base_url}/health",
                headers=_auth_headers(settings),
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "ready": bool(payload.get("ready", True)),
                "mode": "remote",
                "detail": payload.get("detail") or payload.get("status") or "GPU worker is reachable.",
                "worker": payload,
            }
        except Exception as exc:
            return {"ready": False, "mode": "remote", "detail": str(exc)}

    command = _local_command(settings)
    executable = command[0] if command else ""
    executable_ready = bool(
        executable
        and (
            Path(executable).is_file()
            or shutil.which(executable)
            or (settings.root and (Path(settings.root) / executable).is_file())
        )
    )
    return {
        "ready": executable_ready,
        "mode": "local",
        "detail": (
            f"Local FreeVideo command: {' '.join(command)}"
            if executable_ready
            else "Local FreeVideo CLI was not found. Configure FREEVIDEO_ROOT or FREEVIDEO_CLI."
        ),
    }


def _validate_video(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"FreeVideo did not create a usable output file: {path}")
    return path


def _generate_local(
    *,
    settings: FreeVideoSettings,
    prompt: str,
    output_path: Path,
    width: int,
    height: int,
    seconds: float,
    seed: int,
    preview: bool,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path = output_path.with_suffix(".prompt.txt")
    prompt_path.write_text(prompt, encoding="utf-8")

    command = _local_command(settings) + [
        "generate",
        "--prompt-file",
        str(prompt_path),
        "--out",
        str(output_path),
        "--width",
        str(width),
        "--height",
        str(height),
        "--seconds",
        str(seconds),
        "--seed",
        str(seed),
    ]
    if preview:
        command.append("--preview")

    completed = subprocess.run(
        command,
        cwd=settings.root or None,
        capture_output=True,
        check=False,
        timeout=settings.timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")[-3000:]
        stdout = completed.stdout.decode("utf-8", errors="replace")[-1500:]
        raise RuntimeError(
            "FreeVideo local generation failed. "
            f"Exit code: {completed.returncode}.\n{stderr or stdout}"
        )
    return _validate_video(output_path)


def _generate_remote(
    *,
    settings: FreeVideoSettings,
    prompt: str,
    output_path: Path,
    width: int,
    height: int,
    seconds: float,
    seed: int,
    preview: bool,
) -> Path:
    if not settings.base_url:
        raise RuntimeError("FREEVIDEO_BASE_URL is not configured")

    response = requests.post(
        f"{settings.base_url}/generate",
        headers=_auth_headers(settings),
        json={
            "prompt": prompt,
            "width": width,
            "height": height,
            "seconds": seconds,
            "seed": seed,
            "preview": preview,
        },
        timeout=settings.timeout_seconds,
    )
    if response.status_code >= 400:
        detail = response.text[-3000:]
        raise RuntimeError(
            f"FreeVideo worker returned HTTP {response.status_code}: {detail}"
        )
    if not response.content:
        raise RuntimeError("FreeVideo worker returned an empty response")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.content)
    return _validate_video(output_path)


def generate_freevideo_clip(
    prompt: str,
    output_path: str | Path,
    *,
    width: int = 768,
    height: int = 1344,
    seconds: float = 10.0,
    seed: int = 2026090901,
    preview: bool = False,
    settings: FreeVideoSettings | None = None,
) -> str:
    settings = settings or get_settings()
    if settings.mode == "disabled":
        raise RuntimeError(
            "FreeVideo is not configured. Set FREEVIDEO_BASE_URL for a remote GPU worker "
            "or FREEVIDEO_ROOT/FREEVIDEO_CLI for local generation."
        )

    output = Path(output_path)
    adapted = adapt_prompt_for_freevideo(prompt)
    kwargs = dict(
        settings=settings,
        prompt=adapted,
        output_path=output,
        width=width,
        height=height,
        seconds=seconds,
        seed=seed,
        preview=preview,
    )
    if settings.mode == "remote":
        result = _generate_remote(**kwargs)
    else:
        result = _generate_local(**kwargs)
    return str(result)


def generate_freevideo_clips(
    prompts: Iterable[str],
    output_dir: str | Path,
    *,
    width: int = 768,
    height: int = 1344,
    seconds: float = 10.0,
    seed: int = 2026090901,
    preview: bool = False,
    settings: FreeVideoSettings | None = None,
    progress: Callable[[int, int, str], None] | None = None,
) -> list[str]:
    prompt_list = list(prompts)
    if not prompt_list:
        return []
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    settings = settings or get_settings()

    results: list[str] = []
    total = len(prompt_list)
    for index, prompt in enumerate(prompt_list, start=1):
        if progress:
            progress(index, total, f"Generating scene {index}/{total}")
        output_path = target_dir / f"freevideo-scene-{index:02d}.mp4"
        result = generate_freevideo_clip(
            prompt,
            output_path,
            width=width,
            height=height,
            seconds=seconds,
            seed=seed + index - 1,
            preview=preview,
            settings=settings,
        )
        results.append(result)
    return results
