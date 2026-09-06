"""Tests for the viaim RecDot wire-protocol reference codec.

`specs/002-viaim-recdot-device/protocol.md` was recovered by reading the vendor's
Android app. A document can be wrong in ways nobody notices until a connector is
built against it on a phone we cannot debug. These tests pin the byte layouts the
document claims — the v2 framing, the acknowledgement convention, the TLV attribute
groups, the two-channel call-audio split, the FlashRecord chunk header, the download
request, and the BLE advertisement — so that the reference codec, the document, and
later the Dart connector all agree on the same bytes.

The exact wire examples come straight from the protocol notes (§4), so a mismatch
here means the notes are wrong, not just the code.

Run with: python -m pytest scripts/test_recdot_wire.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from recdot_wire import (  # noqa: E402
    ACK_FLAG,
    AudioChannel,
    BleAdvertisement,
    CallAudioPacket,
    FlashChunk,
    Frame,
    TlvAttribute,
    decode_advertisement,
    decode_frame,
    decode_tlv_group,
    encode_frame,
    encode_get_record_request,
    encode_tlv_group,
    split_call_audio,
    split_flash_chunk,
)

CHECK_BOND_CODE = 0x5101
GET_SERIAL = 0x550B
GET_VERSION = 0x5500
DIALOG_AUDIO_DATA = 0x5007
GET_RECORD = 0x5A39


# --- v2 framing -------------------------------------------------------------


def test_bond_code_check_matches_documented_wire_bytes() -> None:
    frame = encode_frame(Frame(command=CHECK_BOND_CODE, payload=bytes(4)))
    assert frame == bytes.fromhex("55 08 51 01 00 00 00 00")


def test_get_serial_matches_documented_wire_bytes() -> None:
    assert encode_frame(Frame(command=GET_SERIAL, payload=b"")) == bytes.fromhex("55 04 55 0B")


def test_get_version_matches_documented_wire_bytes() -> None:
    payload = encode_tlv_group([TlvAttribute(attribute=1, value=bytes([0x07]))])
    frame = encode_frame(Frame(command=GET_VERSION, payload=payload))
    assert frame == bytes.fromhex("55 07 55 00 02 01 07")


def test_long_frame_uses_0x56_sync_and_offset_length() -> None:
    payload = bytes(300)
    frame = encode_frame(Frame(command=DIALOG_AUDIO_DATA, payload=payload))
    assert frame[0] == 0x56
    assert frame[1] == (len(payload) + 4) - 256
    assert decode_frame(frame) == (Frame(command=DIALOG_AUDIO_DATA, payload=payload), len(frame))


def test_exactly_256_byte_frame_is_refused_because_the_vendor_framer_cannot_resync() -> None:
    with pytest.raises(ValueError):
        encode_frame(Frame(command=DIALOG_AUDIO_DATA, payload=bytes(252)))


def test_payload_over_508_bytes_is_refused() -> None:
    with pytest.raises(ValueError):
        encode_frame(Frame(command=DIALOG_AUDIO_DATA, payload=bytes(509)))


def test_decode_round_trips_short_frame_and_reports_consumed_length() -> None:
    frame = bytes.fromhex("55 08 51 01 00 00 00 00") + b"\xaa\xbb"
    decoded, consumed = decode_frame(frame)
    assert decoded == Frame(command=CHECK_BOND_CODE, payload=bytes(4))
    assert consumed == 8


def test_decode_returns_nothing_for_an_incomplete_frame() -> None:
    assert decode_frame(bytes.fromhex("55 08 51 01 00")) is None


def test_decode_rejects_unknown_sync_byte() -> None:
    with pytest.raises(ValueError):
        decode_frame(bytes.fromhex("99 04 55 0B"))


# --- acknowledgements -------------------------------------------------------


def test_ack_frame_carries_status_byte_then_data() -> None:
    frame = bytes.fromhex("55 07 D1 01 00 02 03")
    decoded, _ = decode_frame(frame)
    assert decoded.is_ack
    assert decoded.command == CHECK_BOND_CODE | ACK_FLAG
    assert decoded.opcode == CHECK_BOND_CODE
    assert decoded.ack_status == 0
    assert decoded.ack_data == bytes([0x02, 0x03])


def test_non_ack_frame_has_no_status() -> None:
    decoded, _ = decode_frame(bytes.fromhex("55 04 55 0B"))
    assert not decoded.is_ack
    assert decoded.ack_status is None


# --- TLV attribute groups ---------------------------------------------------


def test_tlv_length_counts_attribute_byte_but_not_itself() -> None:
    encoded = encode_tlv_group([TlvAttribute(attribute=2, value=bytes([0x01]))])
    assert encoded == bytes([0x02, 0x02, 0x01])


def test_tlv_group_round_trips_several_attributes_including_empty_values() -> None:
    attributes = [
        TlvAttribute(attribute=1, value=bytes([0x01])),
        TlvAttribute(attribute=0xFF, value=b""),
        TlvAttribute(attribute=3, value=b"abc"),
    ]
    assert decode_tlv_group(encode_tlv_group(attributes)) == attributes


def test_tlv_decode_refuses_a_truncated_group() -> None:
    with pytest.raises(ValueError):
        decode_tlv_group(bytes([0x05, 0x01, 0x02]))


# --- call audio (0x5007) ----------------------------------------------------


def test_call_audio_with_both_channels_splits_payload_in_equal_halves() -> None:
    speaker = bytes(range(40))
    mic = bytes(range(40, 80))
    payload = bytes([AudioChannel.SPEAKER | AudioChannel.MIC]) + speaker + mic
    assert split_call_audio(payload) == CallAudioPacket(speaker=speaker, mic=mic)


def test_call_audio_with_only_speaker_channel_keeps_whole_payload() -> None:
    speaker = bytes(range(40))
    payload = bytes([AudioChannel.SPEAKER]) + speaker
    assert split_call_audio(payload) == CallAudioPacket(speaker=speaker, mic=b"")


def test_call_audio_ignores_upper_nibble_of_channel_byte() -> None:
    payload = bytes([0xF0 | AudioChannel.MIC]) + bytes(40)
    assert split_call_audio(payload) == CallAudioPacket(speaker=b"", mic=bytes(40))


def test_call_audio_with_odd_length_and_two_channels_is_refused() -> None:
    with pytest.raises(ValueError):
        split_call_audio(bytes([AudioChannel.SPEAKER | AudioChannel.MIC]) + bytes(41))


# --- FlashRecord chunks (0x5A3A) --------------------------------------------


def test_flash_chunk_offset_is_three_byte_big_endian() -> None:
    chunk = split_flash_chunk(bytes([0x01, 0x02, 0x03, 3]) + bytes(40))
    assert chunk == FlashChunk(offset=0x010203, speaker=bytes(40), mic=b"", is_end_of_file=False)


def test_flash_chunk_channel_4_alternates_40_byte_frames_speaker_then_mic() -> None:
    first = bytes([1] * 40)
    second = bytes([2] * 40)
    third = bytes([3] * 40)
    fourth = bytes([4] * 40)
    chunk = split_flash_chunk(bytes([0, 0, 0, 4]) + first + second + third + fourth)
    assert chunk.speaker == first + third
    assert chunk.mic == second + fourth


def test_flash_chunk_channel_255_is_end_of_file() -> None:
    chunk = split_flash_chunk(bytes([0, 0x10, 0x00, 255]))
    assert chunk.is_end_of_file
    assert chunk.offset == 0x1000


def test_flash_chunk_unknown_channel_is_refused() -> None:
    with pytest.raises(ValueError):
        split_flash_chunk(bytes([0, 0, 0, 7]) + bytes(40))


# --- FlashRecord download request (0x5A39) ----------------------------------


def test_get_record_request_writes_integers_little_endian() -> None:
    payload = encode_get_record_request(side=1, index=0x0102, offset=0x0A0B0C0D, length=0x10)
    expected = (
        bytes([0x02, 0x01, 0x01])
        + bytes([0x05, 0x02, 0x02, 0x01, 0x00, 0x00])
        + bytes([0x05, 0x03, 0x0D, 0x0C, 0x0B, 0x0A])
        + bytes([0x05, 0x04, 0x10, 0x00, 0x00, 0x00])
    )
    assert payload == expected


def test_get_record_cancel_is_a_single_attribute_255() -> None:
    assert encode_get_record_request(is_cancel=True) == bytes([0x01, 0xFF])


# --- BLE advertisement ------------------------------------------------------


def _advertisement(product_id: int, prefix_letter: int = 0) -> bytes:
    left_mac = bytes.fromhex("20FF000000A1")
    right_mac = bytes.fromhex("20FF000000B2")
    battery = bytes([0x80 | 55, 60, 0xFF])
    return (
        bytes([product_id, prefix_letter, 0])
        + battery
        + bytes([0x12, 0x34])
        + left_mac
        + right_mac
        + bytes([0])
    )


def test_advertisement_identifies_recdot_and_reads_battery_and_macs() -> None:
    advert = decode_advertisement(_advertisement(0x08))
    assert advert == BleAdvertisement(
        product_id=8,
        left_battery_percent=55,
        is_left_charging=True,
        right_battery_percent=60,
        is_right_charging=False,
        case_battery_percent=None,
        is_case_charging=False,
        left_mac="20:FF:00:00:00:A1",
        right_mac="20:FF:00:00:00:B2",
        feature=0,
    )


def test_advertisement_captured_from_a_real_recdot_on_iphone_decodes_as_product_8() -> None:
    # Golden bytes: nRF Connect on the user's iPhone, 2026-09-06. The scanner mis-labelled
    # the first two bytes as a company id, which is why the buds show up unnamed.
    captured = bytes.fromhex("0808 0800 FFFF 3041 20FF 36E9 2A64 20FF 36E9 08E0 00".replace(" ", ""))
    advert = decode_advertisement(captured)
    assert advert.product_id == 8
    assert advert.left_mac == "20:FF:36:E9:2A:64"
    assert advert.right_mac == "20:FF:36:E9:08:E0"
    assert advert.feature == 0


def test_advertisement_prefix_letter_scales_product_id() -> None:
    assert decode_advertisement(_advertisement(0x08, ord("E"))).product_id == 6908


def test_advertisement_shorter_than_21_bytes_is_refused() -> None:
    with pytest.raises(ValueError):
        decode_advertisement(bytes(20))
