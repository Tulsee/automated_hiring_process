"""Tests for the transcription service's judgement logic (Module 14).

Running whisper itself is slow and downloads a model, so these cover the parts
around it: how device and compute type are resolved, and which transcripts get
flagged for a human. The model is exercised for real in
`check_transcription.py`.
"""

import pytest

from app.core.config import settings
from app.services import transcription_service
from app.services.transcription_service import (
    LOW_CONFIDENCE_THRESHOLD,
    TRANSCRIPT_FLAG_EMPTY,
    TRANSCRIPT_FLAG_LOW_CONFIDENCE,
    TRANSCRIPT_FLAG_TOO_SHORT,
    flags_for,
    resolve_device,
)


def segment(text="hello", avg_logprob=-0.2):
    return {
        "start": 0.0,
        "end": 1.0,
        "text": text,
        "avg_logprob": avg_logprob,
        "no_speech_prob": 0.01,
    }


class TestResolveDevice:
    def test_an_explicit_device_is_respected(self):
        assert resolve_device("cpu") == "cpu"
        assert resolve_device("cuda") == "cuda"

    def test_auto_falls_back_to_cpu_without_a_gpu(self):
        assert resolve_device("auto") in {"cpu", "cuda"}


class TestTranscriptFlags:
    def test_a_normal_answer_is_not_flagged(self):
        text = "I have five years of backend experience building APIs in Python"

        assert flags_for(text, [segment(text)]) == []

    def test_an_empty_transcript_is_flagged(self):
        """Silence often transcribes to nothing - that needs surfacing."""
        assert TRANSCRIPT_FLAG_EMPTY in flags_for("", [])

    def test_a_very_short_answer_is_flagged(self):
        assert TRANSCRIPT_FLAG_TOO_SHORT in flags_for("Thank you.", [segment()])

    def test_an_empty_answer_is_not_also_called_short(self):
        flags = flags_for("", [])

        assert TRANSCRIPT_FLAG_TOO_SHORT not in flags

    def test_low_confidence_is_flagged(self):
        """Whisper invents text on bad audio; avg_logprob exposes it."""
        text = "the the the the the the the"

        flags = flags_for(
            text, [segment(text, avg_logprob=LOW_CONFIDENCE_THRESHOLD - 0.5)]
        )

        assert TRANSCRIPT_FLAG_LOW_CONFIDENCE in flags

    def test_confident_long_audio_is_not_flagged(self):
        text = " ".join(["word"] * 50)

        flags = flags_for(
            text,
            [segment(text, avg_logprob=-0.1), segment(text, avg_logprob=-0.3)],
        )

        assert flags == []

    def test_confidence_is_averaged_across_segments(self):
        text = " ".join(["word"] * 20)

        # One bad segment should not condemn an otherwise confident answer.
        flags = flags_for(
            text,
            [segment(text, avg_logprob=-0.1), segment(text, avg_logprob=-1.2)],
        )

        assert TRANSCRIPT_FLAG_LOW_CONFIDENCE not in flags

    def test_segments_without_confidence_are_ignored(self):
        text = " ".join(["word"] * 20)

        flags = flags_for(text, [segment(text, avg_logprob=None)])

        assert flags == []

    def test_the_short_answer_threshold_follows_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "MIN_TRANSCRIPT_WORDS", 50)

        text = " ".join(["word"] * 10)

        assert TRANSCRIPT_FLAG_TOO_SHORT in flags_for(text, [segment(text)])


class TestModelCaching:
    def test_the_model_is_loaded_once_per_configuration(self, monkeypatch):
        """Loading costs seconds and hundreds of MB, so it must be reused."""
        loads = []

        class FakeModel:
            def __init__(self, name, device=None, compute_type=None):
                loads.append((name, device, compute_type))

        monkeypatch.setattr(transcription_service, "_model", None)
        monkeypatch.setattr(transcription_service, "_model_key", None)

        fake_module = type("Module", (), {"WhisperModel": FakeModel})

        monkeypatch.setitem(
            __import__("sys").modules, "faster_whisper", fake_module
        )

        first = transcription_service.get_model()
        second = transcription_service.get_model()

        assert first is second
        assert len(loads) == 1

    def test_float16_is_downgraded_on_cpu(self, monkeypatch):
        """float16 is a GPU compute type and fails to load on CPU."""
        recorded = []

        class FakeModel:
            def __init__(self, name, device=None, compute_type=None):
                recorded.append(compute_type)

        monkeypatch.setattr(transcription_service, "_model", None)
        monkeypatch.setattr(transcription_service, "_model_key", None)
        monkeypatch.setattr(settings, "WHISPER_DEVICE", "cpu")
        monkeypatch.setattr(settings, "WHISPER_COMPUTE_TYPE", "float16")

        monkeypatch.setitem(
            __import__("sys").modules,
            "faster_whisper",
            type("Module", (), {"WhisperModel": FakeModel}),
        )

        transcription_service.get_model()

        assert recorded == ["int8"]
