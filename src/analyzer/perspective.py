#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — Perspective Detection Module

Determine which character is narrating each chapter,
based on a configurable mapping file.
"""

import json
from pathlib import Path


def load_perspective_map(config_path: str) -> dict[str, str]:
    """Load chapter-to-perspective mapping from JSON config.

    Args:
        config_path: Path to perspective_map.json.

    Returns:
        Dict mapping chapter keys to perspective identifiers.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("perspective_map", {})


def get_perspective(chapter_key: str, perspective_map: dict[str, str], default: str = "narrator") -> str:
    """Get the narrative perspective for a chapter.

    Args:
        chapter_key: Chapter identifier (e.g., "01", "SP01_1").
        perspective_map: Mapping from chapter keys to perspective IDs.
        default: Default perspective if chapter not found.

    Returns:
        Perspective identifier string.
    """
    return perspective_map.get(chapter_key, default)


def detect_perspective_from_text(text: str, character_names: list[str] | None = None) -> str | None:
    """Attempt to detect narrative perspective from text content.

    Heuristic: if a character name appears as the object of action
    (others talk to/about them), they are likely NOT the narrator.
    The narrator refers to others by name and calls themselves "我" (I).

    This is a best-effort detection. For reliable results, use
    the explicit perspective_map config.

    Args:
        text: Chapter text content.
        character_names: List of character names to check.

    Returns:
        Detected character name, or None if unclear.
    """
    if not character_names:
        return None

    # Simple heuristic: count how often each character is mentioned
    # as being addressed/spoken to (likely NOT the narrator)
    scores = {}
    for name in character_names:
        # Pattern: someone calls this character by name
        addressed_patterns = [
            f"「{name}",  # Direct speech addressing
            f"{name}，",  # Vocative
            f"{name}！",  # Exclamatory vocative
            f"Khun{name}",  # Thai honorific
        ]
        address_count = sum(text.count(p) for p in addressed_patterns)
        scores[name] = address_count

    # The character with the FEWEST addresses is most likely the narrator
    # (people don't address themselves by name in first-person narration)
    if scores:
        narrator = min(scores, key=scores.get)
        if scores[narrator] < max(scores.values()) * 0.5:
            return narrator

    return None
