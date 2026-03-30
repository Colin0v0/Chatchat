from __future__ import annotations

import subprocess


def transcode_audio_to_wav(input_bytes: bytes) -> bytes:
    if not input_bytes:
        raise RuntimeError("Audio payload is empty.")

    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        "pipe:1",
    ]
    return run_ffmpeg(args=args, input_bytes=input_bytes)


def run_ffmpeg(*, args: list[str], input_bytes: bytes) -> bytes:
    try:
        completed = subprocess.run(
            args,
            input=input_bytes,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required but not found in PATH.") from exc

    if completed.returncode != 0:
        details = completed.stderr.decode("utf-8", errors="ignore").strip()
        if details:
            raise RuntimeError(f"ffmpeg failed: {details}")
        raise RuntimeError("ffmpeg failed to process audio.")

    if not completed.stdout:
        raise RuntimeError("ffmpeg produced an empty output.")

    return completed.stdout
