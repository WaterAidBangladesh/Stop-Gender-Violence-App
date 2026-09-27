"""Reads the Knowledge Hub topic texts straight out of the Flutter source.

The app's topic content lives as Dart string literals in
`lib/screens/knowledge_detail_screen.dart`. Copying it into this repository
would create a second copy that silently drifts from what users actually read
in the app, and the brief is explicit that the corpus is WaterAid's own
material — so the Dart file stays the single source of truth and this module
parses it at index time.

Three further topic texts exist in that file but are commented out of the hub
list, so users cannot see them in the app. Reviewed 2026-09-26, and they do not
all get the same answer:

* **Types of Gender-Based Violence** — INCLUDED. Finished content: a complete
  five-part taxonomy (physical, sexual, psychological, economic, harmful
  traditional practices), each with an explanation, credited to MJF. Nothing
  reads as draft.
* **Safeguarding Principles** — INCLUDED. Finished content: five named
  principles (do no harm, confidentiality, survivor-centred, accountability,
  non-discrimination), credited to the WaterAid Global Safeguarding Policy.
  Terse but complete.
* **Reporting Mechanisms** — EXCLUDED, and not because it looks like a draft;
  it reads as finished, credited WaterAid policy. Two specific conflicts:

  1. It says reporting can be done by "anonymous reporting through apps or
     hotlines". In *this* app that is not true today: the report form is
     unreachable from any screen, and submitting requires a signed-in user, so
     the anonymous route does not exist. Indexing this would have Bharosha
     telling a survivor to use a capability the app does not have.
  2. It instructs the reader to include "any evidence or witness details" in a
     report. That collides head-on with the standing rule never to suggest
     gathering evidence against an abuser. safety.py refuses questions that
     *ask* how to gather evidence, but a retrieved passage that volunteers it
     would route around that refusal entirely.

  Enable it with one flag once (1) in-app reporting actually works and (2)
  WaterAid decides how the evidence line should be handled.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Set True only when in-app reporting works and the "include any evidence" line
# has been resolved with WaterAid. See the module docstring.
INCLUDE_REPORTING_MECHANISMS = False

# topic id -> (Dart list variable, the title the Knowledge Hub shows, indexed)
TOPICS: dict[str, tuple[str, str, bool]] = {
    "1": ("_safeguardingSections", "What is Safeguarding?", True),
    "2": ("_gbvSections", "What is Gender-Based Violence?", True),
    "3": ("_typesOfGbvSections", "Types of Gender Based Violence", True),
    "4": ("_rolesAndResponsibilitiesSections", "Roles & Responsibilities in Safeguarding", True),
    "5": ("_reportingMechanismsSections", "Reporting Mechanisms", INCLUDE_REPORTING_MECHANISMS),
    "6": ("_preventionGbvSections", "Prevention of Gender Based Violence", True),
    "7": ("_mythsFactsSections", "Myths vs. Facts about Gender Based Violence", True),
    "8": ("_safeguardingPrinciplesSections", "Safeguarding Principles", True),
}

# Parsing the Dart file needs the Flutter project next door, which is not in the
# container. build_index.py writes this snapshot whenever it parses the Dart
# successfully, and load_sections falls back to it when the Dart is absent — so
# the image builds reproducibly from the service repo alone, while the Dart file
# stays the single source of truth wherever it is available.
SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "corpus" / "knowledge_hub.json"

DEFAULT_DART_PATH = (
    Path(__file__).resolve().parents[2]
    / "stop_gender_violence_fresh_ui"
    / "lib"
    / "screens"
    / "knowledge_detail_screen.dart"
)


@dataclass(frozen=True)
class Section:
    """One titled section of one topic, with the credit the app displays."""

    topic_id: str
    topic_title: str
    section_title: str
    content: str
    credit: str | None

    @property
    def source(self) -> str:
        """Attribution string carried through to the answer.

        Bharosha credits its sources the way the app already credits each topic,
        so a reader can see where a statement came from.
        """
        if self.credit:
            cleaned = self.credit.lstrip("*").replace("Source:", "").strip()
            return f"{self.topic_title} — {cleaned}"
        return f"{self.topic_title} (WaterAid Shomota Shurokkha Knowledge Hub)"


# Dart adjacent-literal concatenation: "a" "b" across newlines is one string.
_STRING_RUN = re.compile(r'(?:"(?:[^"\\]|\\.)*"\s*)+', re.DOTALL)
_ONE_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"', re.DOTALL)
_ENTRY_KEY = re.compile(r'"(title|content|credit)"\s*:\s*')

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    '"': '"',
    "'": "'",
    "\\": "\\",
    "$": "$",
}


def _unescape(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        char = raw[i]
        if char == "\\" and i + 1 < len(raw):
            out.append(_ESCAPES.get(raw[i + 1], raw[i + 1]))
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _join_literals(run: str) -> str:
    return "".join(_unescape(m.group(1)) for m in _ONE_STRING.finditer(run))


def _list_body(dart: str, variable: str) -> str:
    """The text between the brackets of `final List<...> variable = [ ... ];`."""
    start = dart.find(variable)
    if start == -1:
        raise ValueError(f"{variable} not found — did the Dart file change?")
    open_bracket = dart.find("[", start)
    if open_bracket == -1:
        raise ValueError(f"no list literal after {variable}")
    depth = 0
    for i in range(open_bracket, len(dart)):
        if dart[i] == "[":
            depth += 1
        elif dart[i] == "]":
            depth -= 1
            if depth == 0:
                return dart[open_bracket + 1 : i]
    raise ValueError(f"unbalanced brackets in {variable}")


def _entries(list_body: str) -> list[dict[str, str]]:
    """Split a Dart list of maps into one dict per `{ ... }` block."""
    entries: list[dict[str, str]] = []
    depth = 0
    start = None
    for i, char in enumerate(list_body):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                entries.append(_entry_fields(list_body[start + 1 : i]))
                start = None
    return [e for e in entries if e.get("content")]


def _entry_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key_match in _ENTRY_KEY.finditer(block):
        run = _STRING_RUN.match(block, key_match.end())
        if run:
            fields[key_match.group(1)] = _join_literals(run.group(0)).strip()
    return fields


def save_snapshot(sections: list[Section]) -> None:
    """Record the parsed sections so a container can build without the Dart."""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(
            [
                {
                    "topic_id": s.topic_id,
                    "topic_title": s.topic_title,
                    "section_title": s.section_title,
                    "content": s.content,
                    "credit": s.credit,
                }
                for s in sections
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_snapshot() -> list[Section]:
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return [Section(**entry) for entry in raw]


def load_sections(dart_path: Path | None = None) -> list[Section]:
    """Every indexable section, in topic order.

    Prefers the Dart file. Falls back to the snapshot when it is absent, which
    is the case inside the container.
    """
    path = dart_path or DEFAULT_DART_PATH
    if not path.exists():
        if SNAPSHOT_PATH.exists():
            return load_snapshot()
        raise FileNotFoundError(
            f"neither {path} nor the snapshot at {SNAPSHOT_PATH} is available"
        )
    dart = path.read_text(encoding="utf-8")

    sections: list[Section] = []
    for topic_id, (variable, topic_title, indexed) in sorted(TOPICS.items()):
        if not indexed:
            continue
        for entry in _entries(_list_body(dart, variable)):
            sections.append(
                Section(
                    topic_id=topic_id,
                    topic_title=topic_title,
                    section_title=entry.get("title", topic_title),
                    content=entry["content"],
                    credit=entry.get("credit"),
                )
            )
    if not sections:
        raise ValueError(f"no sections parsed from {path}")
    return sections


if __name__ == "__main__":  # quick manual check: python app/knowledge_source.py
    for section in load_sections():
        print(f"[{section.topic_id}] {section.section_title} "
              f"({len(section.content)} chars) — {section.source}")
