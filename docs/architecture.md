# Architecture & Design Notes

## Overview

ai-audiobook-maker is a modular toolkit that turns text (from PDFs, images, or raw text) into character-voiced audiobooks using AI TTS APIs.

The pipeline is:

```
PDF Files → Text Extraction → Clean TXT → [OCR if needed] → TTS Generation → MP3 Audiobook
```

## Module Design

### 1. Text Extraction (`src/extractor/`)

**8-Step Cleaning Pipeline:**

| Step | Purpose | Regex/Operation |
|------|---------|-----------------|
| 1 | Remove standalone single letters (PDF column artifacts) | `\n[a-zA-Z]\n` |
| 2 | Remove inline single letters between Chinese chars | `([\u4e00-\u9fff])([a-zA-Z])([\u4e00-\u9fff])` |
| 3 | Remove trailing single letters after Chinese punctuation | `([\u4e00-\u9fff，。！？…])\s*[a-zA-Z]\s*$` |
| 4 | Remove leading single letters before Chinese chars | `^\s*[a-zA-Z]\s+(?=[\u4e00-\u9fff])` |
| 5 | Remove superscript digits | `[¹²³⁴⁵⁶⁷⁸⁹⁰]` |
| 6 | Collapse excessive blank lines | `\n{3,}` → `\n\n` |
| 7 | Merge lines → split by sentence-ending punctuation | Join all → split by `。！？` |
| 8 | Final whitespace cleanup | Trim and normalize spaces |

### 2. Image OCR (`src/ocr/`)

Uses multimodal AI (MiMo V2.5) to OCR image-only pages:
- Image compression (resize + JPEG quality reduction) for API limits
- Retry with rate-limit (429) handling
- Configurable prompt for different OCR needs

### 3. TTS Engine (`src/tts/`)

**Base Client** (`base.py`):
- Dual HTTP backends: `requests.Session` (for basic TTS) and `urllib` (for VoiceDesign)
- Automatic retry with exponential backoff
- SSL verification control (disabled by default for corporate proxy environments)
- Text chunking: two strategies (punctuation-based and sentence-boundary)

**Basic TTS** (`mimo_tts.py`):
- Single voice for all narration
- Uses `mimo-v2-tts` model
- Resume/checkpoint: skip files > 10KB

**VoiceDesign TTS** (`voicedesign.py`):
- Character-specific voice profiles via director notes
- Emotion/style detection per chunk
- Two-message API structure (user=director+style, assistant=style_tag+text)
- Content filter handling (skip filtered chunks, continue with rest)

### 4. Analyzer (`src/analyzer/`)

**Perspective Detection** (`perspective.py`):
- Config-based chapter → character mapping (JSON)
- Best-effort text-based detection heuristic (character addressed by others = not narrator)

**Emotion Detection** (`emotion.py`):
- Keyword matching with priority ordering
- 7 built-in styles + extensible custom styles
- Keywords are Chinese-language specific (can be extended for other languages)

## API Details

### MiMo VoiceDesign API Format

This is a **non-standard** OpenAI-compatible endpoint:

```python
# Endpoint: POST /v1/chat/completions
payload = {
    "model": "mimo-v2.5-tts-voicedesign",
    "messages": [
        {
            "role": "user",
            "content": "<director_note>\n当前段落的风格是：<style_name>——<style_desc>。请用符合角色性格的声音朗读下面的文本。"
        },
        {
            "role": "assistant",
            "content": "<style><style_desc></style>\n<text_content>"
        }
    ],
    "audio": {"format": "mp3"}
}
```

**NOT** the standard `/audio/speech` endpoint or single-message format.

### Response Format

```python
result["choices"][0]["message"]["audio"]["data"]  # Base64-encoded MP3
```

## Key Design Decisions

1. **No ffmpeg dependency** — MP3 chunks are concatenated via binary append. This works for basic playback but may have frame alignment issues. Users can opt for pydub/ffmpeg for production quality.

2. **SSL disabled by default** — Corporate proxy environments often break SSL. The client sets `verify=False` and `trust_env=False` by default. Can be overridden.

3. **Environment variables for secrets** — API keys via `MIMO_API_KEY` env var or `.env` file, never hardcoded or in config files.

4. **Config-based perspective mapping** — Rather than trying to auto-detect narrator identity (which is unreliable), we use an explicit JSON mapping. Auto-detection is available as a helper but not the default.

5. **Content filter tolerance** — The API may filter intimate/violent content. Failed chunks are logged and skipped rather than halting the entire process.
