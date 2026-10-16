"""Tests for audio extraction (Module 14).

These run real ffmpeg against real generated recordings rather than mocking the
subprocess, because the failure modes worth catching - no audio track, a
corrupt container, a missing binary - are exactly the ones a mock would hide.
"""

import subprocess
import wave

import pytest

from app.services import audio_service
from app.services.audio_service import (
    TARGET_CHANNELS,
    TARGET_SAMPLE_RATE,
    AudioExtractionError,
    audio_path_for,
    extract_audio,
    get_ffmpeg_path,
)


@pytest.fixture(scope="module")
def ffmpeg():
    return get_ffmpeg_path()


def make_video(ffmpeg, path, *, seconds=2, with_audio=True):
    """Render a small real webm, with or without an audio track."""
    command = [ffmpeg, "-y"]

    if with_audio:
        command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]

    command += [
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={seconds}:size=160x120:rate=10",
    ]

    if with_audio:
        command += ["-c:a", "libopus"]
    else:
        command += ["-an"]

    command += ["-c:v", "libvpx", "-shortest", str(path)]

    result = subprocess.run(command, capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stderr[-500:]

    return path


class TestFfmpegAvailability:
    def test_an_ffmpeg_binary_is_resolvable(self, ffmpeg):
        assert ffmpeg

    def test_the_binary_actually_runs(self, ffmpeg):
        result = subprocess.run(
            [ffmpeg, "-version"], capture_output=True, text=True, timeout=60
        )

        assert result.returncode == 0
        assert "ffmpeg version" in result.stdout


class TestExtractAudio:
    def test_extracts_a_wav_from_a_recording(self, ffmpeg, tmp_path):
        video = make_video(ffmpeg, tmp_path / "answer.webm")

        audio = extract_audio(video, output_path=tmp_path / "answer.wav")

        assert audio.exists()
        assert audio.stat().st_size > 0

    def test_audio_is_16khz_mono_as_whisper_expects(self, ffmpeg, tmp_path):
        video = make_video(ffmpeg, tmp_path / "answer.webm")

        audio = extract_audio(video, output_path=tmp_path / "answer.wav")

        with wave.open(str(audio)) as handle:
            assert handle.getframerate() == TARGET_SAMPLE_RATE
            assert handle.getnchannels() == TARGET_CHANNELS
            # 2 seconds of input, allowing for container rounding.
            assert 1.5 < handle.getnframes() / handle.getframerate() < 2.5

    def test_the_audio_file_is_kept_for_later_inspection(
        self, ffmpeg, tmp_path, monkeypatch
    ):
        """STT drops and invents words, so the audio must survive."""
        monkeypatch.setattr(audio_service, "AUDIO_UPLOAD_DIR", tmp_path / "audio")

        video = make_video(ffmpeg, tmp_path / "answer.webm")

        audio = extract_audio(video)

        assert audio.exists()
        assert audio.parent == tmp_path / "audio"

    def test_default_audio_path_mirrors_the_video_name(self, monkeypatch, tmp_path):
        monkeypatch.setattr(audio_service, "AUDIO_UPLOAD_DIR", tmp_path)

        assert audio_path_for("uploads/x/abc_question_1.webm").name == (
            "abc_question_1.wav"
        )

    def test_rejects_a_recording_with_no_audio_track(self, ffmpeg, tmp_path):
        """A camera-only recording must fail loudly, not transcribe to ""."""
        video = make_video(ffmpeg, tmp_path / "silent.webm", with_audio=False)

        with pytest.raises(AudioExtractionError):
            extract_audio(video, output_path=tmp_path / "silent.wav")

    def test_rejects_a_missing_recording(self, tmp_path):
        with pytest.raises(AudioExtractionError, match="not found"):
            extract_audio(tmp_path / "nope.webm")

    def test_rejects_a_corrupt_recording(self, tmp_path):
        video = tmp_path / "corrupt.webm"
        video.write_bytes(b"this is not a video")

        with pytest.raises(AudioExtractionError):
            extract_audio(video, output_path=tmp_path / "corrupt.wav")

    def test_reports_a_missing_ffmpeg_clearly(self, tmp_path, monkeypatch):
        video = tmp_path / "answer.webm"
        video.write_bytes(b"x")

        monkeypatch.setattr(
            audio_service, "get_ffmpeg_path", lambda: "ffmpeg-does-not-exist"
        )

        with pytest.raises(AudioExtractionError, match="not available"):
            extract_audio(video, output_path=tmp_path / "answer.wav")
