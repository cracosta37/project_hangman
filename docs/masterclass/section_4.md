# 4. Data Handling & Input Processing

## Topic 4.1 — Unicode Normalization & Accent Removal

This is one of the most "invisible but critical" pieces of the project. It's implemented in two places and covered by a dedicated block of tests. Let's build it up from the problem it solves.

---

### 1. The problem it solves

In hangman, a guess only counts if the typed character **equals** a character in the secret word. Look at the matching logic in `hangman/model/game.py:155`:

```python
positions = [i for i, l in enumerate(self.word) if l == letter]
```

That `==` is a strict character-by-character comparison. Now consider a word like `"café"`:

- The `é` in `"café"` is **not** the letter `e`. It is a *different* Unicode code point.
- If the word bank stores `CAFE` (accent stripped) but a player types `É`, or the word bank stores `CAFÉ` but the player types `E`, the strict comparison silently fails and the player loses a life for "missing" a letter that *visually looks the same*.

The project's solution: **strip all accents from every word at load time, and normalize every player guess the same way.** Once both sides of the `==` comparison are in the same "canonical form", accent differences can never break matching. That is exactly what the study guide means by *"guessing 'a' matches 'á'."*

---

### 2. Background: how accented characters are stored

The key insight for beginners: **a single accented letter can be one character or two, depending on how it was typed or encoded.**

| Input | Code points | Description |
|---|---|---|
| `é` (precomposed) | `U+00E9` (1 code point) | A single "Latin small letter e with acute" glyph |
| `e\u0301` (decomposed) | `U+0065` + `U+0301` (2 code points) | Base letter `e` + a *combining acute accent* that renders on top of it |

Both display identically on screen, but `"é" == "e\u0301"` is `False` in Python. The same visual letter has **two different spellings in Unicode**.

#### Normalization forms

`unicodedata.normalize()` converts a string between these equivalent representations:

- **NFD** (Normalisation form, Decomposed): breaks every precomposed character into *base + combining marks*. `é` → `e` + `U+0301`.
- **NFC** (Composed): does the reverse — merges base + marks back into single precomposed characters where a precomposed form exists.
- (NFKD/NFKC are the "compatibility" variants that also expand things like ligatures `ﬁ` → `fi` or `①` → `1`; not needed here.)

#### Character categories

After decomposition, the accent survives as a separate *combining mark* code point. `unicodedata.category(ch)` classifies every code point; diacritics like `U+0301` (combining acute accent) fall in category **`Mn`** — *Mark, non-spacing*. That gives us a clean, data-driven way to find and delete *all* accents in one pass, no matter which script they come from (Spanish `ñ`, French `ç`, German `ü`…):

```python
import unicodedata
unicodedata.category("\u0301")   # 'Mn'
unicodedata.category("e")        # 'Ll'  (letter, lowercase)
unicodedata.category(" ")        # 'Zs'  (space)
```

---

### 3. The implementation in this codebase

#### The core method: `WordRepository._normalize_for_internal`

`hangman/services/word_repository.py:122-141`:

```python
@staticmethod
def _normalize_for_internal(text: str) -> str:
    # NFD decomposition
    decomposed = unicodedata.normalize("NFD", text)
    # remove combining marks
    filtered = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    # collapse spaces and uppercase
    collapsed = " ".join(filtered.split())
    return collapsed.upper()
```

Four steps, in a deliberate order:

1. **`unicodedata.normalize("NFD", text)`** — explode every precomposed accented character into base + mark.
2. **Filter out `Mn` characters** — the generator expression `"".join(ch for ch in decomposed if ...)` keeps everything *except* combining marks, i.e. deletes every accent.
3. **`" ".join(filtered.split())`** — a classic Python idiom: `split()` with no arguments splits on *any* whitespace (spaces, tabs, newlines) and drops empty pieces; joining with `" "` collapses `hello   world` / `hello\tworld` into a single clean space.
4. **`.upper()`** — case-insensitive matching.

> Note it's a `@staticmethod` with no `self`: it's a pure string function, which makes it trivially unit-testable (the tests call it directly as `WordRepository._normalize_for_internal(...)`).

#### Step-by-step trace: `"café"`

```python
text       = "café"                    # c, a, f, é(U+00E9)          → 4 code points
decomposed = unicodedata.normalize("NFD", text)
#          = "cafe\u0301"              # c, a, f, e, U+0301          → 5 code points
filtered   = "cafe"                    # U+0301 is 'Mn' → removed
collapsed  = "cafe"                    # no whitespace to collapse
result     = "CAFE"
```

#### A second, subtler trace: already-decomposed input

The test suite includes `("e\u0301", "E")` (`tests/unit/test_word_repository.py:203`). This simulates a word bank file where `é` was *already stored decomposed* (base `e` + combining accent). The same two lines handle it perfectly — NFD is idempotent on already-decomposed text, and the `Mn` filter still removes the mark. **This is exactly why we normalize instead of writing an ad-hoc replace table like `text.replace("á", "a")`**: an ad-hoc table would only work for one representation and one language.

And `("\u0301\u0301", "")` (line 204) shows the edge case: a string made *only* of combining marks normalizes to the empty string.

---

### 4. Where it plugs into the pipeline

Normalization is the **last step of validation** for each word, at `word_repository.py:117`:

```python
def _validate_normalize(self, raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if len(text) > 120:
        return None
    # Validate allowed characters (letters incl. international, spaces, hyphens)
    alpha_count = 0
    for ch in text:
        if ch.isalpha():
            alpha_count += 1
        elif ch in {" ", "-"}:
            continue
        else:
            return None
    if alpha_count < 2:
        return None
    return self._normalize_for_internal(text)      # ← accents die here, last
```

Notice the ordering: validation runs **before** accent removal, and it uses `ch.isalpha()`, which returns `True` for *any* Unicode letter — `é`, `ñ`, `ç` all pass. So international words are accepted, then reduced to their accent-free canonical form. (Also note the 120-char cap is checked on the pre-normalization length — fine for this use case.)

The normalized result is what gets stored everywhere:

- **`normalized_words_by_diff`** (line 26) — a `Dict[str, Set[str]]` of *normalized* words per difficulty. Because it's a `set`, normalization gives you **free deduplication across accent and case variants**. This is locked in by the test at `test_word_repository.py:127-129`:

  ```python
  def test_load_from_list_deduplication(make_repo):
      repo = make_repo(["apple", "Apple", "ápple", " apple "])
      assert repo.normalized_words_by_diff["MEDIUM"] == {"APPLE"}
  ```

  Four different spellings of the same word → one entry.

- **`used_words`** (line 28, comment: *"stores normalized forms (canonical) for dedup & no-repeat"*) — the session no-repeat set also stores the canonical form, so `"café"` and `"cafe"` count as the *same* word and can't both be played in one session (`get_by_difficulty`, line 159-167).

---

### 5. The matching side: `Game._normalize`

The repository guarantees the *word* is accent-free. The *guess* is normalized too, in `hangman/model/game.py:34-40`:

```python
def _normalize(self, text: str) -> str:
    text = text or ""
    if not self.normalize_input:
        return text.upper()
    normalized = unicodedata.normalize("NFD", text)
    filtered = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return filtered.upper()
```

