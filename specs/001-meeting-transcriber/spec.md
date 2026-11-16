# Spec 001 — Meeting Transcriber

## Problem
Native Teams/Zoom transcription is unavailable and paid tools are not funded. The Scrum Master needs transcripts of work meetings to feed an approved agent (Microsoft Copilot) for minutes and action tracking.

## Constraints
- No install: runs in managed Chrome on Windows from a static web page.
- Audio never leaves the machine and is never written to disk.
- Invisible during meetings: no live transcript or attention-grabbing UI.
- Must capture both sides of a headset call (desktop Teams/Zoom included).

## User stories
1. Start a recording with one click and a standard Chrome share picker (entire screen + system audio).
2. My own voice (microphone) is labelled separately from everyone else (system audio).
3. Stop, and get a timestamped, speaker-labelled transcript shortly after.
4. Copy a Copilot-ready prompt + transcript, or download it as .txt for long meetings.
5. Choose accuracy (larger model) vs speed (smaller model); choice is remembered.
6. Warned before closing the tab with an unsaved transcript.

## Out of scope (v1)
Live captions, per-person diarization within "Others", saving history, non-English meetings.
