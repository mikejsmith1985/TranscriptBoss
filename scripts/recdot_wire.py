"""Reference codec for the viaim RecDot wire protocol described in specs/002-viaim-recdot-device/protocol.md.

This is not the connector. The connector lives in the Omi fork, in Dart. This module
is the independent second implementation the protocol notes are checked against: it
encodes and decodes the byte layouts exactly as the notes state them, so a byte example
in the notes, a test here, and the Dart codec later must all agree. It is also what
generates the golden fixtures for the Dart tests, which is why it must not be derived
from the Dart code it will be used to test.

Everything here is pure functions over bytes: no Bluetooth, no I/O, no vendor code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag

# --- Framing constants --------------------------------------------------------

SHORT_FRAME_SYNC = 0x55
LONG_FRAME_SYNC = 0x56
FRAME_HEADER_LENGTH = 4
LONG_FRAME_LENGTH_OFFSET = 256
MAX_PAYLOAD_LENGTH = 508
ACK_FLAG = 0x8000
OPCODE_MASK = 0x7FFF

# The vendor encoder writes a total length of 0x00 for a frame of exactly 256 bytes,
# which its own reassembler cannot resynchronise on. Refusing that size keeps every
# frame we produce decodable by the buds' firmware, whose behaviour matches the app.
UNDECODABLE_FRAME_LENGTH = 256

# --- TLV attribute groups -----------------------------------------------------


@dataclass(frozen=True)
class TlvAttribute:
    """One `[len][attr][value]` entry inside a command payload."""

    attribute: int
    value: bytes


def encode_tlv_group(attributes: list[TlvAttribute]) -> bytes:
    """Encode attributes back to back; `len` counts the attribute byte but not itself."""
    encoded = bytearray()
    for entry in attributes:
        encoded.append(len(entry.value) + 1)
        encoded.append(entry.attribute)
        encoded += entry.value
    return bytes(encoded)


def decode_tlv_group(payload: bytes) -> list[TlvAttribute]:
    """Walk a TLV group; a length that runs past the payload is a malformed packet."""
    attributes: list[TlvAttribute] = []
    position = 0
    while position < len(payload):
        declared_length = payload[position]
        value_end = position + 1 + declared_length
        if declared_length < 1 or value_end > len(payload):
            raise ValueError(f"TLV at offset {position} runs past the payload")
        attribute = payload[position + 1]
        attributes.append(TlvAttribute(attribute, bytes(payload[position + 2 : value_end])))
        position = value_end
    return attributes


# --- Frames -------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """A v2 frame: a 16-bit command and its payload."""

    command: int
    payload: bytes

    @property
    def is_ack(self) -> bool:
        """True when the bud is acknowledging a command rather than sending one."""
        return bool(self.command & ACK_FLAG)

    @property
    def opcode(self) -> int:
        """The command without the acknowledgement bit."""
        return self.command & OPCODE_MASK

    @property
    def ack_status(self) -> int | None:
        """The status byte an acknowledgement carries first; None for plain commands."""
        if not self.is_ack or not self.payload:
            return None
        return self.payload[0]

    @property
    def ack_data(self) -> bytes:
        """Acknowledgement data after the status byte; the whole payload otherwise."""
        return self.payload[1:] if self.is_ack else self.payload


def encode_frame(frame: Frame) -> bytes:
    """Frame a command in v2 framing: sync, total length, big-endian command, payload."""
    if len(frame.payload) > MAX_PAYLOAD_LENGTH:
        raise ValueError(f"payload of {len(frame.payload)} bytes exceeds {MAX_PAYLOAD_LENGTH}")
    total_length = FRAME_HEADER_LENGTH + len(frame.payload)
    if total_length == UNDECODABLE_FRAME_LENGTH:
        raise ValueError("a 256-byte frame cannot be decoded by the vendor framer")
    if total_length > UNDECODABLE_FRAME_LENGTH:
        header = bytes([LONG_FRAME_SYNC, total_length - LONG_FRAME_LENGTH_OFFSET])
    else:
        header = bytes([SHORT_FRAME_SYNC, total_length])
    return header + frame.command.to_bytes(2, "big") + frame.payload


def decode_frame(stream: bytes) -> tuple[Frame, int] | None:
    """Decode one frame from the start of a byte stream.

    Returns the frame and how many bytes it consumed, or None when the stream does not
    yet hold a whole frame. An unknown sync byte means the stream has lost alignment.
    """
    if len(stream) < 2:
        return None
    total_length = _read_total_length(stream[0], stream[1])
    if len(stream) < total_length:
        return None
    command = int.from_bytes(stream[2:4], "big")
    payload = bytes(stream[FRAME_HEADER_LENGTH:total_length])
    return Frame(command, payload), total_length


def _read_total_length(sync_byte: int, length_byte: int) -> int:
    """Turn the sync and length bytes into the frame's total length."""
    if sync_byte == SHORT_FRAME_SYNC:
        return length_byte
    if sync_byte == LONG_FRAME_SYNC:
        return length_byte + LONG_FRAME_LENGTH_OFFSET
    raise ValueError(f"unknown sync byte 0x{sync_byte:02X}")


