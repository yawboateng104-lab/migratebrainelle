# app/services/video_merge_service.py
import os
import shlex
import subprocess
from pathlib import Path

from app.config import settings


class VideoMergeError(Exception):
    """Raised when ffmpeg merge fails."""


def _run_command(cmd: list[str]) -> None:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise VideoMergeError(
            f"Command failed ({result.returncode}): {' '.join(shlex.quote(c) for c in cmd)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def concatenate_videos(
    input_video_paths: list[str],
    output_video_path: str,
) -> str:
    """
    Concatenate multiple MP4 clips into one MP4 using ffmpeg concat demuxer.
    Assumes compatible codecs/streams.
    """
    if not input_video_paths:
        raise VideoMergeError("No input videos provided for concatenation")

    output_video_path = str(Path(output_video_path))
    work_dir = Path(output_video_path).parent
    work_dir.mkdir(parents=True, exist_ok=True)

    concat_file = work_dir / "concat_inputs.txt"
    concat_lines = []
    for path in input_video_paths:
        concat_lines.append(f"file '{os.path.abspath(path)}'")
    concat_file.write_text("\n".join(concat_lines), encoding="utf-8")

    cmd = [
        settings.FFMPEG_BIN,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        output_video_path,
    ]
    _run_command(cmd)
    return output_video_path


def merge_video_with_voiceover(
    input_video_path: str,
    voiceover_audio_path: str,
    output_video_path: str,
) -> str:
    """
    Add narration to a stitched video. Shortest stream wins.
    """
    output_video_path = str(Path(output_video_path))
    Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        settings.FFMPEG_BIN,
        "-y",
        "-i",
        input_video_path,
        "-i",
        voiceover_audio_path,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-shortest",
        output_video_path,
    ]
    _run_command(cmd)
    return output_video_path


def create_thumbnail(
    input_video_path: str,
    output_image_path: str,
    timestamp_seconds: int = 1,
) -> str:
    """
    Extract a single frame as thumbnail.
    """
    output_image_path = str(Path(output_image_path))
    Path(output_image_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        settings.FFMPEG_BIN,
        "-y",
        "-ss",
        str(timestamp_seconds),
        "-i",
        input_video_path,
        "-frames:v",
        "1",
        output_image_path,
    ]
    _run_command(cmd)
    return output_image_path