This is the same NFD + `Mn`-filter recipe (a small, deliberate duplication — the `Game` model must stay independent of the `WordRepository` service, per the project's separation of concerns). It's applied to every letter guess at `game.py:143`:

```python
letter = self._normalize(raw_letter.strip().upper())
```

so in `guess_letter` the comparison `l == letter` (line 155) always compares two canonical forms:

- word side: `CAFE` (stripped at load time by the repository)
- guess side: a player typing `é` → NFD → `e` + `Mn` → filter → `E` → matches the `E` in the word. ✓

There's a toggle: `Game.__init__` takes `normalize_input` (line 11). When `False`, the game keeps accented letters as first-class letters — the letter pool grows from 26 to include `ÑÁÉÍÓÚÜÇ` (lines 26-27), and `_normalize` only uppercases. This is the "international mode" variant; the default (`True`) is the accent-stripping mode described in the study guide.

---

### 6. Test coverage (what the suite proves)

From `tests/unit/test_word_repository.py`:

**Direct unit tests of the normalization function** (lines 196-207), parametrized:

```python
@pytest.mark.parametrize("input_text,expected", [
    ("hello", "HELLO"),                             # Simple case
    ("  hello   world  ", "HELLO WORLD"),           # Leading/trailing/multiple spaces
    ("café", "CAFE"),                               # Accents removed
    ("Árbol Niño", "ARBOL NINO"),                   # Multiple accented words
    ("hello\tworld\npython", "HELLO WORLD PYTHON"), # Tabs/newlines → spaces
    ("well-being", "WELL-BEING"),                   # Hyphens preserved
    ("e\u0301", "E"),                               # Already-decomposed accent
    ("\u0301\u0301", ""),                           # Combining characters only
])
def test_normalize_for_internal(input_text, expected):
    assert WordRepository._normalize_for_internal(input_text) == expected
```

**Idempotency** (lines 210-212) — normalizing an already-normalized string changes nothing. This property is what makes it safe to normalize data at load time *and* again on every guess:

```python
def test_normalize_for_internal_idempotent():
    text = "HELLO WORLD"
    assert WordRepository._normalize_for_internal(text) == text
```

**Behavioral tests through the public API** — `("café", "CAFE")` also appears in `test_validate_normalize_valid_cases` (line 170), proving the full load path produces `CAFE`.

---

### 7. Key takeaways for a beginner

1. **Accented letters are code points, not "letters with decorations."** `é` ≠ `e` + anything in a raw comparison; you must transform both sides into a common form.
2. **NFD + removing `Mn` is the standard, locale-independent accent-stripping recipe.** It works for any language's diacritics without a hardcoded replacement table.
3. **Normalize at the boundary** (when data enters the system) so the rest of the program can assume one canonical form — here: uppercase, accent-free, single-spaced.
4. **Normalization buys you deduplication for free** when storage is a `set` (`"Apple"`, `"ápple"`, `" apple "` → one `APPLE`).
5. **Order matters:** decompose *before* filtering (or precomposed accents are invisible to the `Mn` filter), and filter marks *before* uppercasing.
6. **Idempotency is a design goal** — the function can be applied repeatedly (load time + guess time) without drifting.

One honest caveat worth knowing: this recipe removes only `Mn` (non-spacing marks). Marks in other categories (`Mc` — spacing combining marks used by Devanagari/Thai — or `Me` — enclosing marks) would survive. For a Latin-alphabet word game, `Mn` is exactly right and the project documents its scope accordingly.

---
---

## Topic 4.2 — Sanitization and Validation

### 1. Concepts first

These are two related but distinct steps in handling data:

| Term | Question it answers | What it does |
|---|---|---|
| **Validation** | *"Is this data acceptable?"* | Checks rules (type, length, allowed characters, uniqueness) and **accepts or rejects** the value. |
| **Sanitization** | *"How do I make this data safe/canonical?"* | **Transforms** the value: trims whitespace, uppercases, strips accents, collapses spaces, deduplicates. |

In this project, both happen **before** any data is trusted by the game logic. The guiding principle: *never assume input is correct* — not from the JSON word bank, not from the moderator typing a secret word, not from a player guessing a letter.

The codebase has **two data sources** to protect against:

1. **The word bank file** (JSON on disk) → guarded by `WordRepository` (`hangman/services/word_repository.py`)
2. **Live user input** (moderator's secret word, player guesses, player names) → guarded by the `Game` model (`hangman/model/game.py`)

---

### 2. The central gate: `WordRepository._validate_normalize`

This single method (word_repository.py:84-117) is the heart of topic 4.2. Every entry read from the JSON file passes through it:

```python
def _validate_normalize(self, raw: object) -> str | None:
    if not isinstance(raw, str):
        return None                      # 1. Type check

    text = raw.strip()
    if not text:
        return None                      # 2. Empty / whitespace-only check

    if len(text) > 120:
        return None                      # 3. Length cap

    alpha_count = 0
    for ch in text:
        if ch.isalpha():
            alpha_count += 1
        elif ch in {" ", "-"}:
            continue
        else:
            return None                  # 4. Character whitelist

    if alpha_count < 2:
        return None                      # 5. Minimum letter count

    return self._normalize_for_internal(text)
```

Read it as a **filtering pipeline** — the value must survive every stage, and the method returns `None` ("reject") the moment any rule fails:

1. **Type check** — `123`, `None`, `[]`, `{}` in the JSON are rejected immediately. Note the parameter is typed `object`, not `str`: the code *expects* that garbage might arrive and handles it deliberately.
2. **Empty check** — `raw.strip()` removes surrounding spaces *and* then rejects `""` and `"   "`. This is sanitization (the strip) feeding validation (the emptiness test).
3. **Length cap (120)** — prevents abusive or corrupt entries that would wreck the display. The boundary is exact, and the tests pin it:
   ```python
   def test_validate_normalize_length_bounds(empty_repo):
       assert empty_repo._validate_normalize("a" * 121) is None
       assert empty_repo._validate_normalize("a" * 120) == "A" * 120
   ```
4. **Character whitelist** — the study guide's *"characters outside of allowed alphabets, hyphens, and spaces"*. Each character must be a letter (any language, since `isalpha()` is Unicode-aware) or one of `{" ", "-"}`. So `"dog!"` and `"hello123"` die here. A **whitelist** ("only allow these") is the safe approach — a blacklist ("ban these") would need updating every time a new weird character appears.
5. **Minimum letter count (2)** — `"a"`, `"-"`, and `" - "` pass the character check (hyphens and spaces are allowed!) but contain fewer than 2 letters, so they're rejected. This is why you can't count on the character loop alone.

Then, if it survived, **sanitization** happens in `_normalize_for_internal` (word_repository.py:122-141): NFD decomposition, removal of diacritics, space collapsing, uppercasing. So `"  café  "` becomes `"CAFE"` — a single canonical form.

The parametrized tests in `tests/unit/test_word_repository.py:166-184` show the full contract:

```python
@pytest.mark.parametrize("value,expected", [
    ("cat", "CAT"),                     # simple
    ("  dog  ", "DOG"),                 # trimmed
    ("hello   world", "HELLO WORLD"),   # spaces collapsed
    ("café", "CAFE"),                   # accent stripped
    ("well-being", "WELL-BEING"),       # hyphen preserved
])
def test_validate_normalize_valid_cases(...): ...

@pytest.mark.parametrize("value", [
    123, None, [], {},  # non-string types
    "", "   ",          # empty
    "dog!", "hello123", # bad characters
    "a", "-", " - ",    # too short
])
def test_validate_normalize_invalid_cases(...): ...
```

---

### 3. File-level validation: `_load` and friends

Before individual words are even looked at, the file itself is validated (word_repository.py:35-58) — and note how **different failure levels use different tools**:

```python
if not self.file_path.exists():
    raise FileNotFoundError(...)          # catastrophic: nothing can work

try:
    data = json.load(fh)
except json.JSONDecodeError as exc:
    raise ValueError(...) from exc        # catastrophic: file unreadable

if isinstance(data, dict):
    self._load_from_dict(data)
elif isinstance(data, list):
    self._load_from_list(data)
else:
    raise TypeError(...)                  # catastrophic: wrong structure
```

But *inside* the file, the strategy changes to **silent skipping**:

```python
def _load_from_dict(self, data: dict) -> None:
    for raw_key, values in data.items():
        if not isinstance(raw_key, str):
            continue                      # skip bad key
        key = raw_key.strip().upper()     # sanitize the key too!
        if key not in self.EXPECTED_DIFFICULTIES:
            continue                      # skip unknown difficulty
        if not isinstance(values, list):
            continue                      # skip bad bucket
        for item in values:
            self._add_if_valid(item, key) # skip bad words
```

This is an important design decision for beginners to notice: **a word bank with 1000 words and 3 typos should load with 997 words, not crash**. One bad entry shouldn't sink the whole file. (The docstring at word_repository.py:41 says exactly this: *"All invalid entries are skipped (silently)."*)

Also note `"easy"`/`"  Easy  "` keys are sanitized with `.strip().upper()` before being checked against `EXPECTED_DIFFICULTIES` — so the file format is forgiving about casing and spacing.

And `_add_if_valid` (word_repository.py:60-63) stores words in a **`set`**, which gives you deduplication for free:

```python
def test_load_from_list_deduplication(make_repo):
    repo = make_repo(["apple", "Apple", "ápple", " apple "])
    assert repo.normalized_words_by_diff["MEDIUM"] == {"APPLE"}
```

Four different raw strings collapse into one stored word. This is the study guide's *"preventing errors like word duplication"*: sanitization makes duplicates *detectable*, and the set makes them *impossible to store twice*.

---

### 4. The second wall: validation of live user input in `Game`

The repository's docstring promises: *"All stored words satisfy `Game.set_word()` constraints"* (word_repository.py:15). That's **defense in depth** — two independent layers enforce the same rules, so a bug in one layer can't let garbage reach the game state.

#### `Game.set_word` (game.py:46-66) — the moderator's secret word

```python
def set_word(self, raw_word: str) -> Dict[str, Any]:
    if raw_word is None:
        return {"ok": False, "error": "No word provided."}

    word = raw_word.strip()
    if len(word) == 0:
        return {"ok": False, "error": "The word cannot be empty."}

    letters_only = [ch for ch in word if ch.isalpha()]
    if len(letters_only) < 2:
        return {"ok": False, "error": "The word must contain at least two letters."}

    if not all(ch.isalpha() or ch in {" ", "-"} for ch in word):
        return {"ok": False, "error": "The word can only contain letters, spaces, or hyphens."}
    ...
```

Same rules as the repository (empty, ≥2 letters, letters/spaces/hyphens only) — but notice a key difference in **how failures are reported** (section 5 below).

#### `Game.guess_letter` (game.py:136-141) — a player's single-letter guess

```python
if not raw_letter or len(raw_letter.strip()) != 1 or not raw_letter.strip().isalpha():
    return {
        "ok": False,
        "repeat": True,
        "error": "Please provide a single alphabetic letter."
    }
```

Three checks chained with `or`: not empty, exactly one character after trimming, and that character is a letter. So a player who types `"ab"`, `"7"`, or `"!"` gets a friendly prompt to retry instead of a crash or a silently-wrong game state.

#### `Game.guess_word` (game.py:208-213) — the full-word guess

```python
if not raw_guess or not isinstance(raw_guess, str):
    return {"ok": False, "repeat": True, "error": "Invalid guess."}

guess = self._normalize(raw_guess.strip().upper())
if not all(ch.isalpha() or ch in {" ", "-"} for ch in guess):
    return {"ok": False, "repeat": True, "error": "Invalid input. Only letters allowed."}
```

Sanitize first (strip/upper), *then* validate the cleaned value.

#### `Game.create_players` (game.py:104-121) — player names

```python
for name in names:
    if not isinstance(name, str) or not name.strip():
        return {"ok": False, "error": "Player names must be non-empty strings."}
    cleaned.append(name.strip().title())

lowered = [n.lower() for n in cleaned]
if len(set(lowered)) != len(lowered):
    return {"ok": False, "error": "Player names must be unique (case-insensitive)."}
```

Here you see sanitization doing real work: `"  carlos "` → `strip()` → `"carlos"` → `title()` → `"Carlos"`. And validation of **uniqueness across values** (not just a single value): `"Alice"` and `"alice"` collide, caught by comparing the set of lowered names.

---

### 5. The public API: validating arguments before doing work

`get_by_difficulty` (word_repository.py:146-168) validates its parameter before touching any state:

```python
if not isinstance(difficulty, str):
    raise TypeError("Difficulty must be a string.")

key = difficulty.strip().upper()
if key not in self.EXPECTED_DIFFICULTIES:
    raise ValueError(f"Invalid difficulty: {difficulty!r}")
...
if not available:
    raise ValueError(f"No unused words remaining for difficulty: {key}")
```

Three distinct failure modes, three distinct messages — a beginner-friendly rule: **each error the caller could make gets its own check and its own message**. And the input is sanitized (`"  easy "` works — see `test_get_by_difficulty_normalizes_input`, test_word_repository.py:223).

---

### 6. Three error-reporting styles in one codebase (big teaching point)

Beginners often ask *"should I raise or return an error?"* — this project deliberately uses **all three styles, each where it fits**:

| Style | Where | Why it fits |
|---|---|---|
| **Raise exceptions** (`FileNotFoundError`, `ValueError`, `TypeError`) | `WordRepository._load`, `get_by_difficulty` | Program-level failures. The caller *cannot* meaningfully continue — a missing file or bad difficulty is a bug/misconfiguration, not a user mistake. Fail fast. |
| **Return a result dict** `{"ok": False, "error": "..."}` | `Game.set_word`, `guess_letter`, `guess_word`, `create_players` | User mistakes during play. The controller wants to **show the message and keep the loop running**, not crash. |
| **Silently skip** | `_load_from_dict`, `_add_if_valid` | Bulk data (the JSON file). One bad line shouldn't destroy 999 good words. |

The result-dict pattern also centralizes the state transition: the caller reads one structured answer and decides what to do, instead of catching five different exception types.

---

### 7. Key takeaways

1. **Validate at the boundary, sanitize into a canonical form** — external data (files, keyboards) is the only place you need heavy checks; internally, you can trust the canonical form.
2. **Whitelist, don't blacklist** — `ch.isalpha() or ch in {" ", "-"}` is future-proof; banning specific characters is not.
3. **Sanitization enables deduplication** — `"Apple"`, `"ápple"`, `" apple "` are only detectable as the same word *after* normalization, and the `set` storage makes duplicates impossible.
4. **Defense in depth** — the same rules (≥2 letters, allowed characters) are enforced in both `WordRepository` and `Game.set_word`, so no single bug corrupts game state.
5. **Pick the error style by context** — exceptions for programmer errors, result dicts for user mistakes, skipping for bulk data.
6. **Pin every rule with a test** — the parametrized valid/invalid tables in `test_word_repository.py:166-190` are the executable specification of exactly what "valid" means (including boundaries: 120 ok, 121 not).

---
---

## Topic 4.3 — Session-Level No-Repeat

The study guide summarizes this topic in one line:

> *Tracking previously used words using a `used_words` set inside `WordRepository` to prevent displaying the same word twice in a single session.*

Let's unpack what that means, why it's built the way it is, and see it in action with the real code.

---

### 1. The problem it solves

When the game picks a word **automatically** (word source option `2`), it uses `random.choice`. If we just picked randomly from the whole bucket every round, the player could get:

```
Round 1: DOG
Round 2: DOG   ← feels broken, and is unfair in a competitive game
Round 3: DOG
```

The fix: remember every word the repository has already handed out, and only pick from the words it **hasn't** handed out yet. That memory is the `used_words` set.

---

### 2. What "session" means here

A *session* is the lifetime of one `WordRepository` object. Look at where it's created — `hangman/controller/game_controller.py:22`:

```python
def __init__(self, view: ConsoleView, constants_module):
    ...
    self.word_repo = WordRepository(BASE_DIR / "data" / "word_bank.json")
```

The controller is created **once** per program run (in `run.py`), so the repository — and its `used_words` set — survives across **all rounds** of that run. The no-repeat rule therefore spans the whole play session:

- Round 1 uses `DOG` → round 2 can never be `DOG` again, even though it's a "new game".
- The only ways to clear the memory are: **quitting the program** (new process → new repository) or calling **`reset_session()`** explicitly.

That's exactly what "session-level" means: not per-round, not forever — per program run, with a manual escape hatch.

---

### 3. The three pieces of code

All of the logic lives in `hangman/services/word_repository.py`. The class docstring even lists it as a formal guarantee (line 17):

```python
class WordRepository:
    """
    Loads, validates, normalizes, and serves words/phrases.

    Guarantees:
    - All stored words satisfy Game.set_word() constraints
    - All internal storage is normalized
    - No-repeat enforced at session level
    """
```

#### Piece 1 — the memory itself (`__init__`, lines 23–30)

```python
def __init__(self, file_path: Union[str, Path]):
    self.file_path = Path(file_path).resolve()
    # Normalized words by difficulty
    self.normalized_words_by_diff: Dict[str, Set[str]] = {diff: set() for diff in self.EXPECTED_DIFFICULTIES}
    # used_words stores normalized forms (canonical) for dedup & no-repeat
    self.used_words: Set[str] = set()

    self._load()
```

Two important details:

- `used_words` starts **empty** — a fresh session has no history.
- The comment says it stores **normalized forms**. This is deliberate and connects to topic 4.1: the word bank is stored in canonical form (uppercased, accents stripped, spaces collapsed). If we stored raw forms instead, `"café"` and `"CAFE"` would look like *different* words and the no-repeat rule would silently fail.

#### Piece 2 — the enforcement (`get_by_difficulty`, lines 146–168)

```python
def get_by_difficulty(self, difficulty: str) -> str:
    ...
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
```

Three steps, in order:

1. **Compute the available pool** with a *set difference*:
   `available = bucket - used_words`.
   This is a pure computation — it does **not** remove anything from the word bank. The bucket stays intact; we just look at what's left.
2. **Fail loudly if the pool is empty** with a descriptive `ValueError`. Note the exact message `"No unused words remaining"` — the controller later greps for that string (more below).
3. **Pick and mark**: choose randomly, then `self.used_words.add(selection)`. The marking happens *after* the pick, so the word is excluded from the *next* call.

#### Piece 3 — the escape hatch (`reset_session`, lines 170–172)

```python
def reset_session(self) -> None:
    """Clear session-level used-word cache."""
    self.used_words.clear()
```

One line: wipe the history. The word bank itself is untouched, so every word becomes eligible again.

---

### 4. Walkthrough with the real word bank

`hangman/data/word_bank.json` has 5 EASY words: `dog, tree, sun, house, python`. After loading and normalizing, the EASY bucket is `{"DOG", "TREE", "SUN", "HOUSE", "PYTHON"}`.

| Round | Call | `available` (bucket − used) | Result | `used_words` after |
|---|---|---|---|---|
| 1 | `get_by_difficulty("EASY")` | all 5 | e.g. `DOG` | `{DOG}` |
| 2 | `get_by_difficulty("EASY")` | 4 (no DOG) | e.g. `SUN` | `{DOG, SUN}` |
| 3 | … | 3 | … | 3 words |
| 4 | … | 2 | … | 4 words |
| 5 | … | 1 | the last one | 5 words |
| 6 | … | `∅` | **`ValueError: No unused words remaining for difficulty: EASY`** | 5 words |

So with a 5-word bucket you get exactly 5 distinct words per session — then the repository *refuses* to repeat, and the error is the signal that tells the controller to offer recovery options.

---

### 5. Why a `set`? (and why `sorted`?)

- **`set` for `used_words`**: membership checks (`x in used_words`) are O(1), and a set can never contain duplicates — which is exactly the semantics we want ("has this word been used? yes/no"). A list would work but be slower and would need extra dedup logic.
- **`tuple(sorted(available))`**: `random.choice` needs a *sequence* (a set isn't indexable), and `sorted` makes the candidate list deterministic. That determinism is what lets tests mock `random.choice` and reason about exact outcomes — see `test_get_by_difficulty_mocked_random` in `tests/unit/test_word_repository.py:277`.

---

### 6. How the controller drives it

The controller never touches `used_words` directly — it only calls the two public methods. There are **three** interaction points in `hangman/controller/game_controller.py`:

#### a) The reset prompt between rounds (lines 53–60, 380–383)

After each finished round, `start()` asks:

```python
def choose_reset_session(self) -> bool:
    while True:
        choice = self.view.prompt(
            "Reset word history for the new game? (Y/N): "
        ).strip().upper()
        if choice in ("Y", "N"):
            return choice == "Y"
        self.view.display("Invalid input. Please choose Y or N.\n")
```

and in the round loop:

```python
# Optionally reset word session cache (NO-REPEAT MODE)
reset_words = self.choose_reset_session()
if reset_words:
    self.word_repo.reset_session()
```

So the player has a choice: keep the no-repeat memory (harder, more variety) or clear it (words can repeat).

#### b) Exhaustion recovery (lines 398–429)

When the automatic picker runs out of words, the `ValueError` from the repository is caught and turned into a menu:

```python
except ValueError as e:
    if self._is_exhaustion_error(e):
        self.view.display(
            f"{e}\n"
            "Recovery options:\n"
            "1) Reset word history for this session\n"
            "2) Choose a different difficulty\n"
            "3) Exit game\n"
        )
        choice = self.view.get_choice(["1", "2", "3"])

        if choice == "1":
            self.word_repo.reset_session()
            continue
        ...
```

where the exhaustion check is just a string match on the repository's error message (lines 62–63):

```python
def _is_exhaustion_error(self, error: ValueError) -> bool:
    return "No unused words remaining" in str(error)
```

This is a nice example of the repository *owning* the rule and the controller *reacting* to it: the repository says "I can't give you a word", and the controller decides what to do about it.

#### c) A nuance worth knowing

Manual word entry (source `1`, the moderator types a secret word via `prompt_hidden`) goes straight to `game.set_word(...)` and **bypasses the repository entirely** — so manually entered words are neither checked against nor added to `used_words`. No-repeat applies only to the automatic picker.

---

### 7. The tests that pin this behavior

`tests/unit/test_word_repository.py`:

**The word gets marked as used** (lines 227–229):
```python
def test_get_by_difficulty_marks_used(repo_with_words):
    word = repo_with_words.get_by_difficulty("easy")
    assert word in repo_with_words.used_words
```

**No repeats** (lines 232–237) — the fixture has exactly two EASY words (`cat`, `dog`), so two draws must yield both, as a set:
```python
def test_get_by_difficulty_no_repeats(repo_with_words):
    results = {
        repo_with_words.get_by_difficulty("easy"),
        repo_with_words.get_by_difficulty("easy")
    }
    assert results == {"CAT", "DOG"}
```

**Exhaustion** (lines 240–244) — a one-word bucket works once, then raises:
```python
def test_get_by_difficulty_exhaustion(repo_single_word):
    repo_single_word.get_by_difficulty("easy")

    with pytest.raises(ValueError):
        repo_single_word.get_by_difficulty("easy")
```

And at the controller level, `tests/unit/test_game_controller.py` verifies the reset decision with a **mocked** repository (this is where the Repository pattern pays off — the mock only needs to know `get_by_difficulty` and `reset_session`):

```python
def test_start_resets_word_session(controller_factory):
    ...
    view.prompt.side_effect = ["Y", "Y", "1", "word", "N"]  # continue, reset=Y, ...
    controller.start()
    controller.word_repo.reset_session.assert_called()

def test_start_continue_without_reset(controller_factory):
    ...
    view.prompt.side_effect = ["Y", "N", "1", "word", "N"]  # continue, reset=N, ...
    controller.start()
    controller.word_repo.reset_session.assert_not_called()
```

---

### 8. Key takeaways

1. **State lives with the data.** The "don't repeat words" rule is enforced entirely inside `WordRepository`. The controller and the `Game` model never track used words — they just ask, and the repository refuses to repeat. That's encapsulation and SRP in action.
2. **A `set` is the natural data structure** for "things I've already seen": O(1) checks, no duplicates, and set difference (`bucket - used`) computes the available pool in one expression.
3. **Normalize before you compare.** Storing canonical forms in `used_words` means `"café"`, `"CAFE"`, and `"cafe"` are all recognized as the *same* word — no-repeat and accent-insensitivity (topic 4.1) compose cleanly.
4. **Finite resources need a failure path and a recovery path.** The word bank is finite, so the code defines what "out of words" looks like (a descriptive `ValueError`) and what the user can do about it (reset / switch difficulty / exit).
5. **"Session" is just object lifetime.** No global state, no persistence — the history exists as long as the repository object exists, and `reset_session()` is the explicit way to end it early.

A good exercise to try: add a test that builds a repo from `{"easy": ["café", "CAFE"]}` and asserts that `get_by_difficulty("easy")` raises `ValueError` on the *first* call — because normalization collapses both entries into one word, so the bucket has only one usable word. That test would prove the no-repeat rule and the normalization rule work together.

---
---

## Topic 4.4 — Configuration Externalization

The study guide summarizes this topic in one line:

> *Moving constant values like maximum health and ASCII hangman graphics into a standalone `constants.py` module rather than scatter-storing them within classes.*

Let's unpack what that means, why it's built the way it is, and see it in action with the real code.

---

### 1. The concept in one sentence

**Configuration externalization** means pulling the *values that define how the app behaves* (max health, the ASCII art, difficulty levels…) out of the classes that use them, and placing them in a dedicated, standalone module — so that **behavior** (logic) and **configuration** (data) can change independently.

The key distinction to hold onto:

| Kind of thing | Question it answers | Example in this project |
|---|---|---|
| **Behavior (logic)** | *"What does the program do?"* | `Game.guess_letter` applies the rules; `Player.lose_health` decrements health |
| **Configuration (data)** | *"How is the program tuned?"* | `MAX_HEALTH = 7`, the `HANGMAN` ASCII frames |

Once configuration lives in its own module, you can change *how the game is tuned* without ever touching *what the game does*.

---

### 2. The anti-pattern: what the code would look like *without* it

Imagine the "naive" version of this project. The magic values would be scattered inside the classes:

```python
# ❌ BAD: configuration scattered inside behavior
class Player:
    def __init__(self, name):
        self.name = name
        self.max_health = 7          # magic number, buried in the model

class ConsoleView:
    def show_health(self, player):
        if player.health == 7:
            print("     _______\n    |       | ...")   # 8 giant ASCII blocks
        elif player.health == 6:
            print("     _______\n    |       | ...")   # copy-pasted, slightly different
        ...
```

Problems with this:

1. **Magic numbers** — where did `7` come from? You have to open the class to find out.
2. **Change amplification** — to make the game harder (5 lives instead of 7), you'd edit `Player`, *and* every `if/elif` branch in the view, *and* any test that hardcodes 7.
3. **Untestable** — a unit test for `Player` is forced to use 7 lives even when it wants to test "a player with 1 life" cheaply.
4. **Hidden coupling** — the view now *knows* the exact health values, so model and view are welded together.

---

### 3. How this project does it — file by file

#### Step 1 — the standalone configuration module: `hangman/constants.py`

All tunable values live in one small, dependency-free module:

```python
# hangman/constants.py:1-2
MAX_HEALTH = 7
HANGMAN = [
    """     _______
    |       |
    |       O
    ...
    |      / \ """,
    ...   # 8 frames total, from "complete figure" down to "empty gallows"
]
```

Two things to notice:

- `MAX_HEALTH = 7` — the single source of truth for how many lives a player has.
- `HANGMAN` is a **list of 8 strings** (indices 0–7). Index 0 is the fully drawn figure; index 7 is the empty gallows. The list is ordered from *most drawn* to *least drawn*.

#### Step 2 — the composition root wires it in: `run.py`

`run.py` is the **only** place in the whole project that imports the real constants module. It's the "composition root" — the single spot where real dependencies are assembled:

```python
# run.py:3, 6-9
from hangman import constants

def run():
        view = ConsoleView()
        controller = GameController(view=view, constants_module=constants)
        controller.start()
```

Note that the **module itself** is passed as a value (`constants_module=constants`), not individual numbers. The module acts as a *namespace object* bundling all configuration together.

#### Step 3 — the controller receives and forwards it: `game_controller.py`

```python
# game_controller.py:16-18
def __init__(self, view: ConsoleView, constants_module):
    self.view = view
    self.c = constants_module          # stored, never imported
```

```python
# game_controller.py:73
self.game = Game(constants_module=self.c, normalize_input=normalize)
```

The controller never does `from hangman import constants`. It just carries the configuration it was given and hands it to the model. This is **dependency injection** applied to configuration — exactly the same mechanism used for the `view` (topic 1.3).

#### Step 4 — the model consumes it: `game.py`

```python
# game.py:11-12
def __init__(self, constants_module, normalize_input: bool = True):
    self.c = constants_module
```

```python
# game.py:118
self.players = [Player(n, self.c.MAX_HEALTH, self.c.HANGMAN) for n in cleaned]
```

This is the key line: `Player(n, self.c.MAX_HEALTH, self.c.HANGMAN)`. The `Game` reads the configuration through the injected object and **decomposes it into plain values** before passing them down.

#### Step 5 — the leaf class knows nothing about configuration: `player.py`

```python
# player.py:7-11
def __init__(self, name: str, max_health: int, hangman_states: List[str]):
    self.name = name
    self.max_health = max_health
    self.health = max_health
    self.hangman_states = hangman_states
```

`Player` has **no idea** that `constants.py` exists. It just receives an integer and a list. It's fully generic — you could build a `Player` for a completely different game with 3 lives and emoji "health bars".

#### Step 6 — the view reads the data through the model: `console_view.py`

```python
# console_view.py:52-54
def show_health(self, player) -> None:
    print(player.hangman_states[player.health])
    print()
```

The view doesn't import `constants` either. It simply indexes the list that the player carries, using the player's current health as the index. The graphics are **data flowing through the model**, not logic hardcoded in the view.

---

### 4. The full flow of the configuration

```
constants.py  (MAX_HEALTH=7, HANGMAN[8 frames])
     │  imported once
     ▼
run.py  ──────────────►  GameController(constants_module=constants)
     (composition root)        │  self.c
                               ▼
                        Game(constants_module=self.c)
                               │  self.c.MAX_HEALTH, self.c.HANGMAN
                               ▼
                        Player(max_health, hangman_states)
                               │  player.hangman_states[player.health]
                               ▼
                        ConsoleView.show_health(player)
```

Every arrow is a **parameter**, never an import. Only the top of the chain touches the real module.

---

### 5. The payoff: tests with *different* configurations

This is where externalization really shines. Because every class accepts configuration as a parameter, the test suite can run the game with entirely different rules:

**`tests/unit/test_game.py:9-19`** — a fake constants module with 3 lives instead of 7:

```python
class DummyConstants:
    MAX_HEALTH = 3
    HANGMAN = ["H", "A", "N", "G", "M", "A", "N"]

@pytest.fixture
def constants():
    return DummyConstants()

@pytest.fixture
def game(constants):
    return Game(constants)
```

The tests exercise `Game` with a 3-life configuration **without ever touching the real `constants.py`**.

**`tests/unit/test_game_controller.py:69`** — the controller doesn't even need real values, so a bare `Mock()` suffices:

```python
controller = GameController(view=view, constants_module=Mock())
```

**`tests/unit/test_player.py:9-25`** — the factory fixture builds players with whatever health the test wants:

```python
def _make_player(name="Alice", max_health=5, hangman_states=None):
    ...
    return Player(name=name, max_health=max_health, hangman_states=hangman_states)
```

**`tests/integration/test_run.py:79-82`** — even the wiring itself is verified: the integration test asserts that `run()` passes the *real* module through:

```python
assert "constants_module" in kwargs
assert kwargs["constants_module"] is run_module.constants
```

Notice a subtle consequence: because the parameter is typed as a plain `constants_module` (no type annotation), **anything with `MAX_HEALTH` and `HANGMAN` attributes works** — the real module, `DummyConstants`, or a `Mock`. That's duck typing doing its job (topic 1.5), and it's what makes all of the above possible.

---

### 6. A subtle detail worth understanding: the 8 frames vs. 7 lives

`MAX_HEALTH = 7` but `HANGMAN` has **8** entries. Why? Because the index used is the *current* health, which ranges from `7` (full) down to `0` (dead):

| `player.health` | frame shown | figure state |
|---|---|---|
| 7 (new player) | `HANGMAN[7]` | empty gallows |
| 5 | `HANGMAN[5]` | head only |
| 3 | `HANGMAN[3]` | head + torso + one arm |
| 1 | `HANGMAN[1]` | nearly complete |
| 0 (eliminated) | `HANGMAN[0]` | complete figure |

So the figure is drawn *as the player loses health*, and the list is ordered from most-drawn (index 0) to least-drawn (index 7). The hidden invariant is:

```
len(HANGMAN) >= MAX_HEALTH + 1
```

If someone changed `MAX_HEALTH` to 10 without adding frames, `player.hangman_states[player.health]` would raise an `IndexError` at runtime. This is a classic "gotcha" of externalized configuration: **the values in the config module must stay consistent with each other**, and a single module at least makes that consistency visible in one place.

---

### 7. Why this design is good (summary)

| Benefit | Where you see it |
|---|---|
| **Single source of truth** | Change `MAX_HEALTH` in one file; `Game`, `Player`, and the view all follow automatically. |
| **Testability** | `DummyConstants` (3 lives), `Mock()`, and `max_health=5` in fixtures — tests run with arbitrary configurations. |
| **Loose coupling** | `Player`, `Game`, `ConsoleView` never import `constants.py`; they only receive values. |
| **Swappable configurations** | You could create `constants_hard.py` with `MAX_HEALTH = 5` and swap it in `run.py` without editing a single class. |
| **Consistency with DI** | Configuration is injected exactly like the `view` — one uniform mechanism for "things this component needs from outside". |

---

### 8. Key takeaways

1. **Configuration is data, not logic.** Keep it in a dedicated module (`constants.py`) so it can be read, changed, and swapped without touching behavior.
2. **Inject, don't import.** Only the composition root (`run.py`) imports the real module; everything downstream receives it as a constructor parameter.
3. **Decompose at the boundary.** `Game` converts the module into plain values (`self.c.MAX_HEALTH`) before passing them to `Player`, so leaf classes stay completely generic.
4. **The test suite is the proof.** The ability to run the same `Game` logic with 3 lives, 5 lives, or a `Mock` is the direct, measurable benefit of externalizing the configuration.

A good exercise to try: create a second constants module (e.g., `MAX_HEALTH = 5` with 6 frames) and run the game with it from a modified `run.py` — you'll see firsthand that no class needed any changes.
