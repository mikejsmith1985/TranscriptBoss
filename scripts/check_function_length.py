"""Enforce the constitution's 40-line function rule on the Dart files this feature adds.

Article IV requires functions to stay under 40 lines. The Dart analyzer has no rule
for this — function-length checks live in `dart_code_metrics`, whose free tier was
retired in 2024 — so it is the one Article IV rule nothing off the shelf can enforce.
Hence this script. That is the documented gap Article VII asks for.

It lives in TranscriptBoss rather than in the fork on purpose: it enforces *our*
standard, not Omi's, and keeping it out of the fork keeps the upstream pull request
free of a check Omi never asked for (plan.md D-4).

Usage:
    python scripts/check_function_length.py omi-fork/app/lib/services/import
    python scripts/check_function_length.py --limit 40 <path> [<path> ...]

Exits 1 when any function exceeds the limit, naming each one.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LIMIT_LINES = 40

# A body must open on the signature line or shortly after it. Anything further away
# is a formatting we do not produce, and pretending to understand it would cost more
# false positives than the rule is worth.
MAX_LINES_FROM_SIGNATURE_TO_BRACE = 3


@dataclass(frozen=True, slots=True)
class Violation:
    """One function that ran past the limit."""

    path: Path
    line: int
    name: str
    length: int


def strip_noise(source: str) -> str:
    """Blank out comments and string contents, preserving line structure.

    Brace counting is only trustworthy once braces inside strings and comments are
    gone. Characters are replaced rather than removed so every reported line number
    still matches the file the user will open.
    """
    out: list[str] = []
    index = 0
    length = len(source)
    while index < length:
        char = source[index]
        pair = source[index : index + 2]

        if pair == "//":
            while index < length and source[index] != "\n":
                out.append(" ")
                index += 1
            continue

        if pair == "/*":
            while index < length and source[index : index + 2] != "*/":
                out.append("\n" if source[index] == "\n" else " ")
                index += 1
            out.append("  ")
            index += 2
            continue

        if char in "'\"":
            index = _skip_string(source, index, out)
            continue

        out.append(char)
        index += 1

    return "".join(out)


def _skip_string(source: str, start: int, out: list[str]) -> int:
    """Blank a string literal, returning the index just past it.

    Handles raw strings, escapes, and triple quotes. Interpolation is blanked along
    with everything else — a brace inside `${...}` is balanced anyway, so losing it
    cannot unbalance the count.
    """
    quote = source[start]
    is_triple = source[start : start + 3] == quote * 3
    terminator = quote * 3 if is_triple else quote
    is_raw = start > 0 and source[start - 1] == "r"

    out.append(" " * len(terminator))
    index = start + len(terminator)
    while index < len(source):
        if not is_raw and source[index] == "\\":
            out.append("  ")
            index += 2
            continue
        if source[index : index + len(terminator)] == terminator:
            out.append(" " * len(terminator))
            return index + len(terminator)
        out.append("\n" if source[index] == "\n" else " ")
        index += 1
    return index


def find_violations(path: Path, limit: int) -> list[Violation]:
    """Report every function in one file whose body exceeds the limit."""
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    clean_lines = strip_noise("\n".join(raw_lines)).splitlines()

    violations: list[Violation] = []
    line_number = 0
    while line_number < len(clean_lines):
        signature = _signature_at(clean_lines, line_number)
        if signature is None:
            line_number += 1
            continue

        brace_line, name = signature
        end_line = _matching_brace_line(clean_lines, brace_line)
        if end_line is None:
            line_number += 1
            continue

        body_length = end_line - line_number + 1
        if body_length > limit:
            violations.append(
                Violation(path=path, line=line_number + 1, name=name, length=body_length)
            )
        line_number = end_line + 1

    return violations


def _signature_at(lines: list[str], start: int) -> tuple[int, str] | None:
    """Recognise a function or method signature starting at `start`.

    Deliberately conservative: it looks for `name(...)` followed by an opening brace
    within a few lines. Anything it cannot confidently identify is skipped, because a
    gate that cries wolf gets switched off.
    """
    text = lines[start].strip()
    if not text or text.startswith(("import ", "export ", "part ", "library ", "@")):
        return None
    if "(" not in text:
        return None
    # Control flow reads like a call but is not a declaration.
    if text.split("(", maxsplit=1)[0].strip().split(" ")[-1] in {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "assert",
    }:
        return None

    name = text.split("(", maxsplit=1)[0].strip().split(" ")[-1].lstrip("_")
    if not name or not (name[0].isalpha() or name[0] == "_"):
        return None

    for offset in range(MAX_LINES_FROM_SIGNATURE_TO_BRACE + 1):
        if start + offset >= len(lines):
            return None
        candidate = lines[start + offset]
        if "=>" in candidate:
            return None  # An expression body cannot run long enough to matter.
        if "{" in candidate:
            return start + offset, name
        if ";" in candidate:
            return None  # An abstract declaration has no body to measure.
    return None


def _matching_brace_line(lines: list[str], brace_line: int) -> int | None:
    """Find the line closing the brace that opens on `brace_line`."""
    depth = 0
    for index in range(brace_line, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        if depth <= 0 and index > brace_line - 1 and "{" in lines[brace_line]:
            return index
    return None


def collect_dart_files(targets: list[str]) -> list[Path]:
    """Expand the given paths into the Dart files under them."""
    files: list[Path] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.dart")))
        elif path.suffix == ".dart":
            files.append(path)
    return [f for f in files if not f.name.endswith((".g.dart", ".gen.dart"))]


def main() -> int:
    """Check every named path and report what broke the rule."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="Dart files or directories to check")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT_LINES)
    arguments = parser.parse_args()

    files = collect_dart_files(arguments.targets)
    if not files:
        print("No Dart files found in the given paths — nothing to check.")
        return 0

    violations: list[Violation] = []
    for file in files:
        violations.extend(find_violations(file, arguments.limit))

    if not violations:
        print(f"Article IV: {len(files)} file(s) checked, every function within {arguments.limit} lines.")
        return 0

    print(f"Article IV: {len(violations)} function(s) over {arguments.limit} lines.\n")
    for violation in violations:
        print(f"  {violation.path}:{violation.line}  {violation.name}() is {violation.length} lines")
    print("\nSplit them, or state at the function why it cannot be split.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
