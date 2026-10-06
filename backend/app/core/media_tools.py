"""Locate local media tooling (ffmpeg / ffprobe / yt-dlp).

The machine this app runs on may not have ffmpeg on PATH, so resolution order
is explicit and predictable:

1. an explicit setting (``LTA_FFMPEG`` / ``LTA_YTDLP``),
2. whatever is already on PATH,
3. a portable copy shipped inside the project at ``tools/ffmpeg/bin``.

Resolution never downloads anything at request time; if a tool is missing the
caller raises a clear, actionable error instead of a bare FileNotFoundError.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import Settings


class MediaToolError(RuntimeError):
    """Raised when a required external media tool cannot be located."""


def _candidates(name: str, configured: str, project_root: Path) -> list[str]:
    exe = f"{name}.exe"
    values = [
        configured,
        shutil.which(name) or "",
        str(project_root / "tools" / "ffmpeg" / "bin" / exe),
        str(project_root / "tools" / "ffmpeg" / "bin" / name),
    ]
    return [value for value in values if value]


def resolve_ffmpeg(settings: Settings, *, required: bool = True) -> str | None:
    for value in _candidates("ffmpeg", settings.ffmpeg_path, settings.project_root):
        path = Path(value)
        if path.is_file():
            return str(path)
    if required:
        raise MediaToolError(
            "未找到 ffmpeg。请把 ffmpeg 放到 项目/tools/ffmpeg/bin/ffmpeg.exe，"
            "或安装后加入 PATH，或设置环境变量 LTA_FFMPEG 指向 ffmpeg.exe。"
        )
    return None


def resolve_ffprobe(settings: Settings, *, required: bool = False) -> str | None:
    for value in _candidates("ffprobe", "", settings.project_root):
        path = Path(value)
        if path.is_file():
            return str(path)
    if required:
        raise MediaToolError("未找到 ffprobe，请随 ffmpeg 一并安装。")
    return None


def resolve_ytdlp(settings: Settings, *, required: bool = True) -> list[str]:
    """Return the argv prefix used to invoke yt-dlp.

    Prefers the module installed into the running interpreter so the tool
    version always matches the environment, then falls back to a configured
    path or a PATH-installed executable.
    """
    if settings.ytdlp_path:
        path = Path(settings.ytdlp_path)
        if path.is_file():
            return [str(path)]

    which = shutil.which("yt-dlp")
    if which:
        return [which]

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        if required:
            raise MediaToolError(
                "未找到 yt-dlp。请运行："
                f'"{Path(__import__("sys").executable)}" -m pip install yt-dlp'
            )
        return []
    return [__import__("sys").executable, "-m", "yt_dlp"]


def resolve_whisper_model(settings: Settings, model_size: str) -> str:
    """Return what WhisperModel() should load.

    A local directory wins over a model name so a machine with unreliable
    access to Hugging Face can run fully offline once the files are present.
    """
    if settings.whisper_model_dir:
        configured = Path(settings.whisper_model_dir)
        if (configured / "model.bin").is_file():
            return str(configured)
    local = settings.project_root / "tools" / "models" / f"faster-whisper-{model_size}"
    if (local / "model.bin").is_file():
        return str(local)
    return model_size
