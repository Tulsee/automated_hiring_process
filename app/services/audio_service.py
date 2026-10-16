"""Pull the audio track out of a recorded answer with ffmpeg.

The extracted audio is kept on disk rather than thrown away after
transcription: speech-to-text sometimes drops or invents words, and the only
way to check a suspicious transcript is to listen to the audio it came from.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_UPLOAD_DIR = Path("uploads/interview_audio")
AUDIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Whisper resamples to 16 kHz mono internally, so extract it that way and skip
# a conversion.
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1

FFMPEG_TIMEOUT_SECONDS = 300


class AudioExtractionError(RuntimeError):
    """ffmpeg could not produce audio from the recording."""


def get_ffmpeg_path() -> str:
    """The ffmpeg binary, preferring the one bundled with imageio-ffmpeg.

    Falling back to PATH means a system ffmpeg still works if the bundled
    package is not installed.
    """
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover - depends on the environment
        logger.info("imageio-ffmpeg unavailable; falling back to ffmpeg on PATH")
        return "ffmpeg"


def audio_path_for(video_path: Path) -> Path:
    return AUDIO_UPLOAD_DIR / f"{Path(video_path).stem}.wav"


def extract_audio(video_path: str | Path, output_path: Path | None = None) -> Path:
    """Write the recording's audio track to a 16 kHz mono WAV file.

    Returns the path to the audio. Raises `AudioExtractionError` if ffmpeg
    fails or produces nothing - a silent or audio-less recording should be
    surfaced, not transcribed as an empty string.
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise AudioExtractionError(f"Recording not found: {video_path}")

    output_path = output_path or audio_path_for(video_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        get_ffmpeg_path(),
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-ac",
        str(TARGET_CHANNELS),
        str(output_path),
    ]

    logger.info("Extracting audio: %s -> %s", video_path.name, output_path.name)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise AudioExtractionError(
            f"ffmpeg timed out after {FFMPEG_TIMEOUT_SECONDS}s on {video_path.name}"
        ) from error
    except FileNotFoundError as error:
        raise AudioExtractionError(
            "ffmpeg is not available; install imageio-ffmpeg or add ffmpeg to PATH"
        ) from error

    if result.returncode != 0:
        # ffmpeg puts the useful part of its diagnostics at the end.
        stderr_tail = "\n".join(result.stderr.strip().splitlines()[-5:])

        raise AudioExtractionError(
            f"ffmpeg failed on {video_path.name}: {stderr_tail}"
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise AudioExtractionError(
            f"ffmpeg produced no audio for {video_path.name}; "
            "the recording may have no audio track"
        )

    logger.info(
        "Audio extracted: %s (%d bytes)", output_path.name, output_path.stat().st_size
    )

    return output_path
