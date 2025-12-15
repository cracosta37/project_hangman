from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Union


class WordRepository:
    """
    Responsible for loading, validating and serving words/phrases to the controller.

    Responsibilities:
    - Load JSON data safely.
    - Validate and sanitize entries.
    - Provide words by difficulty key.
    - Maintain a session-level "used" set (normalized) to implement no-repeat.
    """

    # Allowed difficulty keys expected by the controller
    EXPECTED_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path).resolve()
        self.words: Dict[str, List[str]] = {k: [] for k in self.EXPECTED_DIFFICULTIES}
        # used_words stores normalized forms (canonical) for dedup & no-repeat
        self.used_words: Set[str] = set()

        self._load()

    # -------------------------
    # Loading and validation
    # -------------------------
    def _load(self) -> None:
        """
        Load and validate the JSON file.
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

        # Normalize root forms
        if isinstance(data, dict):
            # iterate over provided keys; place validated words into matching uppercase buckets
            for raw_key, values in data.items():
                if not isinstance(raw_key, str):
                    continue
                key = raw_key.strip().upper()
                # only accept expected difficulties; ignore other keys
                if key not in self.EXPECTED_DIFFICULTIES:
                    continue
                if not isinstance(values, list):
                    continue
                for item in values:
                    validated = self._validate_and_clean_entry(item)
                    if validated is not None:
                        # Check for the number of alphabetic letters
                        min_letters = 2
                        if sum(1 for ch in validated if ch.isalpha()) >= min_letters:
                            self.words[key].append(validated)
        elif isinstance(data, list):
            # Treat an unkeyed list as MEDIUM default
            for item in data:
                validated = self._validate_and_clean_entry(item)
                if validated is not None:
                    # Check for the number of alphabetic letters
                    min_letters = 2
                    if sum(1 for ch in validated if ch.isalpha()) >= min_letters:
                        self.words["MEDIUM"].append(validated)
        else:
            raise TypeError("Word bank root must be either an object (dict) or an array (list).")

        # After load: ensure we do not have empty buckets for the expected difficulties.
        # It's acceptable for some buckets to be empty, but it's often better to warn or raise
        # depending on product policy. Here we keep it permissive (no exception), but controller
        # must handle missing words at selection time.
        #
        # Optionally: remove duplicates within each bucket (case/diacritic-insensitive)
        for key in list(self.words.keys()):
            self.words[key] = self._unique_preserve_order(self.words[key])

    def _validate_and_clean_entry(self, raw: object) -> Union[str, None]:
        """
        Validate and return a cleaned string or None if invalid.

        Rules:
        - Must be a str.
        - Trim leading/trailing whitespace.
        - Must contain only letters, spaces or hyphens.
        - Must contain at least two alphabetic letters.
        - Must be shorter than a reasonable cap (e.g., 120 chars).
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
                continue
            if ch == " " or ch == "-":
                continue
            # any other character (punctuation, digits, symbols) -> invalid
            return None

        if alpha_count < 2:
            # must contain at least two letters
            return None

        # At this stage the entry is syntactically acceptable.
        # Return the original (trimmed) text (controller/model will perform additional normalization).
        return text

    # -------------------------
    # Utility helpers
    # -------------------------
    @staticmethod
    def _normalize_for_internal(text: str) -> str:
        """
        Normalize text to a canonical internal form for deduplication and used-word tracking.

        Steps:
        - NFD unicode decomposition
        - Remove combining marks (diacritics)
        - Uppercase
        - Collapse multiple spaces into single (preserve single spaces)
        - Strip leading/trailing spaces
        """
        if text is None:
            return ""

        # NFD decomposition
        decomposed = unicodedata.normalize("NFD", text)
        # remove combining marks
        filtered = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
        # collapse spaces and uppercase
        collapsed = " ".join(filtered.split())
        return collapsed.upper()

    @staticmethod
    def _unique_preserve_order(items: List[str]) -> List[str]:
        seen: Set[str] = set()
        out: List[str] = []
        for it in items:
            key = WordRepository._normalize_for_internal(it)
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

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

        bucket = list(self.words.get(key, []))
        if not bucket:
            raise ValueError(f"No words available for difficulty: {key}")

        # Filter out already used (internal normalized forms)
        available = [
            w for w in bucket
            if self._normalize_for_internal(w) not in self.used_words
        ]

        if not available:
            # No unused words remaining in this bucket. Raise a descriptive error.
            raise ValueError(f"No unused words remaining for difficulty: {key}")

        selection = random.choice(available)
        # Mark selected as used (store normalized form)
        self.used_words.add(self._normalize_for_internal(selection))
        return selection

    def reset_session(self) -> None:
        """Clear session-level used-word cache."""
        self.used_words.clear()