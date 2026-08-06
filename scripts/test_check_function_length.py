"""Tests for the Article IV function-length gate.

This checker decides whether the constitution's 40-line rule is enforced across the
whole feature, so a bug in it is silent: functions sail past the limit and nobody
finds out. It was originally verified only by hand against Omi's `capture_controller.dart`,
which proved it worked on one file and nothing more.

The cases below are the ways a brace counter gets fooled — braces inside strings,
braces inside comments, control flow that reads like a declaration, expression bodies
that have no braces at all — plus the exact boundary, because an off-by-one in a
limit check is both easy to write and impossible to notice.

Run with: python -m pytest scripts/test_check_function_length.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from check_function_length import (  # noqa: E402
    collect_dart_files,
    find_violations,
    strip_noise,
)

DEFAULT_LIMIT = 40


def write_dart(tmp_path: Path, body: str, name: str = "sample.dart") -> Path:
    """Write a Dart source file for the checker to read."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def build_function(line_count: int, name: str = "doWork") -> str:
    """Build a function whose body spans exactly `line_count` lines.

    The signature line carries the opening brace and the last line carries the closing
    one, so the span the checker measures is exactly `line_count`.
    """
    filler = "\n".join(f"  var step{i} = {i};" for i in range(line_count - 2))
    return f"void {name}() {{\n{filler}\n}}\n"


def test_a_short_function_passes(tmp_path: Path) -> None:
    """The ordinary case: nothing to report."""
    path = write_dart(tmp_path, build_function(10))

    assert find_violations(path, DEFAULT_LIMIT) == []


def test_a_long_function_is_reported_with_its_length(tmp_path: Path) -> None:
    """The length must be right, not just the fact of a violation — it is what the
    author uses to judge how much splitting is needed."""
    path = write_dart(tmp_path, build_function(60))

    violations = find_violations(path, DEFAULT_LIMIT)

    assert len(violations) == 1
    assert violations[0].name == "doWork"
    assert violations[0].length == 60
    assert violations[0].line == 1


def test_the_boundary_is_exact(tmp_path: Path) -> None:
    """Exactly at the limit passes; one line over does not.

    An off-by-one here is easy to write and impossible to spot in normal use.
    """
    at_limit = write_dart(tmp_path, build_function(DEFAULT_LIMIT), "at_limit.dart")
    over_limit = write_dart(tmp_path, build_function(DEFAULT_LIMIT + 1), "over_limit.dart")

    assert find_violations(at_limit, DEFAULT_LIMIT) == []
    assert len(find_violations(over_limit, DEFAULT_LIMIT)) == 1


def test_braces_inside_strings_do_not_confuse_the_count(tmp_path: Path) -> None:
    """A brace in a string literal must not open or close a body.

    Dart interpolation makes this common: `'${value}'` appears constantly, and a naive
    counter would treat every one as a nested scope and lose track entirely.
    """
    source = (
        "void shortOne() {\n"
        "  final label = 'a { brace } in a string';\n"
        "  final other = \"another } here {\";\n"
        "  print('$label $other');\n"
        "}\n"
    )
    path = write_dart(tmp_path, source)

    assert find_violations(path, DEFAULT_LIMIT) == []


def test_braces_inside_comments_do_not_confuse_the_count(tmp_path: Path) -> None:
    """A brace in a comment must be invisible to the counter."""
    source = (
        "void shortOne() {\n"
        "  // an unbalanced { in a line comment\n"
        "  /* and a } in a block comment */\n"
        "  return;\n"
        "}\n"
    )
    path = write_dart(tmp_path, source)

    assert find_violations(path, DEFAULT_LIMIT) == []


def test_strip_noise_preserves_line_numbers() -> None:
    """Reported line numbers must match the file the user will open.

    Blanking has to replace comment and string content in place rather than removing
    it, or every violation after the first comment points at the wrong line.
    """
    source = "one\n/* two\nthree */\nfour\n"

    assert len(strip_noise(source).splitlines()) == len(source.splitlines())


def test_control_flow_is_not_mistaken_for_a_declaration(tmp_path: Path) -> None:
    """`if (...) {` reads exactly like a signature and is not one.

    Counting it would attribute a long function's body to its first conditional and
    report a violation against something that does not exist.
    """
    inner = "\n".join(f"    var step{i} = {i};" for i in range(50))
    source = f"void shortOne() {{\n  if (ready) {{\n{inner}\n  }}\n}}\n"
    path = write_dart(tmp_path, source)

    violations = find_violations(path, DEFAULT_LIMIT)

    # The enclosing function is genuinely too long and should be the one reported.
    assert [v.name for v in violations] == ["shortOne"]


def test_expression_bodied_functions_are_skipped(tmp_path: Path) -> None:
    """A `=>` body has no braces and cannot run long enough to matter."""
    source = "int total() => 1 + 2 + 3;\n"
    path = write_dart(tmp_path, source)

    assert find_violations(path, DEFAULT_LIMIT) == []


def test_abstract_declarations_are_skipped(tmp_path: Path) -> None:
    """A declaration with no body has nothing to measure."""
    source = "abstract class Thing {\n  void doWork();\n}\n"
    path = write_dart(tmp_path, source)

    assert find_violations(path, DEFAULT_LIMIT) == []


def test_generated_files_are_not_checked(tmp_path: Path) -> None:
    """Generated code is not ours to split, and Omi forbids editing it by hand."""
    write_dart(tmp_path, build_function(80), "thing.g.dart")
    write_dart(tmp_path, build_function(80), "thing.gen.dart")
    write_dart(tmp_path, build_function(80), "thing.dart")

    collected = collect_dart_files([str(tmp_path)])

    assert [path.name for path in collected] == ["thing.dart"]


def test_several_long_functions_are_all_reported(tmp_path: Path) -> None:
    """Reporting only the first would hide the rest behind repeated runs."""
    source = build_function(50, "first") + build_function(50, "second")
    path = write_dart(tmp_path, source)

    violations = find_violations(path, DEFAULT_LIMIT)

    assert sorted(v.name for v in violations) == ["first", "second"]


def test_an_empty_file_is_not_a_violation(tmp_path: Path) -> None:
    """A placeholder or barrel file has nothing to report."""
    path = write_dart(tmp_path, "")

    assert find_violations(path, DEFAULT_LIMIT) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
