# Draft issue for BasedHardware/omi

Kept short on purpose. Omi's `AGENTS.md` asks that issues state a problem with
evidence rather than an implementation epic, so the design detail stays in the PR.

Paste everything below the line.

---

**Title:** Import an existing audio file and transcribe it on-device

Omi transcribes on-device for free and unlimited, but only audio it captured
itself. There is no way to hand it a recording that already exists — from a voice
memo, a dictaphone, or another wearable. The one import path that exists
(`app/lib/backend/http/api/imports.dart:105`, `startLimitlessImport`) uploads a
ZIP for **cloud** processing, which is metered and is a different thing.

My own case, since it is the reason I built this: I record with viaim RecDot
earbuds and end up with roughly **20 hours of audio a week**. Unlimited free
on-device transcription is specifically why I bought into Omi — it is the only
thing that makes that volume viable. But the recordings arrive as files from the
earbuds' own app, and there is no way to hand them to the engine that would
transcribe them for nothing. The metered cloud allowance covers around a month of
what I generate in a week, so that route is not an alternative.

That gap gets worse the more audio you have, which is to say it hits the people
who need Omi most.

**The interesting part is how little the app would have to change.** Reading
against `f12031d`, the commit this was developed on:

- `lib/services/audio_sources/audio_source.dart:54` — `AudioSource` is already an
  abstraction over where bytes come from, with two implementations, and nothing in
  the interface refers to hardware. A file is a third producer, not a special case.
- `lib/services/sockets/pure_polling.dart:224` — `send()` is unpaced, and
  `:155` advances the transcript timeline by transcribed audio duration rather than
  wall clock. So audio can be fed faster than real time and still land correctly.
- `lib/services/capture/capture_controller.dart:1885` —
  `forceProcessingCurrentConversation()` already closes a session into a normal
  conversation.

**I have this working and would like to contribute it.** It adds a
`FileImportSource`, a pump that bounds how much audio is in flight (a file has no
natural pacing, unlike a mic), and native decoders — `AVAudioFile` +
`AVAudioConverter` on iOS, `MediaExtractor` + `MediaCodec` on Android — because
nothing in the app can currently read an `.m4a`. **Both platforms are implemented.**
The diff touches two existing files by 62 added lines, with no deletions and no new
package dependencies; everything else is new and isolated. 92 unit tests pass, and
the full suite is unaffected.

Two things before I open a PR:

1. **Would you take this?** I would rather ask than send an unsolicited PR.
2. **Does `SFSpeechRecognizer` throttle at volume?** iOS forces
   `requiresOnDeviceRecognition = true` (`AppDelegate.swift:681`), which is ideal
   here, but a long import becomes many sequential requests — roughly 120 for an
   hour of audio at 30-second chunks. If Apple rate-limits that, it shapes the
   design, and you will know sooner than I can find out.

One caveat I want to be upfront about: **I have not been able to run this on a
physical device** — I have no Mac and no Android hardware. The unit tests pass and
the analyzer is clean, but the native decoders have never executed. If you are
interested in principle, I would want that covered before merge, either by someone
with a device or by whatever you think is appropriate.

*Written and implemented with Claude Code, which I mention for transparency rather
than as a disclaimer — every file:line reference above was verified against
`f12031d`, and I stand behind the design decisions as my own.*
