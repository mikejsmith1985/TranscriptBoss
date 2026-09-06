"""Tests for the G.722 golden-vector generator.

The Dart G.722 decoder in the Omi fork must be bit-exact with the ITU reference. These tests
make sure the fixtures that prove it are deterministic, have the sample counts each mode
implies, carry the chunked stream the decoder must match frame by frame, and idle at the
codec's real quantiser noise rather than a made-up zero.

Run with: python -m pytest scripts/test_generate_g722_vectors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))
# The bit-exact reference package lives in a local tools dir, not site-packages (task T005).
sys.path.insert(0, str(SCRIPTS_DIR / ".tools" / "pyg722"))


pytest.importorskip("G722", reason="bit-exact G.722 package not installed (task T005)")

from generate_g722_vectors import (  # noqa: E402
    G722_FIXTURE_NAMES,
    write_g722_vectors,
)


IDLE_NOISE_LSB_LIMIT = 4


def _load(directory: Path, name: str) -> dict:
    return json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))


# --- G.722 fixtures ------------------------------------------------------------


def test_g722_generator_writes_every_named_fixture(tmp_path: Path) -> None:
    write_g722_vectors(tmp_path)
    for name in G722_FIXTURE_NAMES:
        assert (tmp_path / f"{name}.json").exists(), name


def test_g722_generator_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_g722_vectors(first)
    write_g722_vectors(second)
    for name in G722_FIXTURE_NAMES:
        assert (first / f"{name}.json").read_bytes() == (second / f"{name}.json").read_bytes(), name


def test_g722_16k_vectors_have_two_samples_per_input_byte(tmp_path: Path) -> None:
    write_g722_vectors(tmp_path)
    for case in _load(tmp_path, "mode_16k")["cases"]:
        g722_bytes = len(bytes.fromhex(case["input_hex"]))
        pcm_bytes = len(bytes.fromhex(case["expected"]["pcm16_hex"]))
        assert pcm_bytes == g722_bytes * 2 * 2, case["name"]


def test_g722_8k_vectors_have_one_sample_per_input_byte(tmp_path: Path) -> None:
    write_g722_vectors(tmp_path)
    for case in _load(tmp_path, "mode_8k")["cases"]:
        g722_bytes = len(bytes.fromhex(case["input_hex"]))
        pcm_bytes = len(bytes.fromhex(case["expected"]["pcm16_hex"]))
        assert pcm_bytes == g722_bytes * 2, case["name"]


def test_g722_chunked_vector_marks_frame_boundaries_that_decode_identically(tmp_path: Path) -> None:
    write_g722_vectors(tmp_path)
    fixture = _load(tmp_path, "chunked")
    assert fixture["chunk_bytes"] == 40
    assert len(bytes.fromhex(fixture["input_hex"])) % fixture["chunk_bytes"] == 0
    assert fixture["expected"]["pcm16_hex"]  # whole-stream decode the Dart decoder must match chunk by chunk


def test_g722_silence_decodes_to_near_silence(tmp_path: Path) -> None:
    write_g722_vectors(tmp_path)
    cases = {case["name"]: case for case in _load(tmp_path, "mode_16k")["cases"]}
    pcm = bytes.fromhex(cases["silence"]["expected"]["pcm16_hex"])
    samples = [int.from_bytes(pcm[i : i + 2], "little", signed=True) for i in range(0, len(pcm), 2)]
    # Sub-band ADPCM never settles to exact zero: the reference idles at up to 3 LSB of
    # quantiser noise on a silent input. Anything louder means the vectors are wrong.
    assert max(abs(sample) for sample in samples) <= IDLE_NOISE_LSB_LIMIT
