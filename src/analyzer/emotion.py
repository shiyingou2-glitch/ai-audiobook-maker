#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — Emotion/Style Detection Module

Detect the emotional tone of text chunks for style-aware TTS generation.
Uses keyword matching with priority ordering.
"""

# Style descriptions used in <style> tags and director notes
STYLE_MAP = {
    "narrate":     "平静叙述，语速中等，像在讲一个故事",
    "introspect":  "内心独白，语速稍慢，带思考感，低声呢喃",
    "embarrass":   "害羞尴尬，语速不稳，声音微微发颤",
    "shock":       "惊讶震惊，语速较快，声音提高",
    "annoy":       "烦躁不满，语速中等偏快，带抱怨语气",
    "vulnerable":  "脆弱感性，语速较慢，声音柔软",
    "cheerful":    "开心愉快，语速轻快，声音明亮",
    "awkward":     "尴尬不自然，语速忽快忽慢，带犹豫感",
}

# Keyword lists for each style (Chinese)
_STYLE_KEYWORDS = {
    "embarrass":   ["尴尬", "羞耻", "脸红", "紧张", "手心出汗", "不敢看", "移开视线", "尴尬地"],
    "shock":       ["惊讶", "震惊", "不敢相信", "天哪", "怎么会", "该死", "差点"],
    "annoy":       ["烦躁", "生气", "可恶", "讨厌", "气死", "抱怨", "狐狸精", "恼火"],
    "vulnerable":  ["脆弱", "眼泪", "心乱", "失眠", "想念", "无法控制", "烦恼", "哭", "孤独"],
    "introspect":  ["我想", "我在想", "我的思绪", "为什么", "怎么", "我以为", "从未", "究竟", "难道", "也许", "不知道为什么"],
    "cheerful":    ["开心", "高兴", "笑", "有趣", "愉快", "咯咯"],
}

# Detection priority order (first match wins)
_PRIORITY = ["embarrass", "shock", "annoy", "vulnerable", "introspect", "cheerful"]


def detect_style(text: str) -> str:
    """Detect the emotional style of a text chunk.

    Uses keyword matching with priority ordering. Falls back to "narrate"
    if no keywords are found.

    Args:
        text: Input text chunk.

    Returns:
        Style name string (key into STYLE_MAP).
    """
    text_lower = text.lower()
    for style in _PRIORITY:
        keywords = _STYLE_KEYWORDS.get(style, [])
        if any(kw in text_lower for kw in keywords):
            return style
    return "narrate"


def add_custom_style(name: str, description: str, keywords: list[str], priority: int | None = None):
    """Add a custom emotion style.

    Args:
        name: Style identifier.
        description: Style description for TTS generation.
        keywords: List of trigger keywords.
        priority: Position in detection priority (None = append at end).
    """
    STYLE_MAP[name] = description
    _STYLE_KEYWORDS[name] = keywords
    if priority is not None and 0 <= priority <= len(_PRIORITY):
        _PRIORITY.insert(priority, name)
    else:
        _PRIORITY.append(name)
