from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Runtime configuration kept small and explicit for the local-first P0."""

    project_root: Path = PROJECT_ROOT
    database_path: Path = PROJECT_ROOT / "data" / "language_training.sqlite3"
    materials_dir: Path = PROJECT_ROOT / "data" / "materials"
    recordings_dir: Path = PROJECT_ROOT / "data" / "recordings"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    app_name: str = "Language Training Agent"
    environment: str = "development"
    #: Weekly window policy for stats()["weekly_learning_seconds"]:
    #: "calendar" = ISO week starting Monday, "rolling7" = trailing 7 days.
    weekly_window: str = "calendar"
    #: Reading Rule Engine tolerances (Spec 33: calibrate with real samples).
    reading_speed_tolerance_pass: float = 0.15
    reading_speed_tolerance_close: float = 0.30
    reading_pause_tolerance_pass: int = 2
    reading_pause_tolerance_close: int = 4
    reading_stress_tolerance_pass: float = 0.25
    reading_stress_tolerance_close: float = 0.45
    #: Weekly assessment tuning (Spec 14/15; calibrate later).
    weekly_dictation_pass_threshold: float = 80.0
    weekly_test_sentence_count: int = 6
    reinforcement_max_sentences: int = 5
    #: Audio-quality bar for searched material (user requirement: 清晰音质).
    audio_quality_min_sample_rate: int = 16000
    audio_quality_min_snr_db: float = 15.0
    audio_quality_max_silence_ratio: float = 0.55
    audio_quality_min_duration_seconds: float = 60.0
    #: Video/URL import pipeline. ffmpeg is required for transcoding; yt-dlp
    #: and faster-whisper are only needed when importing from a video link.
    ffmpeg_path: str = ""
    ytdlp_path: str = ""
    whisper_model_size: str = "base"
    #: Spoken language for transcription; empty means auto-detect.
    whisper_language: str = ""
    #: Optional local directory holding a converted faster-whisper model
    #: (config.json + model.bin + tokenizer.json + vocabulary.txt). When set,
    #: no model download is attempted at all.
    whisper_model_dir: str = ""
    #: Hugging Face endpoint override; the public host is unreachable from
    #: some networks, so a mirror can be configured explicitly.
    hf_endpoint: str = ""
    import_dir_name: str = "imports"

    @classmethod
    def from_env(cls) -> Settings:
        project_root = Path(os.getenv("LTA_PROJECT_ROOT", str(PROJECT_ROOT))).resolve()
        data_root = project_root / "data"
        return cls(
            project_root=project_root,
            database_path=Path(os.getenv("LTA_DATABASE_PATH", str(data_root / "language_training.sqlite3"))),
            materials_dir=Path(os.getenv("LTA_MATERIALS_DIR", str(data_root / "materials"))),
            recordings_dir=Path(os.getenv("LTA_RECORDINGS_DIR", str(data_root / "recordings"))),
            processed_dir=Path(os.getenv("LTA_PROCESSED_DIR", str(data_root / "processed"))),
            app_name=os.getenv("LTA_APP_NAME", "Language Training Agent"),
            environment=os.getenv("LTA_ENVIRONMENT", "development"),
            weekly_window=os.getenv("LTA_WEEKLY_WINDOW", "calendar"),
            reading_speed_tolerance_pass=float(os.getenv("LTA_READING_SPEED_PASS", "0.15")),
            reading_speed_tolerance_close=float(os.getenv("LTA_READING_SPEED_CLOSE", "0.30")),
            reading_pause_tolerance_pass=int(os.getenv("LTA_READING_PAUSE_PASS", "2")),
            reading_pause_tolerance_close=int(os.getenv("LTA_READING_PAUSE_CLOSE", "4")),
            reading_stress_tolerance_pass=float(os.getenv("LTA_READING_STRESS_PASS", "0.25")),
            reading_stress_tolerance_close=float(os.getenv("LTA_READING_STRESS_CLOSE", "0.45")),
            weekly_dictation_pass_threshold=float(os.getenv("LTA_WEEKLY_DICTATION_PASS", "80")),
            weekly_test_sentence_count=int(os.getenv("LTA_WEEKLY_TEST_SENTENCES", "6")),
            reinforcement_max_sentences=int(os.getenv("LTA_REINFORCEMENT_MAX_SENTENCES", "5")),
            audio_quality_min_sample_rate=int(os.getenv("LTA_AUDIO_QUALITY_SAMPLE_RATE", "16000")),
            audio_quality_min_snr_db=float(os.getenv("LTA_AUDIO_QUALITY_SNR_DB", "15")),
            audio_quality_max_silence_ratio=float(os.getenv("LTA_AUDIO_QUALITY_SILENCE", "0.55")),
            audio_quality_min_duration_seconds=float(os.getenv("LTA_AUDIO_QUALITY_MIN_DURATION", "60")),
            ffmpeg_path=os.getenv("LTA_FFMPEG", ""),
            ytdlp_path=os.getenv("LTA_YTDLP", ""),
            whisper_model_size=os.getenv("LTA_WHISPER_MODEL", "base"),
            whisper_language=os.getenv("LTA_WHISPER_LANGUAGE", ""),
            hf_endpoint=os.getenv("LTA_HF_ENDPOINT", "https://hf-mirror.com"),
            import_dir_name=os.getenv("LTA_IMPORT_DIR", "imports"),
        )

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.materials_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.import_dir.mkdir(parents=True, exist_ok=True)

    @property
    def import_dir(self) -> Path:
        return self.processed_dir / self.import_dir_name

