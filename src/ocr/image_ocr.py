#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — Image OCR Module

OCR image-only pages (e.g., scanned manga/novel pages) using
multimodal AI APIs like MiMo V2.5.

Usage:
    python -m src.ocr.image_ocr --img-dir /path/to/images --output-dir /path/to/output
"""

import os
import re
import sys
import json
import base64
import time
import argparse
import ssl
import urllib.request
from pathlib import Path

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_ssl_context(verify: bool = False) -> ssl.SSLContext:
    """Create SSL context with optional verification."""
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def compress_image(img_path: str, max_width: int = 1024, quality: int = 75) -> str:
    """Compress and resize image, return base64-encoded JPEG.

    Requires Pillow. Raises ImportError if not installed.
    """
    if not HAS_PIL:
        raise ImportError("Pillow is required for image compression: pip install Pillow")

    img = Image.open(img_path)
    if img.width > max_width:
        ratio = max_width / img.width
        new_h = int(img.height * ratio)
        img = img.resize((max_width, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def ocr_image(
    img_path: str,
    api_url: str,
    api_key: str,
    ssl_context: ssl.SSLContext | None = None,
    model: str = "mimo-v2.5",
    prompt: str = "请完整识别这张图片中的所有文字内容，按照原文格式输出，不要遗漏任何文字。",
    max_tokens: int = 4000,
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> str | None:
    """OCR a single image using multimodal API.

    Args:
        img_path: Path to the image file.
        api_url: API endpoint URL.
        api_key: API authentication key.
        ssl_context: Custom SSL context (created if None).
        model: Model name for the API.
        prompt: Instruction prompt for the model.
        max_tokens: Maximum tokens in response.
        max_retries: Number of retry attempts.
        retry_delay: Base delay between retries (seconds).

    Returns:
        Extracted text string, or None if all retries failed.
    """
    if ssl_context is None:
        ssl_context = get_ssl_context()

    b64 = compress_image(img_path)

    for attempt in range(max_retries):
        payload = json.dumps({
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            "max_tokens": max_tokens
        }).encode("utf-8")

        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )

        try:
            with urllib.request.urlopen(req, context=ssl_context, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result["choices"][0]["message"]["content"]
                if text and len(text.strip()) > 10:
                    return text
                print(f"  Attempt {attempt+1}: Empty/short result, retrying...")
                time.sleep(2)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            print(f"  Attempt {attempt+1}: HTTP {e.code} - {body}")
            if e.code == 429:  # Rate limit
                print("  Rate limited, waiting 10s...")
                time.sleep(10)
            else:
                time.sleep(retry_delay)
        except Exception as e:
            print(f"  Attempt {attempt+1}: {type(e).__name__}: {e}")
            time.sleep(retry_delay)

    return None


def batch_ocr(
    img_dir: str,
    output_path: str,
    api_url: str,
    api_key: str,
    pattern: str = "*.jpg",
    **kwargs,
) -> dict:
    """OCR all images in a directory and save combined text.

    Args:
        img_dir: Directory containing image files.
        output_path: Path for the output text file.
        api_url: API endpoint URL.
        api_key: API authentication key.
        pattern: Glob pattern for image files.
        **kwargs: Additional arguments passed to ocr_image().

    Returns:
        Dict with stats: total, success, failed, total_chars.
    """
    img_dir = Path(img_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img_files = sorted(img_dir.glob(pattern), key=lambda p: p.name)
    print(f"Found {len(img_files)} images")

    ssl_context = get_ssl_context()
    all_text = []
    success_count = 0

    for i, img_path in enumerate(img_files):
        print(f"\n[{i+1}/{len(img_files)}] Processing: {img_path.name}")
        text = ocr_image(str(img_path), api_url, api_key, ssl_context=ssl_context, **kwargs)
        if text:
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Remove markdown bold
            text = text.strip()
            print(f"  Got {len(text)} chars")
            all_text.append(f"--- {img_path.name} ---\n{text}")
            success_count += 1
        else:
            print("  FAILED to OCR this image!")
            all_text.append(f"--- {img_path.name} ---\n[OCR failed]")

    combined = "\n\n".join(all_text)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(combined)

    failed_count = len(img_files) - success_count
    stats = {
        "total": len(img_files),
        "success": success_count,
        "failed": failed_count,
        "total_chars": len(combined),
    }
    print(f"\n=== DONE ===")
    print(f"Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}")
    print(f"Output: {output_path}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Image OCR for AI Audiobook Maker")
    parser.add_argument("--img-dir", required=True, help="Directory containing images")
    parser.add_argument("--output", required=True, help="Output text file path")
    parser.add_argument("--api-url", required=True, help="API endpoint URL")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--pattern", default="*.jpg", help="Image file glob pattern")
    args = parser.parse_args()

    batch_ocr(args.img_dir, args.output, args.api_url, args.api_key, pattern=args.pattern)


if __name__ == "__main__":
    main()
