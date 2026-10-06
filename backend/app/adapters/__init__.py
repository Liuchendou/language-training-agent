"""Adapters for replaceable external capabilities.

Concrete implementations wired into the app:
- ``speech``: local ASR (faster-whisper) with word/segment timestamps.
- ``audio``: deterministic reading analysis (duration / pause / RMS energy).
- ``voa_material`` / ``web_material`` / ``bilibili_material``: material sources.

No LLM provider is wired in: every training rule is a deterministic
implementation (P0 Spec 2.1). The former placeholder ports (``llm.py`` and
``material.py``) were unused skeletons and have been removed.
"""
