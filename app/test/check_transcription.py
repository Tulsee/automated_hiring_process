"""Manual check: run real ffmpeg + whisper over a recording.

The pytest suite stubs whisper out to stay fast and offline. This script runs
the real thing, which downloads the model on first use (~140MB for "base").

    uv run python app/test/check_transcription.py
    uv run python app/test/check_transcription.py path/to/answer.webm

With no path it synthesises a spoken answer with Windows TTS, muxes it into a
webm, and transcribes that - so the whole chain is exercised without needing a
recorded interview.
"""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.audio_service import get_ffmpeg_path
from app.services.transcription_service import transcribe_answer

SPOKEN_TEXT = (
    "I have five years of backend development experience. "
    "I mainly build REST APIs in Python using FastAPI, with MongoDB for "
    "storage. Recently I designed a service that handles about two thousand "
    "requests per second."
)


def synthesise_speech(wav_path: Path) -> bool:
    """Speak SPOKEN_TEXT into a WAV using Windows TTS. False if unavailable."""
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{wav_path}'); "
        f"$s.Speak('{SPOKEN_TEXT}'); "
        "$s.Dispose()"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    return result.returncode == 0 and wav_path.exists()


def build_sample_recording(directory: Path) -> Path:
    """A webm that looks like a real answer: spoken audio plus video."""
    ffmpeg = get_ffmpeg_path()

    wav_path = directory / "spoken.wav"

    video_path = directory / "sample_answer.webm"

    if synthesise_speech(wav_path):
        print(f"Synthesised speech: {wav_path.name}")

        audio_input = ["-i", str(wav_path)]
    else:
        print("Windows TTS unavailable; falling back to a 440Hz tone.")
        print("(Expect an empty or flagged transcript - a tone has no words.)")

        audio_input = ["-f", "lavfi", "-i", "sine=frequency=440:duration=5"]

    command = [
        ffmpeg,
        "-y",
        *audio_input,
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=30:size=320x240:rate=10",
        "-c:a",
        "libopus",
        "-c:v",
        "libvpx",
        "-shortest",
        str(video_path),
    ]

    result = subprocess.run(command, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{result.stderr[-800:]}")

    return video_path


async def main():
    paths = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    with tempfile.TemporaryDirectory() as directory:
        if paths:
            video_path = Path(paths[0])

            if not video_path.exists():
                raise SystemExit(f"Not found: {video_path}")
        else:
            video_path = build_sample_recording(Path(directory))

        print(f"\nRecording    : {video_path}")
        print(f"Whisper model: {settings.WHISPER_MODEL}")
        print("\nTranscribing (first run downloads the model)...\n")

        transcript = await transcribe_answer(video_path)

    print("========== TRANSCRIPT ==========\n")
    print(transcript["text"] or "(empty)")
    print("\n================================\n")
    print(f"words        : {transcript['word_count']}")
    print(f"language     : {transcript['language']} "
          f"(p={transcript['language_probability']})")
    print(f"duration     : {transcript['duration_seconds']}s")
    print(f"segments     : {len(transcript['segments'])}")
    print(f"flags        : {transcript['flags'] or 'none'}")
    print(f"audio kept at: {transcript['audio_path']}")

    if transcript["segments"]:
        print("\nFirst segments:")

        for segment in transcript["segments"][:5]:
            print(
                f"  [{segment['start']:6.2f} - {segment['end']:6.2f}] "
                f"(conf {segment['avg_logprob']}) {segment['text']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
