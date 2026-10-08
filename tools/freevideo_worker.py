from __future__ import annotations

import hmac
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask


app = FastAPI(title="MoneyPrinterTurbo FreeVideo Worker", version="1.0")


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    width: int = Field(default=768, ge=256, le=2048)
    height: int = Field(default=1344, ge=256, le=2048)
    seconds: float = Field(default=10.0, gt=0, le=30)
    seed: int = 2026090901
    preview: bool = False


def _settings() -> tuple[str, str, str, int]:
    cli = os.getenv("FREEVIDEO_CLI", "").strip()
    root = os.getenv("FREEVIDEO_ROOT", "").strip()
    token = os.getenv("FREEVIDEO_API_TOKEN", "").strip()
    timeout = max(60, int(os.getenv("FREEVIDEO_TIMEOUT_SECONDS", "3600")))
    return cli, root, token, timeout


def _authorize(authorization: str | None) -> None:
    _, _, token, _ = _settings()
    if not token:
        return
    expected = f"Bearer {token}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid FreeVideo worker token")


def _command(cli: str, root: str) -> list[str]:
    if cli:
        return shlex.split(cli, posix=os.name != "nt")
    if root:
        root_path = Path(root)
        if os.name == "nt":
            ps1 = root_path / "freevideo.ps1"
            if ps1.is_file():
                return [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ps1),
                ]
        launcher = root_path / "freevideo"
        if launcher.is_file():
            return [str(launcher)]
    return ["freevideo"]


def _command_ready(command: list[str], root: str) -> bool:
    if not command:
        return False
    executable = command[0]
    if Path(executable).is_file() or shutil.which(executable):
        return True
    if root and (Path(root) / executable).is_file():
        return True
    return False


@app.get("/health")
def health(authorization: str | None = Header(default=None)) -> dict:
    _authorize(authorization)
    cli, root, token, _ = _settings()
    command = _command(cli, root)
    ready = _command_ready(command, root)
    return {
        "ready": ready,
        "status": "ready" if ready else "freevideo-cli-not-found",
        "detail": (
            "FreeVideo CLI is available."
            if ready
            else "Configure FREEVIDEO_ROOT or FREEVIDEO_CLI on this GPU worker."
        ),
        "auth_enabled": bool(token),
    }


@app.post("/generate")
def generate(
    request: GenerateRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    cli, root, _, timeout = _settings()
    command = _command(cli, root)
    if not _command_ready(command, root):
        raise HTTPException(
            status_code=503,
            detail="FreeVideo CLI was not found. Configure FREEVIDEO_ROOT or FREEVIDEO_CLI.",
        )

    work_parent = os.getenv("FREEVIDEO_WORKER_TMP", "").strip() or None
    if work_parent:
        Path(work_parent).mkdir(parents=True, exist_ok=True)
    job_dir = Path(tempfile.mkdtemp(prefix="freevideo-worker-", dir=work_parent))
    prompt_path = job_dir / "prompt.txt"
    output_path = job_dir / "video.mp4"
    prompt_path.write_text(request.prompt, encoding="utf-8")

    cmd = command + [
        "generate",
        "--prompt-file",
        str(prompt_path),
        "--out",
        str(output_path),
        "--width",
        str(request.width),
        "--height",
        str(request.height),
        "--seconds",
        str(request.seconds),
        "--seed",
        str(request.seed),
    ]
    if request.preview:
        cmd.append("--preview")

    try:
        completed = subprocess.run(
            cmd,
            cwd=root or None,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=504, detail="FreeVideo generation timed out") from exc
    except Exception as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")[-3000:]
        stdout = completed.stdout.decode("utf-8", errors="replace")[-1500:]
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500,
            detail=(
                f"FreeVideo exited with code {completed.returncode}. "
                f"{stderr or stdout or 'No output was produced.'}"
            ),
        )

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename="freevideo.mp4",
        background=BackgroundTask(shutil.rmtree, job_dir, ignore_errors=True),
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("FREEVIDEO_WORKER_HOST", "0.0.0.0")
    port = int(os.getenv("FREEVIDEO_WORKER_PORT", "8765"))
    uvicorn.run("tools.freevideo_worker:app", host=host, port=port, reload=False)
