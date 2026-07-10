"""Capture step: handwritten page images -> proofread-ready text (the Normalizer).

Groups page images by date, sends ALL pages of one entry to Gemini vision in a single
call (so text flowing across page breaks stays continuous), and writes one combined
transcript per entry to data/transcripts/YYYY-MM-DD.md.

  python -m mirror.transcribe

Then PROOFREAD the files in data/transcripts/ (fix any misread words) before running
`python -m mirror.prototype`. This is the trust gate — nothing enters the graph unverified.

Naming convention it expects in data/entries/:
  2024-01-06-1.jpeg, 2024-01-06-2.jpeg, ...   -> one 4-page entry dated 2024-01-06
  2025-01-03.jpeg                              -> one single-page entry
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

DEFAULT_VISION_MODEL = "gemini-3.5-flash"  # multimodal — reads handwriting; override in .env
ENTRIES_DIR = Path("data/entries")
TRANSCRIPTS_DIR = Path("data/transcripts")

# YYYY-MM-DD  with an optional -N page suffix
NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d+))?$")
MIME = {".jpeg": "image/jpeg", ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}

PROMPT = (
    "You are transcribing a handwritten personal journal entry. "
    "The images are consecutive pages of ONE entry, in order. "
    "Transcribe the handwriting into clean plain text, exactly as written — do not "
    "summarize, correct, censor, or add commentary. Preserve paragraph breaks. "
    "Treat the pages as one continuous entry: if a sentence runs across a page break, "
    "join it naturally. Output only the transcribed text."
)


def group_entries() -> dict[str, list[Path]]:
    """date -> [page paths in page order]."""
    if not ENTRIES_DIR.exists():
        raise SystemExit(f"  No {ENTRIES_DIR}/ — put your page images there first.")
    groups: dict[str, list[tuple[int, Path]]] = {}
    for path in ENTRIES_DIR.iterdir():
        if path.suffix.lower() not in MIME:
            continue
        m = NAME_RE.match(path.stem)
        if not m:
            print(f"  ! skipping {path.name} — expected YYYY-MM-DD[-N].<img>")
            continue
        date, page = m[1], int(m[2]) if m[2] else 1
        groups.setdefault(date, []).append((page, path))
    return {d: [p for _, p in sorted(pages)] for d, pages in sorted(groups.items())}


def transcribe_entry(client: genai.Client, pages: list[Path], model: str) -> str:
    parts = [types.Part.from_text(text=PROMPT)]
    for p in pages:
        parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=MIME[p.suffix.lower()]))
    resp = client.models.generate_content(model=model, contents=parts)
    return (resp.text or "").strip()


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("  Set GEMINI_API_KEY in .env (see .env.example).")
    os.environ.pop("GOOGLE_API_KEY", None)   # use our .env key unambiguously

    entries = group_entries()
    if not entries:
        raise SystemExit(f"  No dated page images found in {ENTRIES_DIR}/.")
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    model = os.getenv("MIRROR_VISION_MODEL", DEFAULT_VISION_MODEL)
    client = genai.Client(api_key=api_key)
    print(f"\n  Transcribing {len(entries)} entries with {model}...\n")
    for date, pages in entries.items():
        pagelabel = f"{len(pages)} page{'s' if len(pages) > 1 else ''}"
        print(f"  → {date}  ({pagelabel}: {', '.join(p.name for p in pages)})")
        text = transcribe_entry(client, pages, model)
        out = TRANSCRIPTS_DIR / f"{date}.md"
        out.write_text(text + "\n", encoding="utf-8")
        print(f"      wrote {out}  [{len(text)} chars]")

    print(
        f"\n  Done. Now PROOFREAD the files in {TRANSCRIPTS_DIR}/ against your notebook —\n"
        f"  fix any misread words — then run:  python -m mirror.prototype\n"
    )


if __name__ == "__main__":
    main()
