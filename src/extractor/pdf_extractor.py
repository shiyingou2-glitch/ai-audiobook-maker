#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-audiobook-maker — PDF Text Extractor

Extract text from PDF files, clean up formatting noise,
and save as clean TXT files for TTS processing.

Usage:
    python -m src.extractor.pdf_extractor --pdf-dir /path/to/pdfs --output-dir /path/to/output
"""

import os
import re
import argparse
import pdfplumber


def clean_text(text: str) -> str:
    """Deep-clean PDF-extracted text with 8-step pipeline.

    Steps:
        1. Remove stray single letters on standalone lines
        2. Remove inline single letters between Chinese chars (PDF artifact)
        3. Remove trailing single letters after Chinese punctuation
        4. Remove leading single letters before Chinese chars
        5. Remove superscript digits
        6. Collapse excessive blank lines
        7. Merge all lines, re-split by sentence-ending punctuation
        8. Clean residual whitespace
    """
    # 1. Standalone single letters (PDF column artifacts)
    text = re.sub(r'\n[a-zA-Z]\n', '\n', text)
    text = re.sub(r'^[a-zA-Z]$', '', text, flags=re.MULTILINE)

    # 2. Inline single letters between Chinese chars (run twice for chains)
    text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])([\u4e00-\u9fff])', r'\1\3', text)
    text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])([\u4e00-\u9fff])', r'\1\3', text)

    # 3. Trailing single letters
    text = re.sub(
        r'([\u4e00-\u9fff，。！？、；：…])\s*[a-zA-Z]\s*$',
        r'\1', text, flags=re.MULTILINE
    )

    # 4. Leading single letters
    text = re.sub(r'^\s*[a-zA-Z]\s+(?=[\u4e00-\u9fff])', '', text, flags=re.MULTILINE)

    # 5. Superscript digits
    text = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', text)

    # 6. Collapse blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 7. Merge lines → split by sentence-ending punctuation
    lines = text.split('\n')
    joined = ''.join(line.strip() for line in lines if line.strip())
    joined = re.sub(r' +', '', joined)
    joined = re.sub(r'(Chapter\s*\d+\s*[-–—]\s*)', r'\n\n\1', joined)
    joined = re.sub(r'\n{3,}', '\n\n', joined)

    paragraphs = re.split(r'(?<=[。！？])', joined)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    text = '\n\n'.join(paragraphs)

    # 8. Final whitespace cleanup
    text = re.sub(r' +', ' ', text)
    return text.strip()


def extract_pdf(pdf_path: str) -> str:
    """Extract raw text from a single PDF file."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
    return '\n'.join(pages)


def process_chapters(pdf_dir: str, output_dir: str, chapters: list[tuple[str, str]] | None = None):
    """Extract and clean all chapters.

    Args:
        pdf_dir: Directory containing PDF files.
        output_dir: Directory to write cleaned TXT files.
        chapters: Optional list of (pdf_filename, output_name) tuples.
                  If None, processes all .pdf files in pdf_dir sorted by name.
    """
    os.makedirs(output_dir, exist_ok=True)

    if chapters is None:
        pdf_files = sorted(f for f in os.listdir(pdf_dir) if f.endswith('.pdf'))
        chapters = [(f, os.path.splitext(f)[0]) for f in pdf_files]

    results = []
    success = 0
    total_chars = 0

    for pdf_file, name in chapters:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        if not os.path.exists(pdf_path):
            results.append(f"SKIP {name}: file not found")
            continue

        try:
            raw = extract_pdf(pdf_path)
            cleaned = clean_text(raw)

            if not cleaned or len(cleaned.strip()) < 5:
                results.append(f"SKIP {name}: empty content")
                continue

            out_path = os.path.join(output_dir, f"{name}.txt")
            chapter_title = os.path.splitext(pdf_file)[0]
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(f"{chapter_title}\n{'='*40}\n\n{cleaned}")

            char_count = len(cleaned)
            total_chars += char_count
            success += 1
            results.append(f"OK {name}: {char_count} chars")

        except Exception as e:
            results.append(f"FAIL {name}: {e}")

    results.append(f"\nTOTAL: {success} chapters, {total_chars} chars")
    return results


def main():
    parser = argparse.ArgumentParser(description="PDF Text Extractor for AI Audiobook Maker")
    parser.add_argument("--pdf-dir", required=True, help="Directory containing PDF files")
    parser.add_argument("--output-dir", required=True, help="Directory for cleaned TXT output")
    args = parser.parse_args()

    results = process_chapters(args.pdf_dir, args.output_dir)
    for line in results:
        print(line)


if __name__ == "__main__":
    main()
