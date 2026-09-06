"""Generate golden JSON vectors for the Dart STAROT codec from the Python reference codec.

The Dart connector in the Omi fork must produce and parse exactly the bytes documented in
specs/002-viaim-recdot-device/protocol.md. Rather than let the Dart tests re-derive their
expectations from the Dart code (which would let a shared misunderstanding pass), every
expectation is generated here from scripts/recdot_wire.py, the independent implementation,
and committed as fixtures the Dart tests load verbatim.

Usage:
    python scripts/generate_recdot_vectors.py [--out omi-recdot/app/test/fixtures/recdot_golden]

The output is deterministic so re-running it never produces a spurious diff.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from recdot_wire import (  # noqa: E402
    AudioChannel,
    Frame,
    TlvAttribute,
    decode_advertisement,
    encode_frame,
    encode_get_record_request,
    encode_tlv_group,
    split_call_audio,
    split_flash_chunk,
)

DEFAULT_OUTPUT_DIR = Path("omi-recdot/app/test/fixtures/recdot_golden")
RECDOT_FIXTURE_NAMES = (
    "framing",
    "ack",
    "tlv",
    "call_audio",
    "flash_chunk",
    "get_record",
    "advertisement",
    "framer_splits",
)

CHECK_BOND_CODE = 0x5101
GET_SERIAL = 0x550B
GET_VERSION = 0x5500
GET_BATTERY = 0x5505
DIALOG_AUDIO_DATA = 0x5007
OFFLINE_UPLOAD = 0x5A3A

# The advertisement nRF Connect captured from the user's RecDot on 2026-09-06.
REAL_IPHONE_ADVERTISEMENT_HEX = "080808" + "00ffff304120ff36e92a6420ff36e908e000"


def _hex(data: bytes) -> str:
    return data.hex()


def _framing_cases() -> list[dict]:
    """Frames whose exact bytes the protocol notes state, plus the refusal edges."""
    version_payload = encode_tlv_group([TlvAttribute(1, bytes([0x07]))])
    long_payload = bytes(range(256)) + bytes(range(44))
    cases = [
        _frame_case("bond_check_code_zero", CHECK_BOND_CODE, bytes(4)),
        _frame_case("get_serial", GET_SERIAL, b""),
        _frame_case("get_version", GET_VERSION, version_payload),
        _frame_case("get_battery", GET_BATTERY, b""),
        _frame_case("long_frame_uses_0x56", DIALOG_AUDIO_DATA, long_payload),
        _frame_case("largest_short_frame_255", DIALOG_AUDIO_DATA, bytes(251)),
        _frame_case("smallest_long_frame_257", DIALOG_AUDIO_DATA, bytes(253)),
    ]
    cases.append({"name": "exactly_256_refused", "payload_len": 252, "expected": {"error": "undecodable_length"}})
    cases.append({"name": "over_508_refused", "payload_len": 509, "expected": {"error": "payload_too_long"}})
    return cases


def _frame_case(name: str, command: int, payload: bytes) -> dict:
    encoded = encode_frame(Frame(command, payload))
    return {
        "name": name,
        "input_hex": _hex(encoded),
        "expected": {"command": command, "payload_hex": _hex(payload), "total_length": len(encoded)},
    }


def _ack_cases() -> list[dict]:
    """Acknowledgement frames: status byte first, data after."""
    ok_ack = bytes.fromhex("55 07 D1 01 00 02 03".replace(" ", ""))
    failed_ack = bytes.fromhex("55 05 D1 01 06".replace(" ", ""))
    plain = encode_frame(Frame(GET_SERIAL, b""))
    return [
        {"name": "ack_status_ok_with_data", "input_hex": _hex(ok_ack),
         "expected": {"is_ack": True, "opcode": CHECK_BOND_CODE, "status": 0, "data_hex": "0203"}},
        {"name": "ack_status_incorrect_state", "input_hex": _hex(failed_ack),
         "expected": {"is_ack": True, "opcode": CHECK_BOND_CODE, "status": 6, "data_hex": ""}},
        {"name": "plain_command_has_no_status", "input_hex": _hex(plain),
         "expected": {"is_ack": False, "opcode": GET_SERIAL, "status": None, "data_hex": ""}},
    ]


def _tlv_cases() -> list[dict]:
    """Attribute groups: the length counts the attribute byte but not itself."""
    groups = {
        "single_attr_one_byte": [TlvAttribute(2, bytes([0x01]))],
        "empty_value": [TlvAttribute(0xFF, b"")],
        "three_attrs_mixed": [TlvAttribute(1, bytes([1])), TlvAttribute(0xFF, b""), TlvAttribute(3, b"abc")],
        "serial_reply_shape": [TlvAttribute(1, b"A92XXXXXXXXXXX"), TlvAttribute(2, b"A92YYYYYYYYYYY")],
    }
    cases = []
    for name, attributes in groups.items():
        encoded = encode_tlv_group(attributes)
        cases.append({
            "name": name,
            "input_hex": _hex(encoded),
            "expected": {"attributes": [{"attribute": a.attribute, "value_hex": _hex(a.value)} for a in attributes]},
        })
    cases.append({"name": "truncated_group_refused", "input_hex": "050102", "expected": {"error": "truncated"}})
    return cases


def _call_audio_cases() -> list[dict]:
    """0x5007 payloads: channel bitmask then equal halves when both sides are present."""
    speaker = bytes(range(40))
    mic = bytes(range(40, 80))
    both = bytes([AudioChannel.SPEAKER | AudioChannel.MIC]) + speaker + mic
    only_speaker = bytes([AudioChannel.SPEAKER]) + speaker
    only_mic_high_nibble = bytes([0xF0 | AudioChannel.MIC]) + mic
    cases = []
    for name, payload in (("both_channels", both), ("speaker_only", only_speaker), ("mic_only_upper_nibble_ignored", only_mic_high_nibble)):
        split = split_call_audio(payload)
        cases.append({"name": name, "input_hex": _hex(payload),
                      "expected": {"speaker_hex": _hex(split.speaker), "mic_hex": _hex(split.mic)}})
    cases.append({"name": "odd_two_channel_refused",
                  "input_hex": _hex(bytes([AudioChannel.SPEAKER | AudioChannel.MIC]) + bytes(41)),
                  "expected": {"error": "odd_length"}})
    return cases


def _flash_chunk_cases() -> list[dict]:
    """0x5A3A chunks: 3-byte big-endian offset, channel tag, audio."""
    single = bytes([0x01, 0x02, 0x03, 3]) + bytes(range(40))
    frames = [bytes([n] * 40) for n in (1, 2, 3, 4)]
    two_way = bytes([0, 0, 0, 4]) + b"".join(frames)
    end = bytes([0, 0x10, 0x00, 255])
    cases = []
    for name, payload in (("single_stream_channel_3", single), ("two_way_channel_4_alternates", two_way), ("end_of_file_255", end)):
        chunk = split_flash_chunk(payload)
        cases.append({"name": name, "input_hex": _hex(payload),
                      "expected": {"offset": chunk.offset, "speaker_hex": _hex(chunk.speaker),
                                   "mic_hex": _hex(chunk.mic), "is_end_of_file": chunk.is_end_of_file}})
    cases.append({"name": "unknown_channel_refused", "input_hex": _hex(bytes([0, 0, 0, 7]) + bytes(40)),
                  "expected": {"error": "unknown_channel"}})
    return cases


def _get_record_cases() -> list[dict]:
    """0x5A39 requests: little-endian integers, and the single-attribute cancel."""
    start = encode_get_record_request(side=1, index=0x0102, offset=0x0A0B0C0D, length=0x10)
    with_password = encode_get_record_request(side=0, index=7, offset=0, length=64000, password="1234")
    cancel = encode_get_record_request(is_cancel=True)
    return [
        {"name": "start_download", "input": {"side": 1, "index": 258, "offset": 168496141, "length": 16},
         "expected": {"payload_hex": _hex(start)}},
        {"name": "start_with_password", "input": {"side": 0, "index": 7, "offset": 0, "length": 64000, "password": "1234"},
         "expected": {"payload_hex": _hex(with_password)}},
        {"name": "cancel", "input": {"cancel": True}, "expected": {"payload_hex": _hex(cancel)}},
    ]


def _advertisement_cases() -> list[dict]:
    """The real capture plus synthetic variants for the prefix-letter rule."""
    real = bytes.fromhex(REAL_IPHONE_ADVERTISEMENT_HEX)
    open_note = bytes([0x08, ord("E"), 0]) + real[3:]
    charging = bytes([0x09, 0, 0, 0x80 | 55, 60, 0xFF]) + real[6:]
    cases = []
    for name, blob in (("real_recdot_iphone_2026_09_06", real), ("open_note_prefix_letter_e", open_note), ("recdot2_left_charging", charging)):
        advert = decode_advertisement(blob)
        cases.append({"name": name, "input_hex": _hex(blob), "expected": {
            "product_id": advert.product_id,
            "left_battery_percent": advert.left_battery_percent, "is_left_charging": advert.is_left_charging,
            "right_battery_percent": advert.right_battery_percent, "is_right_charging": advert.is_right_charging,
            "case_battery_percent": advert.case_battery_percent, "is_case_charging": advert.is_case_charging,
            "left_mac": advert.left_mac, "right_mac": advert.right_mac, "feature": advert.feature}})
    cases.append({"name": "too_short_refused", "input_hex": _hex(bytes(20)), "expected": {"error": "too_short"}})
    return cases


def _framer_splits_fixture() -> dict:
    """A three-frame stream the Dart framer must reassemble however it is chunked."""
    frames = [
        Frame(CHECK_BOND_CODE, bytes(4)),
        Frame(DIALOG_AUDIO_DATA, bytes([AudioChannel.SPEAKER | AudioChannel.MIC]) + bytes(range(256)) + bytes(range(44))),
        Frame(GET_SERIAL, b""),
    ]
    stream = b"".join(encode_frame(frame) for frame in frames)
    return {
        "stream_hex": _hex(stream),
        "garbage_prefix_hex": "0011ff",
        "expected_frames": [{"command": f.command, "payload_hex": _hex(f.payload)} for f in frames],
        "note": "Feed the stream one byte at a time, in 7-byte chunks, and all at once; expect the same frames. With the garbage prefix, the framer must resync on the first sync byte.",
    }


def build_recdot_vectors() -> dict[str, dict]:
    """Every fixture file's content, keyed by fixture name."""
    return {
        "framing": {"cases": _framing_cases()},
        "ack": {"cases": _ack_cases()},
        "tlv": {"cases": _tlv_cases()},
        "call_audio": {"cases": _call_audio_cases()},
        "flash_chunk": {"cases": _flash_chunk_cases()},
        "get_record": {"cases": _get_record_cases()},
        "advertisement": {"cases": _advertisement_cases()},
        "framer_splits": _framer_splits_fixture(),
    }


def write_recdot_vectors(output_dir: Path) -> None:
    """Write every fixture as pretty, key-sorted JSON so re-runs are byte-identical."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in build_recdot_vectors().items():
        payload = {"generator": "scripts/generate_recdot_vectors.py", "source": "scripts/recdot_wire.py", **content}
        (output_dir / f"{name}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    arguments = parser.parse_args()
    write_recdot_vectors(arguments.out)
    print(f"wrote {len(RECDOT_FIXTURE_NAMES)} fixtures to {arguments.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
