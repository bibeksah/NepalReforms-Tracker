"""
Data cleaning utilities for Nepali PDF budget documents.

Handles:
  - CID font encoding artifacts from PDF extraction
  - Budget string normalization to integers
  - Noise filtering (page numbers, metadata rows, zero-budget lines)
"""

import re

# Compile regex patterns globally to avoid recompilation overhead inside loops
_CID_PATTERN = re.compile(r'\(cid:\d+\)')
_WHITESPACE_PATTERN = re.compile(r'\s+')
_NON_DIGIT_PATTERN = re.compile(r'[^\d.]')


def clean_cid_text(text: str) -> str:
    """Remove CID encoding markers and normalize whitespace."""
    if not text:
        return ""
    text = _CID_PATTERN.sub('', text)
    text = _WHITESPACE_PATTERN.sub(' ', text).strip()
    return text


def normalize_budget(budget_str) -> int:
    """Parse a budget string (possibly with commas/spaces) to an integer."""
    if not budget_str:
        return 0
    clean_val = _NON_DIGIT_PATTERN.sub('', str(budget_str))
    try:
        return int(float(clean_val))
    except ValueError:
        return 0


def is_valid_project(proj: dict) -> bool:
    """
    Returns False if the project appears to be noise.

    Filters:
      - Numeric-only titles (page numbers)
      - Very short titles (<5 chars)
      - Zero-budget lines
    """
    title = proj.get('title_ne', '')
    if title.isdigit():
        return False
    if len(title) < 5:
        return False
    if proj.get('budget', 0) == 0:
        return False
    return True
