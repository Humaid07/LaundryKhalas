"""Deterministic customer-reply style normaliser (spec 2026-07-31 — no dashes).

Runs immediately before a customer-facing WhatsApp message is sent, as a safety net
BEHIND the system-prompt style rules: even if the model emits dash formatting, this
pure function rewrites it into natural prose WITHOUT a second LLM call.

It removes, from natural customer-facing language only:
  * dash bullet markers at line start ("- item"  → "item")
  * en dashes (–) and em dashes (—) used as separators
  * dash time ranges     ("6 PM - 8 PM"  → "6 PM to 8 PM")
  * dash turnaround/unit ranges ("1-2 days" / "1–2 days" → "1 to 2 days")
  * spaced numeric ranges ("AED 100 - 200" → "AED 100 to 200")

It MUST NOT touch machine values. Before rewriting, it masks and later restores:
  * URLs and email addresses
  * identifiers with a letter in them (LK-AE-1024, coupon codes, UUIDs, provider
    message ids)
  * all-digit multi-hyphen sequences (phone numbers, numeric refs)
so an order id like ``LK-AE-1024`` or a payment link is returned byte-for-byte.

The no-dash rule applies to customer prose ONLY — never to internal logs, JSON,
tool arguments, or DB values, which never pass through here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- protected spans (masked out before any rewrite, restored after) ---------
_URL = re.compile(r"https?://\S+|www\.\S+")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Hyphen-joined token containing at least one letter: LK-AE-1024, SAVE-20, a UUID,
# "well-known", "24-hour". Pure number-number ranges (1-2) are deliberately NOT
# matched here so the range rules can convert them.
_ALPHA_HYPHEN = re.compile(r"\b\w+(?:-\w+)+\b")
# All-digit sequence with 2+ hyphens: phone numbers / numeric refs (050-123-4567).
_NUM_ID = re.compile(r"\b\d+(?:-\d+){2,}\b")

_OPEN, _CLOSE = "", ""

# --- rewrite patterns --------------------------------------------------------
_BULLET = re.compile(r"(?m)^[ \t]*[-–—•]\s+")
_TIME_RANGE = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*[AaPp]\.?[Mm]\.?)\s*[-–—]\s*(\d{1,2}(?::\d{2})?\s*[AaPp]\.?[Mm]\.?)"
)
_UNIT_RANGE = re.compile(
    r"(\d+)\s*[-–—]\s*(\d+)(\s*(?:days?|hours?|hrs?|weeks?|minutes?|mins?|"
    r"business\s+days?|working\s+days?))",
    re.IGNORECASE,
)
_NUM_RANGE = re.compile(r"(\d+)\s*[-–—]\s*(\d+)")
_EM = re.compile(r"\s*—\s*")
_EN = re.compile(r"\s*–\s*")
_SPACED_HYPHEN = re.compile(r"\s+-\s+")
_CAP_AFTER_STOP = re.compile(r"(\.\s+)([a-z])")

# --- validation (run on the masked text, so identifiers never trip it) -------
_RESIDUAL = [
    re.compile(r"[–—]"),          # any en/em dash left
    _BULLET,                       # dash bullet line
    re.compile(r"\d\s*-\s*\d"),   # numeric range still using a hyphen
    re.compile(r"\s-\s"),         # spaced hyphen separator
]


@dataclass
class NormalizationResult:
    text: str
    changed: bool
    dash_count: int          # dashes detected in the ORIGINAL customer prose
    emoji_count: int = 0     # emoji / pictographic codepoints removed
    exclaim_count: int = 0   # exclamation marks removed from routine prose
    rules_applied: list[str] = field(default_factory=list)
    valid: bool = True       # True when no offending dash formatting remains


# --- emoji / pictographic-symbol removal (customer prose only) ---------------
# Covers the standard emoji planes plus the common emoji-adjacent BMP symbol
# blocks (misc symbols, dingbats incl. check marks, stars, clocks, warning),
# plus the zero-width joiner, variation selectors and keycap combiner that glue
# multi-codepoint emoji together. Latin/accented letters, currency symbols,
# ASCII punctuation and identifiers all live OUTSIDE these ranges, so order ids,
# URLs, emails, prices, phone numbers, names and payment links are never touched.
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoticons, pictographs, transport, supplemental, flags, skin tones
    "\U00002600-\U000027BF"   # misc symbols + dingbats (checks ✅ ✔, warning ⚠, ✂ ✈ ✉ ✨ ❌ ❤)
    "\U00002B00-\U00002BFF"   # stars / block arrows (⭐ ⬛)
    "\U00002300-\U000023FF"   # clocks / hourglass / media (⌚ ⌛ ⏰ ⏳ ▶)
    "\U0000FE00-\U0000FE0F"   # variation selectors (emoji-presentation glue)
    "\U00002049\U0000203C\U00002139\U000020E3\U0000200D"  # ⁉ ‼ ℹ keycap ZWJ
    "]"
)


def strip_emojis(text: str) -> tuple[str, int]:
    """Remove emoji / decorative pictographs from customer prose, tidying the
    whitespace they leave behind. Returns ``(clean_text, codepoints_removed)``.
    Deterministic; never touches ASCII/alphanumeric content (order ids, URLs,
    prices, phone numbers, names, payment links, structured data)."""
    stripped = _EMOJI.sub("", text)
    removed = len(text) - len(stripped)
    if not removed:
        return text, 0
    stripped = re.sub(r"[ \t]{2,}", " ", stripped)            # collapse gaps left behind
    stripped = re.sub(r" +([.,!?;:])", r"\1", stripped)       # kill space before punctuation
    stripped = re.sub(r"(?m)[ \t]+$", "", stripped)           # trailing spaces per line
    return stripped.strip(), removed


def _mask(text: str) -> tuple[str, list[str]]:
    spans: list[str] = []

    def repl(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"{_OPEN}{len(spans) - 1}{_CLOSE}"

    def repl_alpha(m: re.Match) -> str:
        # Only protect a hyphen token that actually contains a letter (LK-AE-1024,
        # coupon codes, UUIDs, hyphenated words). Pure number-number tokens like
        # "1-2" are left for the range rules to convert.
        if any(c.isalpha() for c in m.group(0)):
            return repl(m)
        return m.group(0)

    for pat in (_URL, _EMAIL, _NUM_ID):
        text = pat.sub(repl, text)
    text = _ALPHA_HYPHEN.sub(repl_alpha, text)
    return text, spans


def _unmask(text: str, spans: list[str]) -> str:
    for i, s in enumerate(spans):
        text = text.replace(f"{_OPEN}{i}{_CLOSE}", s)
    return text


# --- exclamation-mark normalisation (routine customer prose only) ------------
# Routine replies should end with a full stop, not "!". A run mixing ! and ?
# (e.g. "?!" / "!?") collapses to a single "?". Applied to MASKED prose, so URLs,
# order ids, emails and payment links (already masked) are never touched.
_EXCLAIM_Q = re.compile(r"[!?]*\?[!?]*")
_EXCLAIM = re.compile(r"!+")
_MULTIDOT = re.compile(r"\.{2,}")


def normalize_customer_reply(text: str | None) -> NormalizationResult:
    """Rewrite ``text`` into natural, dash-free customer prose. Deterministic and
    side-effect free — the same input always yields the same output. Machine values
    (URLs, emails, identifiers, refs) are preserved exactly."""
    if not text or not str(text).strip():
        return NormalizationResult(text=text or "", changed=False, dash_count=0)

    raw = str(text)
    # 1) remove emojis / decorative pictographs first — disjoint from identifiers,
    #    so order ids, URLs, emails, prices, phone numbers, names and payment links
    #    are never touched.
    no_emoji, emoji_count = strip_emojis(raw)
    original = no_emoji
    masked, spans = _mask(original)
    # Count dashes only in the PROSE (masked text), so an identifier's own hyphens
    # are not counted as style violations.
    dash_count = sum(masked.count(c) for c in ("-", "–", "—"))
    exclaim_count = masked.count("!")

    rules: list[str] = ["emoji"] if emoji_count else []
    work = masked

    new = _BULLET.sub("", work)
    if new != work:
        rules.append("dash_bullet")
        work = new

    new = _TIME_RANGE.sub(r"\1 to \2", work)
    if new != work:
        rules.append("time_range")
        work = new

    new = _UNIT_RANGE.sub(r"\1 to \2\3", work)
    if new != work:
        rules.append("turnaround_range")
        work = new

    new = _NUM_RANGE.sub(r"\1 to \2", work)
    if new != work:
        rules.append("numeric_range")
        work = new

    new = _EM.sub(". ", work)
    if new != work:
        rules.append("em_dash")
        work = _CAP_AFTER_STOP.sub(lambda m: m.group(1) + m.group(2).upper(), new)

    new = _EN.sub(", ", work)
    if new != work:
        rules.append("en_dash")
        work = new

    new = _SPACED_HYPHEN.sub(", ", work)
    if new != work:
        rules.append("spaced_hyphen")
        work = new

    # Exclamation marks → full stops (a run containing "?" collapses to "?").
    excl = _EXCLAIM_Q.sub("?", work)
    excl = _EXCLAIM.sub(".", excl)
    excl = _MULTIDOT.sub(".", excl)
    if excl != work:
        rules.append("exclamation")
        work = excl

    valid = not any(p.search(work) for p in _RESIDUAL)
    final = _unmask(work, spans)
    return NormalizationResult(
        text=final,
        changed=final != raw,
        dash_count=dash_count,
        emoji_count=emoji_count,
        exclaim_count=exclaim_count,
        rules_applied=rules,
        valid=valid,
    )