# --- Call audio (0x5007) ------------------------------------------------------


class AudioChannel(IntFlag):
    """Channel bits in the first byte of a call-audio packet."""

    SPEAKER = 1
    MIC = 2
    VPU = 4
    TALK_MINUS_VPU = 16


CHANNEL_MASK = 0x0F


@dataclass(frozen=True)
class CallAudioPacket:
    """The far-end and near-end G.722 bytes carried by one call-audio packet."""

    speaker: bytes
    mic: bytes


def split_call_audio(payload: bytes) -> CallAudioPacket:
    """Split a `0x5007` payload into its channels.

    The first byte's low nibble says which channels are present. When both the speaker
    (far end) and mic (near end) bits are set the remaining bytes are two equal halves,
    speaker first. There is no per-block length, so an odd remainder is corrupt.
    """
    channels = payload[0] & CHANNEL_MASK
    audio = payload[1:]
    has_speaker = bool(channels & AudioChannel.SPEAKER)
    has_mic = bool(channels & AudioChannel.MIC)
    if has_speaker and has_mic:
        if len(audio) % 2:
            raise ValueError("two-channel call audio must have an even payload")
        half = len(audio) // 2
        return CallAudioPacket(speaker=audio[:half], mic=audio[half:])
    if has_speaker:
        return CallAudioPacket(speaker=audio, mic=b"")
    return CallAudioPacket(speaker=b"", mic=audio if has_mic else b"")


# --- FlashRecord chunks (0x5A3A) ----------------------------------------------

FLASH_CHANNEL_SINGLE = 3
FLASH_CHANNEL_TWO_WAY = 4
FLASH_CHANNEL_END_OF_FILE = 255
FLASH_FRAME_LENGTH = 40
FLASH_HEADER_LENGTH = 4


@dataclass(frozen=True)
class FlashChunk:
    """One chunk of a FlashRecord download: where it sits in the file and its audio."""

    offset: int
    speaker: bytes
    mic: bytes
    is_end_of_file: bool


def split_flash_chunk(payload: bytes) -> FlashChunk:
    """Parse a `0x5A3A` chunk: 3-byte big-endian offset, channel tag, audio."""
    if len(payload) < FLASH_HEADER_LENGTH:
        raise ValueError("flash chunk shorter than its header")
    offset = int.from_bytes(payload[:3], "big")
    channel = payload[3]
    audio = payload[FLASH_HEADER_LENGTH:]
    if channel == FLASH_CHANNEL_END_OF_FILE:
        return FlashChunk(offset, b"", b"", is_end_of_file=True)
    if channel == FLASH_CHANNEL_SINGLE:
        return FlashChunk(offset, audio, b"", is_end_of_file=False)
    if channel == FLASH_CHANNEL_TWO_WAY:
        speaker, mic = _deinterleave_flash_frames(audio)
        return FlashChunk(offset, speaker, mic, is_end_of_file=False)
    raise ValueError(f"unknown flash channel tag {channel}")


def _deinterleave_flash_frames(audio: bytes) -> tuple[bytes, bytes]:
    """Two-way flash audio alternates 40-byte frames: speaker, mic, speaker, mic."""
    frames = [audio[start : start + FLASH_FRAME_LENGTH] for start in range(0, len(audio), FLASH_FRAME_LENGTH)]
    speaker = b"".join(frames[0::2])
    mic = b"".join(frames[1::2])
    return speaker, mic


