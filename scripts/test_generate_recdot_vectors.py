"""Tests for the RecDot golden-vector generator.

The Dart codec in the Omi fork is checked against JSON fixtures produced here, not against
itself. These tests make sure the fixtures are worth trusting: the generator is deterministic
and every framing fixture decodes through the Python reference codec to the value it claims.

Run with: python -m pytest scripts/test_generate_recdot_vectors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))
# The bit-exact reference package lives in a local tools dir, not site-packages (task T005).
sys.path.insert(0, str(SCRIPTS_DIR / ".tools" / "pyg722"))

from generate_recdot_vectors import (  # noqa: E402
    RECDOT_FIXTURE_NAMES,
    write_recdot_vectors,
)
from recdot_wire import decode_frame  # noqa: E402


def _load(directory: Path, name: str) -> dict:
    return json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))


# --- RecDot framing fixtures ---------------------------------------------------


def test_recdot_generator_writes_every_named_fixture(tmp_path: Path) -> None:
    write_recdot_vectors(tmp_path)
    for name in RECDOT_FIXTURE_NAMES:
        assert (tmp_path / f"{name}.json").exists(), name


def test_recdot_generator_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_recdot_vectors(first)
    write_recdot_vectors(second)
    for name in RECDOT_FIXTURE_NAMES:
        assert (first / f"{name}.json").read_bytes() == (second / f"{name}.json").read_bytes(), name


def test_framing_fixtures_decode_to_their_claimed_frames(tmp_path: Path) -> None:
    write_recdot_vectors(tmp_path)
    for case in _load(tmp_path, "framing")["cases"]:
        if "error" in case["expected"]:
            continue
        decoded, consumed = decode_frame(bytes.fromhex(case["input_hex"]))
        assert decoded.command == case["expected"]["command"], case["name"]
        assert decoded.payload.hex() == case["expected"]["payload_hex"], case["name"]
        assert consumed == len(bytes.fromhex(case["input_hex"])), case["name"]


def test_framer_split_fixture_holds_three_frames_and_the_documented_wire_bytes(tmp_path: Path) -> None:
    write_recdot_vectors(tmp_path)
    fixture = _load(tmp_path, "framer_splits")
    stream = bytes.fromhex(fixture["stream_hex"])
    assert stream.startswith(bytes.fromhex("5508510100000000"))
    assert len(fixture["expected_frames"]) == 3
    remaining = stream
    for expected in fixture["expected_frames"]:
        decoded, consumed = decode_frame(remaining)
        assert decoded.command == expected["command"]
        assert decoded.payload.hex() == expected["payload_hex"]
        remaining = remaining[consumed:]
    assert remaining == b""


def test_advertisement_fixture_carries_the_real_iphone_capture(tmp_path: Path) -> None:
    write_recdot_vectors(tmp_path)
    cases = {case["name"]: case for case in _load(tmp_path, "advertisement")["cases"]}
    real = cases["real_recdot_iphone_2026_09_06"]
    assert real["input_hex"] == "080808 00ffff304120ff36e92a6420ff36e908e000".replace(" ", "")
    assert real["expected"]["product_id"] == 8
    assert real["expected"]["left_mac"] == "20:FF:36:E9:2A:64"
