#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — Basic MiMo TTS Module

Convert text files to MP3 audiobook chapters using MiMo TTS API.
No character voice design — single voice for all narration.

Usage:
    python -m src.tts.mimo_tts --text-dir /path/to/txt --output-dir /path/to/mp3
    python -m src.tts.mimo_tts --chapter 01_初印象.txt
    python -m src.tts.mimo_tts --start 0 --end 5
"""

import os
import sys
import argparse
from pathlib import Path

from .base import TTSClient, chunk_text_by_punctuation, concatenate_mp3, load_api_config


def text_to_speech(client: TTSClient, text: str, model: str = "mimo-v2-tts", voice: str = "default_zh") -> bytes:
    """Convert text to speech audio bytes.

    Args:
        client: TTSClient instance.
        text: Text content to convert.
        model: TTS model name.
        voice: Voice identifier.

    Returns:
        MP3 audio bytes.

    Raises:
        RuntimeError: If API call fails after all retries.
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "assistant", "content": text}
        ],
        "audio": {"format": "mp3", "voice": voice}
    }
    result = client.call_api_requests(payload)
    b64_audio = result["choices"][0]["message"]["audio"]["data"]
    return __import__("base64").b64decode(b64_audio)


def process_chapter(
    txt_path: Path,
    output_dir: Path,
    client: TTSClient,
    model: str = "mimo-v2-tts",
    voice: str = "default_zh",
    max_chars: int = 1000,
    chunk_delay: float = 1.5,
) -> bool:
    """Process a single chapter: read text → chunk → TTS → save MP3.

    Args:
        txt_path: Path to the text file.
        output_dir: Directory for MP3 output.
        client: TTSClient instance.
        model: TTS model name.
        voice: Voice identifier.
        max_chars: Maximum characters per chunk.
        chunk_delay: Delay between chunks (seconds).

    Returns:
        True if chapter was successfully processed, False otherwise.
    """
    import time
    chapter_name = txt_path.stem
    final_path = output_dir / f"{chapter_name}.mp3"

    # Resume: skip if already done
    if final_path.exists() and final_path.stat().st_size > 10000:
        print(f"  [Skip] {chapter_name} (already exists)")
        return True

    print(f"\n[Process] {chapter_name}")

    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        print("  [Skip] Empty file")
        return False

    print(f"  Text: {len(text)} chars")
    chunks = chunk_text_by_punctuation(text, max_chars=max_chars)
    print(f"  Chunks: {len(chunks)}")

    all_audio = b""
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
        try:
            audio_bytes = text_to_speech(client, chunk, model=model, voice=voice)
            all_audio += audio_bytes
            print(f"    OK ({len(audio_bytes)/1024:.1f} KB)")
            time.sleep(chunk_delay)
        except Exception as e:
            print(f"    FAIL: {e}")
            return False

    concatenate_mp3([all_audio], str(final_path))
    print(f"  [Done] {final_path.name} ({len(all_audio)/1024:.1f} KB)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Basic MiMo TTS Audiobook Generator")
    parser.add_argument("--text-dir", required=True, help="Directory containing TXT files")
    parser.add_argument("--output-dir", required=True, help="Directory for MP3 output")
    parser.add_argument("--chapter", type=str, help="Process single chapter by filename")
    parser.add_argument("--start", type=int, default=0, help="Start chapter index")
    parser.add_argument("--end", type=int, default=None, help="End chapter index (exclusive)")
    parser.add_argument("--model", default="mimo-v2-tts", help="TTS model name")
    parser.add_argument("--voice", default="default_zh", help="Voice identifier")
    args = parser.parse_args()

    api_key, base_url = load_api_config()
    client = TTSClient(api_key, base_url)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Connectivity test
    print("[Test] API connectivity...")
    try:
        audio = text_to_speech(client, "你好，测试。", model=args.model, voice=args.voice)
        print(f"[OK] Test audio: {len(audio)/1024:.1f} KB")
    except Exception as e:
        print(f"[FAIL] API unavailable: {e}")
        return

    # Determine chapters to process
    text_dir = Path(args.text_dir)
    if args.chapter:
        txt_files = [text_dir / args.chapter]
    else:
        all_txt = sorted(text_dir.glob("*.txt"))
        start = args.start
        end = args.end if args.end is not None else len(all_txt)
        txt_files = all_txt[start:end]

    success, fail, skip = 0, 0, 0
    for txt_path in txt_files:
        if not txt_path.exists():
            print(f"\n[Skip] File not found: {txt_path.name}")
            skip += 1
            continue
        try:
            if process_chapter(txt_path, output_dir, client, model=args.model, voice=args.voice):
                success += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            fail += 1

    print(f"\n{'='*50}")
    print(f"Complete! Success:{success} Failed:{fail} Skipped:{skip}")


if __name__ == "__main__":
    main()