# --- FlashRecord download request (0x5A39) ------------------------------------

GET_RECORD_ATTR_SIDE = 1
GET_RECORD_ATTR_INDEX = 2
GET_RECORD_ATTR_OFFSET = 3
GET_RECORD_ATTR_LENGTH = 4
GET_RECORD_ATTR_PASSWORD = 5
GET_RECORD_CANCEL_ATTR = 0xFF


def encode_get_record_request(
    side: int = 0,
    index: int = 0,
    offset: int = 0,
    length: int = 0,
    password: str | None = None,
    is_cancel: bool = False,
) -> bytes:
    """Build the payload that starts, resumes, or cancels a FlashRecord download.

    The integers are little-endian, unlike every value the buds send back, which is why
    this request has its own encoder rather than a generic one.
    """
    if is_cancel:
        return encode_tlv_group([TlvAttribute(GET_RECORD_CANCEL_ATTR, b"")])
    attributes = [
        TlvAttribute(GET_RECORD_ATTR_SIDE, bytes([side])),
        TlvAttribute(GET_RECORD_ATTR_INDEX, index.to_bytes(4, "little")),
        TlvAttribute(GET_RECORD_ATTR_OFFSET, offset.to_bytes(4, "little")),
        TlvAttribute(GET_RECORD_ATTR_LENGTH, length.to_bytes(4, "little")),
    ]
    if password is not None:
        attributes.append(TlvAttribute(GET_RECORD_ATTR_PASSWORD, password.encode("ascii")))
    return encode_tlv_group(attributes)


# --- BLE advertisement --------------------------------------------------------

ADVERTISEMENT_LENGTH = 21
BATTERY_ABSENT = 0xFF
BATTERY_CHARGING_BIT = 0x80
BATTERY_PERCENT_MASK = 0x7F
PREFIX_SCALE = 100
FIRST_PREFIX_LETTER = ord("0")


@dataclass(frozen=True)
class BleAdvertisement:
    """What a RecDot says about itself before any connection is made."""

    product_id: int
    left_battery_percent: int | None
    is_left_charging: bool
    right_battery_percent: int | None
    is_right_charging: bool
    case_battery_percent: int | None
    is_case_charging: bool
    left_mac: str
    right_mac: str
    feature: int


def decode_advertisement(manufacturer_data: bytes) -> BleAdvertisement:
    """Decode the 21-byte manufacturer payload the buds advertise over BLE."""
    if len(manufacturer_data) < ADVERTISEMENT_LENGTH:
        raise ValueError("advertisement manufacturer data shorter than 21 bytes")
    prefix_letter = manufacturer_data[1]
    prefix_value = prefix_letter * PREFIX_SCALE if prefix_letter > FIRST_PREFIX_LETTER else 0
    left_percent, is_left_charging = _decode_battery(manufacturer_data[3])
    right_percent, is_right_charging = _decode_battery(manufacturer_data[4])
    case_percent, is_case_charging = _decode_battery(manufacturer_data[5])
    return BleAdvertisement(
        product_id=prefix_value + manufacturer_data[0],
        left_battery_percent=left_percent,
        is_left_charging=is_left_charging,
        right_battery_percent=right_percent,
        is_right_charging=is_right_charging,
        case_battery_percent=case_percent,
        is_case_charging=is_case_charging,
        left_mac=_format_mac(manufacturer_data[8:14]),
        right_mac=_format_mac(manufacturer_data[14:20]),
        feature=manufacturer_data[20],
    )


def _decode_battery(raw: int) -> tuple[int | None, bool]:
    """A battery byte is 0xFF when absent; otherwise bit 7 charging, bits 0–6 percent."""
    if raw == BATTERY_ABSENT:
        return None, False
    return raw & BATTERY_PERCENT_MASK, bool(raw & BATTERY_CHARGING_BIT)


def _format_mac(raw: bytes) -> str:
    """Render six address bytes the way Bluetooth settings screens show them."""
    return ":".join(f"{octet:02X}" for octet in raw)
