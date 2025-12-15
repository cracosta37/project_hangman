from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Union


class WordRepository:
    """
    Loads, validates, normalizes, and serves words/phrases.

    Guarantees:
    - All stored words satisfy Game.set_word() constraints
    - All internal storage is normalized
    - No-repeat enforced at session level
    """

    # Allowed difficulty keys expected by the controller
    EXPECTED_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path).resolve()
        # Normalized words by difficulty
        self.normalized_words_by_diff: Dict[str, Set[str]] = {diff: set() for diff in self.EXPECTED_DIFFICULTIES}
        # used_words stores normalized forms (canonical) for dedup & no-repeat
        self.used_words: Set[str] = set()

        self._load()

    # -------------------------
    # Loading and validation
    # -------------------------
    def _load(self) -> None:
        """
        Load, validate, and normalizes the JSON file.
        Accept two formats:
            1) dict with keys (easy/medium/hard) mapping to lists of strings
            2) list of strings -> treat as MEDIUM default bucket
        All invalid entries are skipped (silently). Optionally, log rejected counts.
        """

        if not self.file_path.exists():
            raise FileNotFoundError(f"Word bank file not found: {self.file_path}")

        try:
            with self.file_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Word bank file is not valid JSON: {self.file_path}") from exc

        if isinstance(data, dict):
            self._load_from_dict(data)
        elif isinstance(data, list):
            self._load_from_list(data)
        else:
            raise TypeError("Word bank root must be either an object (dict) or an array (list).")

    def _load_from_dict(self, data: dict) -> None:
        for raw_key, values in data.items():
            if not isinstance(raw_key, str):
                continue

            key = raw_key.strip().upper()
            if key not in self.EXPECTED_DIFFICULTIES:
                continue

            if not isinstance(values, list):
                continue

            for item in values:
                normalized = self._validate_normalize(item)
                if normalized:
                    self.normalized_words_by_diff[key].add(normalized)

    def _load_from_list(self, data: list) -> None:
        for item in data:
            normalized = self._validate_normalize(item)
            if normalized:
                self.normalized_words_by_diff["MEDIUM"].add(normalized)

    def _validate_normalize(self, raw: object) -> str | None:
        """
        Validate, clean, and normalize a word or phrase.
        Returns normalized string or None if invalid.
        """

        if not isinstance(raw, str):
            return None

        text = raw.strip()
        if not text:
            return None

        # Length cap (prevents abusive entries)
        if len(text) > 120:
            return None

        # Validate allowed characters (letters incl. international, spaces, hyphens)
        # We'll check each character category using unicode classification.
        alpha_count = 0
        for ch in text:
            if ch.isalpha():
                alpha_count += 1
            elif ch in {" ", "-"}:
                continue
            # any other character (punctuation, digits, symbols) -> invalid
            else:
                return None

        if alpha_count < 2:
            # must contain at least two letters
            return None

        return self._normalize_for_internal(text)

    # -------------------------
    # Normalization
    # -------------------------
    @staticmethod
    def _normalize_for_internal(text: str) -> str:
        """
        Normalize text to a canonical internal form.

        Steps:
        - NFD unicode decomposition
        - Remove combining marks (diacritics)
        - Uppercase
        - Collapse multiple spaces into single (preserve single spaces)
        - Strip leading/trailing spaces
        """
        
        # NFD decomposition
        decomposed = unicodedata.normalize("NFD", text)
        # remove combining marks
        filtered = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
        # collapse spaces and uppercase
        collapsed = " ".join(filtered.split())
        return collapsed.upper()

    # -------------------------
    # Public API
    # -------------------------
    def get_by_difficulty(self, difficulty: str) -> str:
        """
        Return a random unused word for the given difficulty key ("EASY","MEDIUM","HARD").
        Raises ValueError if difficulty is invalid or no words are available.
        """

        if not isinstance(difficulty, str):
            raise TypeError("Difficulty must be a string.")

        key = difficulty.strip().upper()
        if key not in self.EXPECTED_DIFFICULTIES:
            raise ValueError(f"Invalid difficulty: {difficulty!r}")

        available = self.normalized_words_by_diff[key] - self.used_words

        if not available:
            # No unused words remaining in this bucket. Raise a descriptive error.
            raise ValueError(f"No unused words remaining for difficulty: {key}")

        selection = random.choice(tuple(sorted(available)))
        # Mark selected as used (store normalized form)
        self.used_words.add(selection)
        return selection

    def reset_session(self) -> None:
        """Clear session-level used-word cache."""
        self.used_words.clear()