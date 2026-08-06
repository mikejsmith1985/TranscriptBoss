# Contract: The Audio Source a File Import Must Satisfy

**Feature**: `001-omi-audio-import` · **Date**: 2026-08-06

This feature adds a third producer to an interface Omi already has. The contract below is not ours to design — it is what the existing pipeline already requires of the microphone and Bluetooth sources, written down so the file source can be held to it.

**Verified against** the Omi app at commit `f12031d`, `lib/services/audio_sources/audio_source.dart`.

---

## The interface

```dart
abstract class AudioSource {
  List<WalFrame> processBytes(List<int> rawBytes);
  List<int> getSocketPayload(List<int> rawBytes);
  List<WalFrame> flush();
  BleAudioCodec get codec;
  String get deviceId;
  String get deviceModel;
}
```

Two implementations exist. `BleDeviceSource` strips a three-byte firmware header and emits one frame per call. `PhoneMicSource` buffers incoming bytes and emits fixed-size frames. The file source is closest to the second.

---

## Obligations

### O-1 — Frames must be indistinguishable from live capture

A frame this source produces must have the same shape, size and encoding as one the microphone produces. Everything downstream — the write-ahead log, the transcription socket, the on-device engine — was written against that shape and is not being changed.

**Evidence required**: A byte-level comparison of frames from this source against frames from `PhoneMicSource` for equivalent audio.

### O-2 — `processBytes` must be total

Callers pass whatever they have. The source buffers a partial frame's worth of bytes and emits nothing rather than emitting a short frame; it emits several frames when given several frames' worth. It never throws on an awkward length.

**Evidence required**: Unit tests feeding byte counts that are one below, exactly, and one above a frame boundary, and a zero-length call.

### O-3 — `flush` must emit the tail exactly once

The final partial frame of a recording is emitted by `flush`, padded as the pipeline expects. Calling `flush` twice must not emit it twice — the last seconds of a recording appearing twice in a transcript is a visible defect.

**Evidence required**: A unit test asserting a second `flush` returns empty.

### O-4 — Nothing is retained after the source is done

No buffer, no decoded audio, no file handle survives the import. Twenty hours a week means the leak that does not matter once matters by Thursday.

**Evidence required**: An integration test importing several recordings in sequence with memory measured between each, showing no upward trend.

### O-5 — Identity must mark the conversation as imported

`deviceModel` must make the resulting conversation identifiable as an import rather than a live capture (FR-013), and `deviceId` must distinguish one import from another so frames are attributable.

**Evidence required**: An imported conversation inspected after creation and shown to carry the import marking.

---

## The pump's obligations

The source produces frames; something must drive it. That driver is not part of `AudioSource`, but it is part of this contract because the pipeline's assumptions depend on it.

### P-1 — Audio in flight must be bounded

The pump feeds the pipeline until a fixed amount of *audio duration* is awaiting transcription, then waits. It must not feed by wall clock (which would make a one-hour import take one hour) and must not feed without limit (which would put the whole recording in one buffer and one transcription call).

**Evidence required**: Peak memory during a one-hour import measured and shown to be flat with respect to recording length.

### P-2 — Chunk boundaries must not lose or duplicate words

Audio is transcribed in pieces. A word spanning a boundary must survive it — appearing once, whole.

**Evidence required**: A recording with continuous speech across many boundaries, transcribed and compared word-for-word against the same audio transcribed in a single pass.

### P-3 — Timeline offsets must accumulate by audio, not by clock

Each transcribed piece is placed in the conversation at its offset within the recording. That offset advances by the duration of audio consumed. A transcript whose timeline follows the import's wall clock would be wrong by however much faster than real time the import ran.

**Evidence required**: An imported conversation's segment timings compared against the known timings of a reference recording.

### P-4 — Live capture takes precedence

If Omi is recording when an import is running, or starts recording during one, the import yields (FR-021). The user's live conversation is not degraded by a background job.

**Evidence required**: An integration test starting a live recording during an import and confirming the live capture is unaffected.

---

## What this feature must not change

FR-023 and SC-010: no existing capture path changes behaviour. The one permitted exception is D-3's drain signal — the transcription socket may gain a notification that a chunk has been transcribed, which adds an observation without altering what the socket does.

**Evidence required**: The Omi app's existing test suite passes unchanged, and live capture is exercised on a device before and after.
