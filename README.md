# 🎧 AI Audiobook Maker

Turn any text/PDF into a character-voiced audiobook using AI TTS APIs.

Built on [MiMo TTS](https://platform.mimofire.com/) VoiceDesign API, featuring **character-specific voice profiles** with **automatic emotion detection** for each text segment.

## ✨ Features

- **PDF Text Extraction** — 8-step cleaning pipeline removes PDF artifacts (stray letters, broken lines, superscripts) and produces clean paragraph-split text
- **Image OCR** — Multimodal AI OCR for image-only/scanned pages with retry & rate-limit handling
- **Basic TTS** — Single-voice text-to-speech for straightforward narration
- **VoiceDesign TTS** — Character-specific voice design with director notes system
  - Each character gets a unique voice profile
  - Automatic emotion/style detection per text chunk
  - `<style>` tag integration for fine-grained voice control
- **Resume/Checkpoint** — Skip already-generated chapters, pick up where you left off
- **Configurable** — Environment variables for API keys, JSON config for character mapping

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/your-username/ai-audiobook-maker.git
cd ai-audiobook-maker
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env and add your MiMo API key
```

Or set environment variable directly:

```bash
export MIMO_API_KEY=your_key_here
export MIMO_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1  # optional
```

Get your API key at [MiMo Platform](https://platform.mimofire.com/).

### 3. Extract Text from PDF

```bash
python -m src.extractor.pdf_extractor --pdf-dir /path/to/pdfs --output-dir /path/to/txt
```

### 4. Generate Audiobook

**Basic TTS (single voice):**

```bash
python -m src.tts.mimo_tts --text-dir /path/to/txt --output-dir /path/to/mp3
```

**VoiceDesign TTS (character voices):**

```bash
# First, create your character mapping config (see config/perspective_map.json)
python -m src.tts.voicedesign \
  --text-dir /path/to/txt \
  --output-dir /path/to/mp3 \
  --config config/perspective_map.json
```

**Process a single chapter:**

```bash
python -m src.tts.mimo_tts --text-dir /path/to/txt --output-dir /path/to/mp3 --chapter 01_Chapter_One.txt
```

**Process a range:**

```bash
python -m src.tts.mimo_tts --text-dir /path/to/txt --output-dir /path/to/mp3 --start 0 --end 5
```

## 📁 Project Structure

```
ai-audiobook-maker/
├── README.md
├── LICENSE                    # MIT
├── .env.example               # API key template
├── requirements.txt
├── config/
│   └── perspective_map.json   # Chapter → character mapping + director notes
├── src/
│   ├── extractor/
│   │   └── pdf_extractor.py   # PDF → clean TXT with 8-step pipeline
│   ├── ocr/
│   │   └── image_ocr.py       # Multimodal AI OCR for image pages
│   ├── tts/
│   │   ├── base.py            # Shared API client, chunking, retry, SSL
│   │   ├── mimo_tts.py        # Basic single-voice TTS
│   │   └── voicedesign.py     # Character VoiceDesign TTS (core)
│   ├── analyzer/
│   │   ├── perspective.py     # Chapter perspective detection
│   │   └── emotion.py         # Emotion/style keyword detection
│   └── utils/
│       ├── config.py          # Env vars & config loading
│       └── audio.py           # MP3 concatenation utilities
├── examples/
│   └── example_config.json    # Full example with multiple characters
└── docs/
    └── architecture.md        # Design & architecture notes
```

## 🎭 Director Notes System

The VoiceDesign module uses a **director notes** system to create character-specific voices:

1. **Director Note** — Describes the character's personality, voice qualities, and speaking style
2. **Style Detection** — Each text chunk is analyzed for emotional tone (embarrass, shock, annoy, vulnerable, introspect, cheerful, narrate)
3. **`<style>` Tags** — The detected style is injected into the API request as an XML-style tag that controls voice modulation

### Example Director Note:

```json
{
    "director_notes": {
        "narrator": "你正在为有声书录制旁白。声音特质：音高中等，咬字清晰，语速中等。",
        "character_a": "这一章是从角色A的视角叙述的——活泼开朗，声音明亮温暖，语速中等偏快。像阳光洒进房间。",
        "character_b": "这一章是从角色B的视角叙述的——克制内敛，咬字精准，语速偏慢。像一杯没加糖的黑咖啡。"
    }
}
```

### Emotion Styles:

| Style | Description | Example Triggers |
|-------|-------------|-----------------|
| narrate | 平静叙述 | default |
| introspect | 内心独白，低声呢喃 | 我想、为什么、也许 |
| embarrass | 害羞尴尬，声音发颤 | 尴尬、脸红、紧张 |
| shock | 惊讶震惊，声音提高 | 震惊、天哪、该死 |
| annoy | 烦躁不满，带抱怨 | 烦躁、可恶、讨厌 |
| vulnerable | 脆弱感性，声音柔软 | 眼泪、想念、哭 |
| cheerful | 开心愉快，声音明亮 | 开心、笑、愉快 |
| awkward | 尴尬不自然，带犹豫 | (custom) |

You can add custom styles via `analyzer.emotion.add_custom_style()`.

## 🔧 API Configuration

### MiMo TTS API

This project uses the [MiMo](https://platform.mimofire.com/) TTS API with these endpoints:

- **Basic TTS**: `mimo-v2-tts` model → `/v1/chat/completions`
- **VoiceDesign**: `mimo-v2.5-tts-voicedesign` model → `/v1/chat/completions`

**VoiceDesign API format** (non-standard OpenAI):

```python
payload = {
    "model": "mimo-v2.5-tts-voicedesign",
    "messages": [
        {"role": "user", "content": "<director_note> + <style_instruction>"},
        {"role": "assistant", "content": "<style>description</style>\n<text>"}
    ],
    "audio": {"format": "mp3"}
}
```

**Important**: The VoiceDesign API uses a two-message structure (user + assistant), not the standard single-message format.

## ⚠️ Known Issues

- **Content Filter**: The API may filter "high risk" content (intimate/violent scenes). Retrying sometimes bypasses this. Failed chunks are skipped.
- **SSL in corporate environments**: Set `verify_ssl=False` (default) if behind a proxy. The client disables SSL verification and proxy detection by default.
- **MP3 concatenation**: Uses simple binary append. For production, consider `ffmpeg` or `pydub` for frame-level concatenation.

## 🤝 Contributing

Contributions welcome! Areas of interest:

- Support for more TTS APIs (OpenAI, Azure, etc.)
- Better audio concatenation (ffmpeg/pydub integration)
- GUI or web interface
- SSML support
- Batch processing optimizations

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
