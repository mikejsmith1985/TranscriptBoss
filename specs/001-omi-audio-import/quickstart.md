# Quickstart: Validating Audio File Import

**Feature**: `001-omi-audio-import` · **Date**: 2026-08-06

Article X: "it compiles" and "it produced a transcript" are not proof. Each scenario below names the evidence that settles one success criterion. A criterion without its evidence is not met, however well the feature appears to work.

---

## Prerequisites

- The forked Omi app built and installed on a physical Android and a physical iOS device. The simulator will not do — on-device transcription and thermal behaviour are the things under test.
- On Android, the whisper model downloaded and live capture confirmed working **before** any import is attempted (T003). Without this, a transcription failure is ambiguous.
- The fixture set from T006 on each device: a short WAV, the same audio as `.m4a` and `.mp3`, a one-hour recording, a silent file, a zero-length file, a truncated file.
- A reference transcript for the one-hour recording, produced by a single-pass transcription of the same audio.

---

## Scenario 1 — A recording becomes a conversation *(SC-001, SC-004)*

1. Open Omi, choose the short `.m4a`, and start the import.
2. Wait for completion.
3. Open the conversation list.

**Evidence**: The conversation exists, carries a transcript, a title and a summary, and is marked as imported. Its transcript is compared against the same audio captured live by Omi on the same device — word error rate within measurement noise of the live capture's.

**Also proves SC-001** when performed by someone who has not read this specification and is given no instructions (T063).

---

## Scenario 2 — No audio leaves the device, nothing is charged *(SC-002)*

⚠️ **Read this before running it.** The on-device transcription socket is *composed* with Omi's backend socket, not substituted for it (see [research.md](./research.md) Part 5). Audio is transcribed locally and never sent; the resulting **text** goes to Omi over `v4/listen`, exactly as it does for a conversation Omi recorded itself, and that is what makes the conversation exist at all.

So an import cannot complete end-to-end in airplane mode, and that is not a defect. Testing it as though it should would fail the feature for the wrong reason.

1. With the network enabled, run a full import while capturing a proxy or platform network log.
2. Record Omi's usage figure for the account before and after.
3. Separately, in airplane mode, start an import and watch it transcribe.

**Evidence**:
- The network log shows **no request carrying audio**, and no call to the metered `/v2/sync-local-files` endpoint. This is the heart of SC-002.
- Omi's usage figure is unchanged — the import consumed no metered transcription allowance.
- In airplane mode, transcription still produces segments locally, proving the engine is on-device. The conversation does not appear until connectivity returns, which is expected and must be what the interface tells the user.

The network log is the half that matters. Airplane mode alone would only prove a call was not *required*; it cannot prove one was not *made* when it could have been.

---

## Scenario 3 — A long recording, unattended *(SC-003, SC-005)*

1. Import the one-hour recording.
2. Record the estimate shown at the start.
3. Leave the device untouched.

**Evidence**: The import completes without intervention. The initial estimate is within a reasonable margin of the actual elapsed time. Peak memory is sampled throughout and is flat with respect to how much of the recording has been consumed — the number to record is peak memory, and it must not scale with recording length. The app is not killed. The device remains usable.

Then repeat with a second and third one-hour recording in sequence, measuring memory between each: no upward trend across imports (contract O-4).

---

## Scenario 4 — Chunk boundaries lose nothing *(FR-008, contract P-2, P-3)*

1. Import the one-hour recording.
2. Compare its transcript word-for-word against the reference transcript.

**Evidence**: No word is missing at a chunk boundary and no word appears twice. Separately, segment timings in the imported conversation are compared against the reference recording's known timings — offsets follow the audio, not the import's wall clock.

This is the scenario most likely to fail silently. A transcript that reads fluently can still have dropped a word at every boundary; only the word-for-word comparison catches it.

---

## Scenario 5 — Every failure says what to do *(SC-009)*

Import each in turn: the corrupt file, the truncated file, the zero-length file, the silent file, a video file, and a file in a format the decoder does not handle.

**Evidence**: Each produces a message stating what happened and what to do. None surfaces only a code. The unsupported-format message names both the format found and the formats accepted. The silent file produces a message rather than an empty conversation. The failures are captured as screenshots, not as assertions alone — the test is whether a person can act on the message.

---

## Scenario 6 — Interruption leaves nothing behind *(SC-007)*

1. Start the one-hour import.
2. Force-quit the app part-way through.
3. Reopen it.

**Evidence**: No conversation exists for that recording. The user is told the import did not finish and can be started again. The scratch file is gone. Repeat across the decoding, transcribing and conversation-creating stages — the last is the one that matters most, and the one a naive implementation gets wrong.

---

## Scenario 7 — No duplicates *(SC-006)*

1. Import the short `.m4a` and let it complete.
2. Copy the file, rename the copy, and import the copy.
3. Import the original again.

**Evidence**: Exactly one conversation exists. Both re-imports tell the user the recording is already imported and point at that conversation. The rename must not defeat this — identity is the contents, not the name.

---

## Scenario 8 — The recording's own time *(SC-008)*

1. Import a fixture carrying a known creation date from yesterday.
2. Import a fixture with no determinable date.

**Evidence**: The first conversation is dated yesterday. The second prompts for a time before starting and is dated to what was given. Neither is dated to the moment of import.

**If T012's spike found no in-app route**, the evidence changes to: the true recording time is recorded and displayed on the conversation, the limitation is stated to the user, and `spec.md` records the fallback. SC-008 is then explicitly not met and is carried as a known gap — not quietly reinterpreted as met.

---

## Scenario 9 — Live capture is unaffected *(SC-010, FR-021, FR-023)*

1. Run Omi's existing test suite on the fork.
2. Record a live conversation with no import running, and keep the transcript.
3. Start the one-hour import, then start a live recording while it runs.

**Evidence**: The existing suite passes unchanged. The live conversation recorded during the import is of the same quality as the one recorded without it — compared directly, not judged. The import yields and resumes afterwards rather than failing.

---

## Scenario 10 — A backlog *(User Story 4)*

1. Select six recordings, one of which is the truncated file.
2. Start the queue and leave the device.

**Evidence**: Five conversations exist. The truncated recording is reported as failed with its own message, and its failure did not stop the others. Queue state was visible throughout. If the device passed a low-battery or thermal threshold during the run, the queue paused and resumed.

---

## What "done" means

Every scenario above passing, with its evidence recorded — not merely observed. Scenarios 2, 4 and 6 are the ones where a feature that looks finished usually is not:

- **2** because a working import proves nothing about whether it stayed local.
- **4** because a fluent transcript can still be missing a word at every join.
- **6** because the crash that matters is the one during conversation creation, and it is the one nobody tests.
