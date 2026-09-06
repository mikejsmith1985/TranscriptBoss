"""Generate bit-exact G.722 golden vectors for the Dart decoder in the Omi fork.

The RecDot sends call audio as G.722. Omi has no G.722 decoder, so one is being ported to Dart
from the public-domain reference. A port is only trustworthy if it is bit-exact, and the way to
know is to compare it against the reference implementation on known inputs. This script uses
the `G722` Python package (a build of that same reference, ITU-test-vector clean) to encode
synthetic signals and record exactly what the decoder must produce, in both sample-rate modes
the buds use.

Usage:
    python scripts/generate_g722_vectors.py [--out omi-recdot/app/test/fixtures/g722_golden]

Requires the package installed into scripts/.tools/pyg722 (task T005).
"""

from __future__ import annotations

import argparse
import array
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / ".tools" / "pyg722"))

import G722  # noqa: E402

DEFAULT_OUTPUT_DIR = Path("omi-recdot/app/test/fixtures/g722_golden")
G722_FIXTURE_NAMES = ("mode_16k", "mode_8k", "chunked")

BITRATE = 64000
WIDEBAND_RATE = 16000
NARROWBAND_RATE = 8000
TONE_HZ = 1000
TONE_AMPLITUDE = 8000
NOISE_AMPLITUDE = 3000
SAMPLES_PER_SIGNAL = 1600
FLASH_FRAME_BYTES = 40

# A tiny linear congruential generator so "noise" is the same on every machine.
LCG_MULTIPLIER = 1103515245
LCG_INCREMENT = 12345
LCG_MODULUS = 2**31


def _silence(sample_count: int) -> array.array:
    return array.array("h", [0] * sample_count)


def _tone(sample_count: int, sample_rate: int) -> array.array:
    return array.array("h", [int(TONE_AMPLITUDE * math.sin(2 * math.pi * TONE_HZ * n / sample_rate)) for n in range(sample_count)])


def _deterministic_noise(sample_count: int) -> array.array:
    state = 20260906
    samples = array.array("h")
    for _ in range(sample_count):
        state = (LCG_MULTIPLIER * state + LCG_INCREMENT) % LCG_MODULUS
        samples.append(int((state / LCG_MODULUS) * 2 * NOISE_AMPLITUDE - NOISE_AMPLITUDE))
    return samples


def _encode(pcm: array.array, sample_rate: int) -> bytes:
    return bytes(G722.G722(sample_rate, BITRATE).encode(pcm))


def _decode(g722_bytes: bytes, sample_rate: int) -> bytes:
    decoded = G722.G722(sample_rate, BITRATE).decode(g722_bytes)
    return array.array("h", decoded).tobytes()


def _mode_cases(sample_rate: int) -> list[dict]:
    """Silence, a tone and noise, encoded then decoded by the reference in one mode."""
    signals = {
        "silence": _silence(SAMPLES_PER_SIGNAL),
        "tone_1khz": _tone(SAMPLES_PER_SIGNAL, sample_rate),
        "noise": _deterministic_noise(SAMPLES_PER_SIGNAL),
    }
    cases = []
    for name, pcm in signals.items():
        encoded = _encode(pcm, sample_rate)
        cases.append({
            "name": name,
            "input_hex": encoded.hex(),
            "expected": {"sample_rate": sample_rate, "pcm16_hex": _decode(encoded, sample_rate).hex()},
        })
    return cases


def _chunked_fixture() -> dict:
    """One wideband stream whose 40-byte chunks must decode, in sequence, to the whole-stream PCM."""
    pcm = _tone(SAMPLES_PER_SIGNAL, WIDEBAND_RATE)
    encoded = _encode(pcm, WIDEBAND_RATE)
    usable = encoded[: len(encoded) - len(encoded) % FLASH_FRAME_BYTES]
    return {
        "sample_rate": WIDEBAND_RATE,
        "chunk_bytes": FLASH_FRAME_BYTES,
        "input_hex": usable.hex(),
        "expected": {"pcm16_hex": _decode(usable, WIDEBAND_RATE).hex()},
        "note": "Decode chunk by chunk with one decoder instance and concatenate; must equal pcm16_hex. Then reset() and decode the first chunk again; must equal the first chunk's share of pcm16_hex.",
    }


def build_g722_vectors() -> dict[str, dict]:
    """Every fixture file's content, keyed by fixture name."""
    return {
        "mode_16k": {"cases": _mode_cases(WIDEBAND_RATE)},
        "mode_8k": {"cases": _mode_cases(NARROWBAND_RATE)},
        "chunked": _chunked_fixture(),
    }


def write_g722_vectors(output_dir: Path) -> None:
    """Write every fixture as pretty, key-sorted JSON so re-runs are byte-identical."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in build_g722_vectors().items():
        payload = {"generator": "scripts/generate_g722_vectors.py", "source": "G722 PyPI package (ITU reference build)", **content}
        (output_dir / f"{name}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    arguments = parser.parse_args()
    write_g722_vectors(arguments.out)
    print(f"wrote {len(G722_FIXTURE_NAMES)} fixtures to {arguments.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
