"""Import training material from a video link (Bilibili / YouTube / 小红书 ...).

Pipeline: yt-dlp download -> ffmpeg transcode to 16 kHz mono WAV -> local ASR
(faster-whisper) with word timestamps -> sentence alignment -> the same
MaterialPreprocessor/MaterialStore path every other material uses.

The work is long (download + CPU transcription), so it runs on a worker thread
and the HTTP layer only ever answers fast JSON: the POST returns a job id and
the client polls the job. That keeps a slow import from turning into an empty
or truncated response in the browser.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import uuid
import wave
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.adapters.speech import RecognizedSegment
from app.config import Settings
from app.core.materials import MaterialExistsError, MaterialStore
from app.core.media_tools import (
    MediaToolError,
    resolve_ffmpeg,
    resolve_whisper_model,
    resolve_ytdlp,
)
from app.db.connection import Database
from app.preprocess.material import (
    MaterialPreprocessError,
    MaterialPreprocessor,
    TimestampedSentence,
)


class VideoImportError(RuntimeError):
    """User-actionable import failure (shown verbatim in the UI)."""


STAGE_LABELS: dict[str, str] = {
    "QUEUED": "排队中",
    "DOWNLOAD": "下载音视频",
    "CONVERT": "转码为训练音频",
    "TRANSCRIBE": "语音识别逐句时间戳",
    "BUILD": "切分三段并入库",
    "DONE": "完成",
    "FAILED": "失败",
}

#: yt-dlp prints progress like "[download]  42.3% of 12.34MiB at ...".
_PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
#: Errors worth surfacing to the user instead of "some site error occurred".
_KNOWN_YTDLP_ERRORS = (
    ("Unsupported URL", "这个链接不被 yt-dlp 支持，请换一条视频页面链接（不是分享短链或直播）。"),
    ("Private video", "该视频是私有的，无法下载。"),
    ("This video is only available for registered users", "该视频需要登录才能观看，请换一条公开视频。"),
    ("Video unavailable", "视频不可用，可能已被删除或限制地区。"),
    ("HTTP Error 412", "平台触发了风控（HTTP 412），稍后重试或换一条视频。"),
    ("Sign in to confirm", "平台要求登录验证，请换一条公开视频。"),
)

_MODEL_CACHE: dict[tuple[str, str, str], object] = {}
_MODEL_LOCK = threading.Lock()


@dataclass
class ImportJob:
    job_id: str
    url: str
    status: str = "QUEUED"
    stage: str = "QUEUED"
    progress: float = 0.0
    message: str = "已加入队列"
    requested_title: str | None = None
    source_title: str | None = None
    material_id: str | None = None
    duration_seconds: float | None = None
    sentence_count: int | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None

    def payload(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "status": self.status,
            "stage": self.stage,
            "stage_label": STAGE_LABELS.get(self.stage, self.stage),
            "progress": round(self.progress, 4),
            "message": self.message,
            "title": self.requested_title or self.source_title,
            "source_title": self.source_title,
            "material_id": self.material_id,
            "duration_seconds": self.duration_seconds,
            "sentence_count": self.sentence_count,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


def _probe_duration(wav_path: str) -> float:
    with wave.open(wav_path, "rb") as handle:
        return handle.getnframes() / handle.getframerate()


#: Sentence-building targets (in words). ASR output frequently carries no
#: punctuation at all, so sentence units are derived from ASR segment pauses
#: plus word counts rather than from punctuation alone.
TARGET_SENTENCE_WORDS = 14
MIN_SENTENCE_WORDS = 4
MAX_SENTENCE_WORDS = 28
_TERMINAL_PUNCTUATION = (".", "!", "?", "…", "。", "！", "？", "；")


def _is_cjk_dominant(text: str) -> bool:
    cjk = sum(1 for char in text if "\u3400" <= char <= "\u9fff")
    letters = sum(1 for char in text if char.isalnum())
    return letters > 0 and cjk / letters > 0.4


def _join_words(texts: list[str]) -> str:
    """CJK text must not gain spaces; spaced scripts must keep them."""
    joined = "".join(texts) if _is_cjk_dominant("".join(texts)) else " ".join(texts)
    return joined.strip()


def build_sentence_units(segments) -> list[TimestampedSentence]:
    """Turn ASR segments into sentence-sized units with precise timestamps.

    Each ASR segment already breaks on a natural pause, so segments are
    accumulated up to TARGET_SENTENCE_WORDS and flushed at punctuation or a
    segment boundary. Oversized results are split and trailing fragments are
    merged back, so the output is always strictly ordered and never collapses
    the whole recording into a single "sentence".
    """
    units: list[TimestampedSentence] = []
    buffer: list[tuple[str, float, float]] = []

    def flush() -> None:
        if not buffer:
            return
        text = _join_words([word for word, _, _ in buffer])
        if text:
            units.append(
                TimestampedSentence(text=text, start_time=buffer[0][1], end_time=buffer[-1][2])
            )
        buffer.clear()

    for segment in segments:
        words = [
            ((word.word or "").strip(), float(word.start), float(word.end))
            for word in (getattr(segment, "words", None) or [])
            if (word.word or "").strip()
        ]
        if not words:
            text = (segment.text or "").strip()
            if not text:
                continue
            words = [(text, float(segment.start), float(segment.end))]
        for word, start, end in words:
            buffer.append((word, start, end))
            if len(buffer) >= MIN_SENTENCE_WORDS and word.endswith(_TERMINAL_PUNCTUATION):
                flush()
        # A segment boundary is a pause: close the unit once it is long enough.
        if len(buffer) >= TARGET_SENTENCE_WORDS:
            flush()
    flush()

    # Split over-long units at word boundaries, keeping timestamps monotonic.
    sized: list[TimestampedSentence] = []
    for unit in units:
        words = unit.text.split() if not _is_cjk_dominant(unit.text) else list(unit.text)
        if len(words) <= MAX_SENTENCE_WORDS or len(words) == 0:
            sized.append(unit)
            continue
        span = max(0.0, unit.end_time - unit.start_time)
        step = span / len(words)
        for offset in range(0, len(words), TARGET_SENTENCE_WORDS):
            chunk = words[offset : offset + TARGET_SENTENCE_WORDS]
            if not chunk:
                continue
            text = _join_words(chunk)
            sized.append(
                TimestampedSentence(
                    text=text,
                    start_time=unit.start_time + offset * step,
                    end_time=unit.start_time + (offset + len(chunk)) * step,
                )
            )

    # Fold a too-short trailing fragment into its predecessor.
    if len(sized) > 1 and len(sized[-1].text.split()) < MIN_SENTENCE_WORDS:
        last = sized.pop()
        previous = sized.pop()
        merged = TimestampedSentence(
            text=_join_words([previous.text, last.text]),
            start_time=previous.start_time,
            end_time=last.end_time,
        )
        sized.append(merged)

    # ASR word timestamps can be degenerate (zero-length words, small
    # overlaps). The material model requires strictly ordered, positive
    # spans, so normalize rather than reject an otherwise good transcript.
    normalized: list[TimestampedSentence] = []
    previous_end = 0.0
    for unit in sized:
        start = max(unit.start_time, previous_end)
        end = unit.end_time if unit.end_time > start else start + 0.05
        normalized.append(TimestampedSentence(text=unit.text, start_time=start, end_time=end))
        previous_end = end
    return normalized


def _read_wav_samples(wav_path: str):
    """Decode our own 16 kHz mono PCM WAV straight into a float32 array.

    faster-whisper decodes file paths through PyAV, and the PyAV wheel
    available here rejects the `metadata_errors` argument its decoder passes.
    Feeding it samples instead skips that path entirely - and the audio it
    would have decoded is exactly what ffmpeg just wrote above.
    """
    import numpy as np

    with wave.open(wav_path, "rb") as handle:
        channels = handle.getnchannels()
        rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise VideoImportError(f"音频位深不受支持：{width * 8} bit（期望 16 bit）。")
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        raise VideoImportError(f"音频采样率不受支持：{rate} Hz（期望 16000 Hz）。")
    return samples


class VideoImportService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.store = MaterialStore(database)
        self._jobs: dict[str, ImportJob] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- public

    def start(
        self,
        *,
        url: str,
        title: str | None = None,
        material_id: str | None = None,
        language: str | None = None,
        model_size: str | None = None,
    ) -> dict[str, object]:
        url = (url or "").strip()
        if not url:
            raise VideoImportError("请填写视频链接。")
        if not re.match(r"^https?://", url, re.IGNORECASE):
            raise VideoImportError("链接需要以 http:// 或 https:// 开头。")

        job = ImportJob(job_id=str(uuid.uuid4()), url=url, requested_title=title)
        with self._lock:
            self._jobs[job.job_id] = job

        worker = threading.Thread(
            target=self._run,
            args=(job, material_id, language or self.settings.whisper_language, model_size or self.settings.whisper_model_size),
            daemon=True,
            name=f"video-import-{job.job_id[:8]}",
        )
        worker.start()
        return job.payload()

    def get(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            job = self._jobs.get(job_id)
        return job.payload() if job else None

    def list_recent(self, limit: int = 20) -> list[dict[str, object]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
        return [job.payload() for job in jobs[:limit]]

    def check_ready(self) -> dict[str, object]:
        """Report which optional tools are present, so the UI can warn early."""
        report: dict[str, object] = {"ffmpeg": False, "yt_dlp": False, "faster_whisper": False, "problems": []}
        try:
            resolve_ffmpeg(self.settings)
            report["ffmpeg"] = True
        except MediaToolError as exc:
            report["problems"].append(str(exc))
        try:
            resolve_ytdlp(self.settings)
            report["yt_dlp"] = True
        except MediaToolError as exc:
            report["problems"].append(str(exc))
        try:
            import faster_whisper  # noqa: F401

            report["faster_whisper"] = True
        except ImportError:
            report["problems"].append("未安装 faster-whisper，无法生成逐句时间戳。")
        model_ref = resolve_whisper_model(self.settings, self.settings.whisper_model_size)
        report["whisper_model"] = model_ref
        report["whisper_model_local"] = model_ref != self.settings.whisper_model_size
        if not report["whisper_model_local"]:
            report["problems"].append(
                f"语音模型 {self.settings.whisper_model_size} 尚未下载到本地，首次识别时会联网下载。"
            )
        report["ready"] = not report["problems"]
        return report

    # ---------------------------------------------------------------- worker

    def _run(self, job: ImportJob, material_id: str | None, language: str, model_size: str) -> None:
        work_dir = self.settings.import_dir / job.job_id
        try:
            self._set(job, status="RUNNING", stage="DOWNLOAD", message="正在解析视频链接…")
            work_dir.mkdir(parents=True, exist_ok=True)
            media_path, source_title = self._download(job, work_dir)

            self._set(job, stage="CONVERT", progress=0.0, message="正在转码为 16kHz 单声道音频…")
            wav_path = self._transcode(job, media_path, work_dir)
            duration = _probe_duration(wav_path)

            self._set(job, stage="TRANSCRIBE", progress=0.0, message=f"正在进行语音识别（{model_size} 模型）…")
            segments = self._transcribe(job, wav_path, duration, language, model_size)

            self._set(job, stage="BUILD", progress=0.0, message="正在切分句子与三段…")
            material_spec, transcript = self._build(job, wav_path, segments, material_id, source_title)

            self._set(job, stage="BUILD", progress=0.8, message="正在写入素材库…")
            self._store(job, material_spec, source_title)

            job.source_title = source_title
            job.material_id = material_spec.material_id
            job.duration_seconds = round(material_spec.duration_seconds, 1)
            job.sentence_count = len(material_spec.sentences)
            self._set(
                job,
                status="DONE",
                stage="DONE",
                progress=1.0,
                message=f"导入完成：{len(material_spec.sentences)} 句，约 {material_spec.duration_seconds / 60:.1f} 分钟。",
                finished_at=datetime.now(UTC).isoformat(),
            )
        except VideoImportError as exc:
            self._fail(job, str(exc))
        except Exception as exc:
            self._fail(job, f"导入失败：{exc}")

    def _set(self, job: ImportJob, **changes) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(job, key, value)

    def _fail(self, job: ImportJob, message: str) -> None:
        with self._lock:
            job.status = "FAILED"
            job.stage = "FAILED"
            job.error = message
            job.message = message
            job.finished_at = datetime.now(UTC).isoformat()

    # ---------------------------------------------------------------- stages

    def _download(self, job: ImportJob, work_dir) -> tuple[str, str]:
        argv = resolve_ytdlp(self.settings)
        argv += [
            "--no-playlist",
            "--no-warnings",
            "--newline",
            "--retries",
            "3",
            "--socket-timeout",
            "30",
            "-f",
            "bestaudio/best",
            "-o",
            str(work_dir / "source.%(ext)s"),
            "--print",
            "after_move:__TITLE__%(title)s",
            job.url,
        ]
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise VideoImportError(f"无法启动 yt-dlp：{exc}") from exc

        tail: list[str] = []
        title: str | None = None
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            if not line:
                continue
            tail.append(line)
            if len(tail) > 40:
                tail.pop(0)
            if line.startswith("__TITLE__"):
                title = line[len("__TITLE__") :].strip()
                continue
            match = _PROGRESS_RE.search(line)
            if match:
                percent = float(match.group(1))
                # Reserve the first 90% of this stage for the actual transfer.
                self._set(
                    job,
                    progress=min(0.9, percent / 100.0 * 0.9),
                    message=f"正在下载音视频… {percent:.1f}%",
                )
        code = process.wait()
        if code != 0:
            raise VideoImportError(self._explain_ytdlp(tail))

        media_files = [
            path
            for path in work_dir.iterdir()
            if path.is_file() and path.name.startswith("source.") and path.suffix.lower() != ".part"
        ]
        if not media_files:
            raise VideoImportError("下载完成但没有找到媒体文件，链接可能指向直播或不支持的内容。")
        self._set(job, progress=0.9, message="下载完成。")
        return str(max(media_files, key=lambda path: path.stat().st_size)), (title or "未命名视频")

    @staticmethod
    def _explain_ytdlp(tail: list[str]) -> str:
        joined = "\n".join(tail)
        for needle, friendly in _KNOWN_YTDLP_ERRORS:
            if needle.lower() in joined.lower():
                return friendly
        for line in reversed(tail):
            if line.startswith("ERROR:"):
                return f"下载失败：{line[len('ERROR:'):].strip()}"
        return "下载失败：无法从该链接获取音视频，请确认链接可在浏览器中直接播放。"

    def _transcode(self, job: ImportJob, media_path: str, work_dir) -> str:
        ffmpeg = resolve_ffmpeg(self.settings)
        wav_path = work_dir / "training.wav"
        result = subprocess.run(
            [
                ffmpeg, "-y", "-loglevel", "error", "-i", media_path,
                "-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(wav_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not wav_path.is_file():
            detail = (result.stderr or "").strip().splitlines()
            raise VideoImportError(
                "音频转码失败：" + (detail[-1] if detail else "该视频可能没有音轨。")
            )
        self._set(job, progress=1.0, message="转码完成。")
        return str(wav_path)

    def _transcribe(
        self, job: ImportJob, wav_path: str, duration: float, language: str, model_size: str
    ) -> list[RecognizedSegment]:
        if self.settings.hf_endpoint:
            # Must be set before faster-whisper resolves the model repository.
            os.environ.setdefault("HF_ENDPOINT", self.settings.hf_endpoint)
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise VideoImportError(
                "未安装 faster-whisper，无法生成逐句时间戳。请先安装："
                f'"{sys.executable}" -m pip install faster-whisper'
            ) from exc

        cache_key = (model_size, "cpu", "int8")
        with _MODEL_LOCK:
            model = _MODEL_CACHE.get(cache_key)
            if model is None:
                # A ready local copy is preferred; a bare model name makes
                # faster-whisper fall back to downloading it.
                model_ref = resolve_whisper_model(self.settings, model_size)
                if model_ref == model_size:
                    self._set(job, message=f"正在加载语音模型 {model_size}（首次使用需下载，请耐心等待）…")
                else:
                    self._set(job, message=f"正在加载本地语音模型 {model_size}…")
                try:
                    model = WhisperModel(model_ref, device="cpu", compute_type="int8")
                except Exception as exc:
                    raise VideoImportError(
                        f"语音模型 {model_size} 加载失败：{exc}"
                    ) from exc
                _MODEL_CACHE[cache_key] = model

        try:
            audio = _read_wav_samples(wav_path)
        except VideoImportError:
            raise
        except Exception as exc:
            raise VideoImportError(f"读取训练音频失败：{exc}") from exc

        try:
            segments, _info = model.transcribe(
                audio,
                language=language or None,  # empty -> let the model detect it
                word_timestamps=True,
                vad_filter=True,
                beam_size=1,
                # Punctuated English output makes sentence splitting cleaner
                # when the caller has already pinned the language to English.
                initial_prompt=(
                    "Hello and welcome. Today we are going to talk about something interesting."
                    if language == "en"
                    else None
                ),
            )
            collected = []
            for segment in segments:
                collected.append(segment)
                if duration > 0:
                    self._set(
                        job,
                        progress=min(1.0, segment.end / duration),
                        message=f"正在识别语音… {min(100, segment.end / duration * 100):.0f}%",
                    )
        except Exception as exc:
            raise VideoImportError(f"语音识别失败：{exc}") from exc

        if not collected:
            raise VideoImportError("没有识别到语音内容，请确认视频包含人声。")
        return collected

    def _build(
        self,
        job: ImportJob,
        wav_path: str,
        segments,
        material_id: str | None,
        source_title: str,
    ):
        units = build_sentence_units(segments)
        if len(units) < 3:
            raise VideoImportError(
                f"识别出的内容不足 3 句（本次 {len(units)} 句），无法切成三个 Part，请换一段更长的视频。"
            )
        transcript = " ".join(unit.text for unit in units)
        resolved_id = (material_id or "").strip() or f"video-{job.job_id[:8]}"
        if self.store.get(resolved_id) is not None:
            resolved_id = f"{resolved_id}-{uuid.uuid4().hex[:4]}"
        title = (job.requested_title or "").strip() or source_title
        try:
            spec = MaterialPreprocessor().process(
                material_id=resolved_id,
                title=title,
                audio_path=wav_path,
                transcript=transcript,
                timestamped_sentences=units,
            )
        except MaterialPreprocessError as exc:
            raise VideoImportError(f"素材切分失败：{exc}") from exc
        self._set(job, progress=0.6, message=f"已切分 {len(spec.sentences)} 句。")
        return spec, transcript

    def _store(self, job: ImportJob, spec, source_title: str) -> None:
        try:
            self.store.create(spec)
        except MaterialExistsError as exc:
            raise VideoImportError(str(exc)) from exc
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE materials SET source_type = 'URL', source_url = ?, source_name = ? WHERE material_id = ?",
                (job.url, f"视频导入 · {source_title}", spec.material_id),
            )
        self._set(job, progress=1.0, message="已写入素材库。")
