#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — VoiceDesign TTS Module

Generate character-voiced audiobook chapters using MiMo VoiceDesign API.
Each character gets a unique voice profile via director notes + style tags.

Features:
    - Character-specific voice design (director notes system)
    - Automatic emotion/style detection per text chunk
    - Resume/checkpoint (skip completed chapters)
    - Content filter handling with retry

Usage:
    python -m src.tts.voicedesign --text-dir /path/to/txt --output-dir /path/to/mp3 --config config/perspective_map.json
    python -m src.tts.voicedesign --chapter 01_初印象.txt
"""

import os
import re
import sys
import json
import time
import base64
import argparse
import glob
from pathlib import Path

from .base import TTSClient, chunk_text_by_sentence, concatenate_mp3, load_api_config
from ..analyzer.emotion import detect_style, STYLE_MAP
from ..analyzer.perspective import load_perspective_map


# ── Default Director Notes ──────────────────────────────────────────
# These are example director notes. Customize them for your own book!

DEFAULT_DIRECTORS = {
    "narrator": """你正在为小说有声书录制旁白。
声音特质：音高中等，咬字清晰，语速中等，像在讲一个故事。
叙述风格：平稳自然，娓娓道来。""",
}


def build_messages(director_note: str, style_name: str, text: str) -> list[dict]:
    """Build the two-message structure required by VoiceDesign API.

    The API expects:
        - user message: director note with style instruction
        - assistant message: <style> tag + text content

    Args:
        director_note: Character voice description / director instruction.
        style_name: Detected emotion style name.
        text: Text content to narrate.

    Returns:
        List of message dicts for the API payload.
    """
    style_desc = STYLE_MAP.get(style_name, STYLE_MAP["narrate"])
    director_with_style = f"{director_note}\n当前段落的风格是：{style_name}——{style_desc}。请用符合角色性格的声音朗读下面的文本。"

    return [
        {"role": "user", "content": director_with_style},
        {"role": "assistant", "content": f"<style>{style_desc}</style>\n{text}"}
    ]


def generate_audio_voicedesign(
    client: TTSClient,
    text: str,
    director_note: str,
    style_name: str = "narrate",
    model: str = "mimo-v2.5-tts-voicedesign",
) -> bytes | None:
    """Generate audio for a text chunk using VoiceDesign API.

    Args:
        client: TTSClient instance.
        text: Text content to convert.
        director_note: Character voice director note.
        style_name: Emotion style for this chunk.
        model: VoiceDesign model name.

    Returns:
        MP3 audio bytes, or None if content was filtered.
    """
    messages = build_messages(director_note, style_name, text)
    payload = {
        "model": model,
        "messages": messages,
        "audio": {"format": "mp3"}
    }

    for attempt in range(client.max_retries):
        try:
            result = client.call_api_urllib(payload)
            choice = result.get("choices", [{}])[0]

            # Check for content_filter (no audio data returned)
            if "message" not in choice or "audio" not in choice.get("message", {}):
                print(f"    ⚠️ No audio data (possible content_filter), retry {attempt+1}")
                time.sleep(2)
                continue

            b64_audio = choice["message"]["audio"]["data"]
            audio_bytes = base64.b64decode(b64_audio)
            return audio_bytes

        except RuntimeError as e:
            print(f"    ❌ API error (attempt {attempt+1}): {e}")
            if attempt < client.max_retries - 1:
                time.sleep(client.retry_delay * (attempt + 1))
        except Exception as e:
            print(f"    ❌ Unexpected error (attempt {attempt+1}): {e}")
            if attempt < client.max_retries - 1:
                time.sleep(client.retry_delay * (attempt + 1))

    return None


def process_chapter_voicedesign(
    txt_path: str,
    output_dir: str,
    client: TTSClient,
    perspective: str,
    director_map: dict[str, str],
    model: str = "mimo-v2.5-tts-voicedesign",
    max_chunk_len: int = 1000,
    chunk_delay: float = 0.5,
) -> bool:
    """Process a single chapter with VoiceDesign TTS.

    Args:
        txt_path: Path to the text file.
        output_dir: Directory for MP3 output.
        client: TTSClient instance.
        perspective: Character perspective key (e.g., "L", "W", "N").
        director_map: Mapping of perspective keys to director notes.
        model: VoiceDesign model name.
        max_chunk_len: Maximum characters per chunk.
        chunk_delay: Delay between API calls (seconds).

    Returns:
        True if successful, False otherwise.
    """
    txt_path = Path(txt_path)
    chapter_name = txt_path.stem
    out_path = Path(output_dir) / f"{chapter_name}_voicedesign.mp3"

    # Resume: skip if already done
    if out_path.exists() and out_path.stat().st_size > 10000:
        print(f"  [Skip] {chapter_name} (already exists)")
        return True

    print(f"\n[Process] {chapter_name} (perspective: {perspective})")

    with open(txt_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Basic cleanup
    text = raw_text.strip()
    text = re.sub(r'={5,}', '', text)
    text = re.sub(r'\d+\..*?\.txt', '', text)
    text = re.sub(r'Chapter\d+-\S+', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    if len(text) < 50:
        print(f"  ⚠️ Text too short ({len(text)} chars), skipping")
        return False

    print(f"  Text: {len(text)} chars")

    # Get director note for this perspective
    director_note = director_map.get(perspective, director_map.get("narrator", ""))

    # Chunk and generate
    chunks = chunk_text_by_sentence(text, max_len=max_chunk_len)
    print(f"  Chunks: {len(chunks)}")

    mp3_data_list = []
    for i, chunk in enumerate(chunks):
        style = detect_style(chunk)
        audio = generate_audio_voicedesign(client, chunk, director_note, style, model)
        if audio:
            mp3_data_list.append(audio)
            print(f"  ✅ Chunk {i+1}/{len(chunks)} OK ({len(audio)/1024:.1f}KB, style: {style})")
        else:
            print(f"  ⚠️ Chunk {i+1}/{len(chunks)} failed, skipping")
        time.sleep(chunk_delay)

    if mp3_data_list:
        concatenate_mp3(mp3_data_list, str(out_path))
        size_mb = out_path.stat().st_size / 1024 / 1024
        print(f"  ✅ Done: {out_path.name} ({size_mb:.2f}MB, {len(mp3_data_list)}/{len(chunks)} chunks)")
        return True
    else:
        print(f"  ❌ All chunks failed: {chapter_name}")
        return False


def main():
    parser = argparse.ArgumentParser(description="VoiceDesign TTS Audiobook Generator")
    parser.add_argument("--text-dir", required=True, help="Directory containing TXT files")
    parser.add_argument("--output-dir", required=True, help="Directory for MP3 output")
    parser.add_argument("--config", required=True, help="Path to perspective_map.json")
    parser.add_argument("--chapter", type=str, help="Process single chapter by filename")
    parser.add_argument("--start", type=int, default=0, help="Start chapter index")
    parser.add_argument("--end", type=int, default=None, help="End chapter index (exclusive)")
    parser.add_argument("--model", default="mimo-v2.5-tts-voicedesign", help="VoiceDesign model name")
    args = parser.parse_args()

    api_key, base_url = load_api_config()
    client = TTSClient(api_key, base_url)

    # Load perspective map and director notes
    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    perspective_map = config.get("perspective_map", {})
    director_map = config.get("director_notes", DEFAULT_DIRECTORS)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Get chapter list
    text_dir = Path(args.text_dir)
    if args.chapter:
        chapters = [(args.chapter, perspective_map.get(Path(args.chapter).stem.split("_")[0], "narrator"))]
    else:
        all_txt = sorted(text_dir.glob("*.txt"))
        start = args.start
        end = args.end if args.end is not None else len(all_txt)
        chapters = []
        for txt_path in all_txt[start:end]:
            ch_key = txt_path.stem.split("_")[0]
            perspective = perspective_map.get(ch_key, "narrator")
            chapters.append((str(txt_path), perspective))

    success, fail, skip = 0, 0, 0
    for txt_path, perspective in chapters:
        try:
            if process_chapter_voicedesign(
                txt_path, str(output_dir), client, perspective, director_map, model=args.model
            ):
                success += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            fail += 1

    print(f"\n{'='*60}")
    print(f"Batch complete! Success:{success} Failed:{fail} Skipped:{skip}")


if __name__ == "__main__":
    main()
