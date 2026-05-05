#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — Shared TTS Utilities

Base API client, text chunking, retry logic, and MP3 concatenation
shared by all TTS modules.
"""

import json
import ssl
import time
import base64
import urllib.request
from typing import Callable

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TTSClient:
    """Base TTS API client with session reuse, retry, and SSL handling."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        verify_ssl: bool = False,
        max_retries: int = 5,
        retry_delay: float = 3.0,
        timeout: int = 120,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        # requests-based session (for mimo_tts basic mode)
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.proxies = {}
        self.session.verify = verify_ssl
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

        # urllib-based SSL context (for voicedesign mode)
        self.ssl_context = ssl.create_default_context()
        if not verify_ssl:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

    @property
    def api_url(self) -> str:
        """Full API endpoint URL."""
        base = self.base_url
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def call_api_urllib(self, payload: dict) -> dict:
        """Call API using urllib (no requests dependency for this path).

        Returns parsed JSON response dict.
        Raises on exhausted retries.
        """
        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.api_url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        last_error = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, context=self.ssl_context, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="ignore")[:200]
                except Exception:
                    pass
                last_error = f"HTTP {e.code}: {body}"
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        raise RuntimeError(f"API call failed after {self.max_retries} retries: {last_error}")

    def call_api_requests(self, payload: dict) -> dict:
        """Call API using requests session.

        Returns parsed JSON response dict.
        Raises on exhausted retries.
        """
        url = self.api_url
        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)[:80]}"
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        raise RuntimeError(f"API call failed after {self.max_retries} retries: {last_error}")


def chunk_text_by_punctuation(text: str, max_chars: int = 1000) -> list[str]:
    """Split text into chunks at sentence boundaries.

    Strategy: find the last sentence-ending punctuation within max_chars,
    split there. Falls back to hard split if no punctuation found.

    Args:
        text: Input text to chunk.
        max_chars: Maximum characters per chunk.

    Returns:
        List of text chunks.
    """
    chunks = []
    while len(text) > max_chars:
        for punct in ["。", "！", "？", "……", "\n\n", "\n", "，"]:
            idx = text.rfind(punct, 0, max_chars)
            if idx > max_chars * 0.3:
                idx += len(punct)
                chunks.append(text[:idx])
                text = text[idx:].strip()
                break
        else:
            chunks.append(text[:max_chars])
            text = text[max_chars:]
    if text.strip():
        chunks.append(text.strip())
    return chunks


def chunk_text_by_sentence(text: str, max_len: int = 1000) -> list[str]:
    """Split text into chunks by sentence boundaries (Chinese + English).

    Args:
        text: Input text to chunk.
        max_len: Maximum characters per chunk.

    Returns:
        List of text chunks.
    """
    import re
    sentences = re.split(r'(?<=[。！？\.\!\?])\s*', text)
    chunks = []
    current = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(current) + len(sent) < max_len:
            current += sent + " "
        else:
            if current:
                chunks.append(current.strip())
            current = sent + " "
    if current:
        chunks.append(current.strip())
    return chunks


def concatenate_mp3(mp3_data_list: list[bytes], output_path: str) -> int:
    """Concatenate MP3 audio chunks into a single file.

    Simple binary append — works for basic playback without ffmpeg.
    For production use, consider ffmpeg or pydub for proper concatenation.

    Args:
        mp3_data_list: List of MP3 bytes objects.
        output_path: Output file path.

    Returns:
        Total bytes written.
    """
    total = 0
    with open(output_path, "wb") as f:
        for data in mp3_data_list:
            f.write(data)
            total += len(data)
    return total


def load_api_config() -> tuple[str, str]:
    """Load API key and base URL from environment variables.

    Env vars:
        MIMO_API_KEY: API authentication key
        MIMO_BASE_URL: API base URL

    Returns:
        Tuple of (api_key, base_url).

    Raises:
        EnvironmentError: If required env vars are not set.
    """
    import os
    api_key = os.environ.get("MIMO_API_KEY", "")
    base_url = os.environ.get("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")
    if not api_key:
        raise EnvironmentError(
            "MIMO_API_KEY environment variable is required. "
            "Set it with: export MIMO_API_KEY=your_key_here"
        )
    return api_key, base_url
