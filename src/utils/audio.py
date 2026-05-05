#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — Audio Utilities

MP3 concatenation and audio file handling.
"""

import os
from pathlib import Path


def concatenate_mp3(mp3_data_list: list[bytes], output_path: str) -> int:
    """Concatenate MP3 audio chunks into a single file.

    Simple binary append — works for basic playback without ffmpeg.
    For production use, consider ffmpeg or pydub for proper concatenation
    with frame-level alignment.

    Args:
        mp3_data_list: List of MP3 bytes objects.
        output_path: Output file path.

    Returns:
        Total bytes written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with open(output_path, "wb") as f:
        for data in mp3_data_list:
            f.write(data)
            total += len(data)
    return total


def get_mp3_duration_approx(file_path: str) -> float:
    """Estimate MP3 duration from file size (rough approximation).

    Assumes ~128kbps bitrate. For accurate duration, use mutagen or ffmpeg.

    Args:
        file_path: Path to MP3 file.

    Returns:
        Estimated duration in seconds.
    """
    size = os.path.getsize(file_path)
    # 128kbps = 16000 bytes/second
    return size / 16000


def scan_completed_chapters(output_dir: str, min_size: int = 10000) -> list[str]:
    """Scan output directory for completed chapter MP3 files.

    Args:
        output_dir: Directory to scan.
        min_size: Minimum file size in bytes to count as completed.

    Returns:
        List of completed chapter filenames.
    """
    completed = []
    for f in Path(output_dir).glob("*.mp3"):
        if f.stat().st_size > min_size:
            completed.append(f.name)
    return sorted(completed)
