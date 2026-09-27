"""Fails while the generated shared files are stale.

The detection layer runs in two languages now — Python on the server, Dart on the
device — and Dart consumes generated JSON rather than a hand-written copy. That
only prevents drift if the JSON is regenerated after every change to the rules, so
the suite enforces it instead of relying on anyone remembering.

If this fails, run:  python tools/export_shared.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tools"))

import export_shared  # noqa: E402
import safety  # noqa: E402

FILES = ("safety_rules.json", "referrals.json", "safety_cases.json")

GENERATORS = {
    "safety_rules.json": export_shared.safety_rules,
    "referrals.json": export_shared.referral_data,
    "safety_cases.json": export_shared.test_cases,
}


@pytest.mark.parametrize("name", FILES)
def test_generated_file_is_current(name: str) -> None:
    """What is on disk must equal what the exporter would write right now."""
    path = export_shared.SERVICE_SHARED / name
    assert path.exists(), f"{name} has never been exported"

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    expected = json.loads(json.dumps(GENERATORS[name](), ensure_ascii=False))
    assert on_disk == expected, (
        f"{name} is stale — the rules changed since it was exported.\n"
        "Run: python tools/export_shared.py"
    )


@pytest.mark.parametrize("name", FILES)
def test_flutter_copy_matches_the_service_copy(name: str) -> None:
    """The app bundles one copy and the container ships another; byte-identical
    or the phone and the server are running different rules."""
    service = (export_shared.SERVICE_SHARED / name).read_text(encoding="utf-8")
    flutter = (export_shared.FLUTTER_ASSETS / name).read_text(encoding="utf-8")
    assert service == flutter, f"{name} differs between shared/ and the app assets"


def test_every_category_has_response_text() -> None:
    """A category with no message would reach a user as an empty reply."""
    responses = export_shared.referral_data()["responses"]
    for category in safety.EMERGENCY_CATEGORIES + safety.REFUSAL_CATEGORIES:
        assert category in responses, f"{category} has no response text"
        for language in ("en", "bn"):
            assert responses[category][language].strip(), f"{category}/{language} empty"


def test_exported_patterns_are_portable_to_dart() -> None:
    """Dart's RegExp is JavaScript-flavoured; Python's re is not.

    These constructs work in Python and fail or behave differently in Dart, so a
    pattern using one would pass the Python tests and silently misbehave on the
    device. Cheap to check, and the failure mode it prevents is invisible.
    """
    forbidden = {
        "(?<=": "lookbehind",
        "(?<!": "negative lookbehind",
        "(?P<": "named group",
        r"\p{": "unicode property",
        r"\Z": "end-of-string anchor",
        r"\A": "start-of-string anchor",
        "(?#": "comment group",
    }
    for category, patterns in export_shared.safety_rules()["patterns"].items():
        for pattern in patterns:
            for token, description in forbidden.items():
                assert token not in pattern, (
                    f"{category} uses {description} ({token}), which Dart cannot "
                    f"run: {pattern}"
                )


def test_shared_cases_cover_both_languages_and_all_outcomes() -> None:
    cases = export_shared.test_cases()["cases"]
    assert len(cases) >= 40
    languages = {case["language"] for case in cases}
    assert languages == {"en", "bn"}
    kinds = {case["kind"] for case in cases}
    assert kinds == {"emergency", "refuse", "proceed"}
    # Every emergency category should appear at least once in the shared corpus:
    # an untested emergency category is the one that fails in the field.
    covered = {case["category"] for case in cases}
    for category in safety.EMERGENCY_CATEGORIES:
        assert category in covered, f"no shared case covers {category}"
