"""Transcribe interview answers with faster-whisper.

Speech-to-text has characteristic failure modes: it drops words on quiet or
clipped audio, and it invents plausible-sounding text when there is nothing to
transcribe (silence often becomes a stray "Thank you."). So a transcript is
stored with the signals needed to judge it - per-segment timings, the model's
own confidence, the detected language - and short or empty results are flagged
for a human rather than passed downstream as fact.
"""

import logging
import math
import wave
from pathlib import Path

import anyio
import numpy as np

from app.core.config import settings
from app.services.audio_service import extract_audio

logger = logging.getLogger(__name__)

# Loading a model costs seconds and hundreds of MB, so one is reused.
_model = None
_model_key: tuple[str, str, str] | None = None

TRANSCRIPT_FLAG_EMPTY = "empty_transcript"
TRANSCRIPT_FLAG_TOO_SHORT = "transcript_too_short"
TRANSCRIPT_FLAG_LOW_CONFIDENCE = "low_confidence"

# avg_logprob is a log probability; below this the model was guessing.
LOW_CONFIDENCE_THRESHOLD = -1.0


class TranscriptionError(RuntimeError):
    """The audio could not be transcribed."""


def load_wav_as_float32(audio_path: Path) -> np.ndarray:
    """Read a 16 kHz mono PCM WAV into the array whisper expects.

    faster-whisper can decode media itself, but that path goes through PyAV,
    whose newer releases broke the call it makes. Since `extract_audio` already
    produces exactly the format whisper wants, decoding it here with the
    standard library removes that dependency from the critical path.
    """
    with wave.open(str(audio_path)) as handle:
        if handle.getsampwidth() != 2:
            raise TranscriptionError(
                f"Expected 16-bit audio, got {handle.getsampwidth() * 8}-bit"
            )

        frames = handle.readframes(handle.getnframes())

        channels = handle.getnchannels()

    samples = np.frombuffer(frames, dtype=np.int16)

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    # int16 PCM to the normalised float32 whisper expects.
    return (samples.astype(np.float32) / 32768.0).copy()


def resolve_device(device: str) -> str:
    """Pick a device, treating "auto" as cuda-if-present."""
    if device != "auto":
        return device

    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:  # pragma: no cover - depends on the environment
        pass

    return "cpu"


def get_model():
    """The shared WhisperModel for the configured settings."""
    global _model, _model_key

    device = resolve_device(settings.WHISPER_DEVICE)

    compute_type = settings.WHISPER_COMPUTE_TYPE

    if device == "cpu" and compute_type in {"float16", "fp16"}:
        # float16 is a GPU compute type; on CPU it fails to load.
        compute_type = "int8"

    key = (settings.WHISPER_MODEL, device, compute_type)

    if _model is not None and _model_key == key:
        return _model

    from faster_whisper import WhisperModel

    logger.info(
        "Loading whisper model '%s' (device=%s, compute_type=%s)",
        settings.WHISPER_MODEL,
        device,
        compute_type,
    )

    _model = WhisperModel(
        settings.WHISPER_MODEL, device=device, compute_type=compute_type
    )

    _model_key = key

    return _model


def flags_for(text: str, segments: list[dict]) -> list[str]:
    """What a human should be warned about in this transcript."""
    flags = []

    word_count = len(text.split())

    if word_count == 0:
        flags.append(TRANSCRIPT_FLAG_EMPTY)
    elif word_count < settings.MIN_TRANSCRIPT_WORDS:
        flags.append(TRANSCRIPT_FLAG_TOO_SHORT)

    confidences = [
        segment["avg_logprob"]
        for segment in segments
        if segment.get("avg_logprob") is not None
    ]

    if confidences:
        mean_confidence = sum(confidences) / len(confidences)

        if mean_confidence < LOW_CONFIDENCE_THRESHOLD:
            flags.append(TRANSCRIPT_FLAG_LOW_CONFIDENCE)

    return flags


def transcribe_audio_sync(audio_path: str | Path) -> dict:
    """Transcribe a WAV file. Blocking; call via `transcribe_answer`."""
    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise TranscriptionError(f"Audio not found: {audio_path}")

    model = get_model()

    audio = load_wav_as_float32(audio_path)

    try:
        segment_iterator, info = model.transcribe(
            audio,
            beam_size=settings.WHISPER_BEAM_SIZE,
            vad_filter=True,
        )
    except Exception as error:
        raise TranscriptionError(
            f"Transcription failed for {audio_path.name}: {error}"
        ) from error

    segments = [
        {
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment.text.strip(),
            "avg_logprob": (
                round(segment.avg_logprob, 4)
                if segment.avg_logprob is not None
                and not math.isnan(segment.avg_logprob)
                else None
            ),
            "no_speech_prob": (
                round(segment.no_speech_prob, 4)
                if segment.no_speech_prob is not None
                else None
            ),
        }
        # faster-whisper yields lazily; the work happens here.
        for segment in segment_iterator
    ]

    text = " ".join(segment["text"] for segment in segments).strip()

    return {
        "text": text,
        "segments": segments,
        "language": info.language,
        "language_probability": round(info.language_probability or 0, 4),
        "duration_seconds": round(info.duration or 0, 2),
        "word_count": len(text.split()),
        "model": settings.WHISPER_MODEL,
        "flags": flags_for(text, segments),
    }


async def transcribe_answer(video_path: str | Path) -> dict:
    """Extract the audio from a recorded answer and transcribe it.

    Both steps block, so they run in a worker thread to keep the event loop
    responsive. The audio file is kept and its path returned.
    """
    audio_path = await anyio.to_thread.run_sync(extract_audio, video_path)

    transcript = await anyio.to_thread.run_sync(transcribe_audio_sync, audio_path)

    transcript["audio_path"] = str(audio_path)

    logger.info(
        "Transcribed %s: %d words, language=%s, flags=%s",
        Path(video_path).name,
        transcript["word_count"],
        transcript["language"],
        transcript["flags"] or "none",
    )

    return transcript
