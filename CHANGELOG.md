# Changelog — TranscriptBoss

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Article VI**: this file is the single source of truth for what changed.
> Every pull request that changes behaviour updates it. Do not create auxiliary
> summary or status documents — the `specs/<feature>/` trees are the only
> exception, and they are Spec Kit pipeline artifacts rather than status docs.

## [Unreleased]

### Added

- Protocol notes for the **viaim RecDot** earbuds under `specs/002-viaim-recdot-device/`,
  recovered from the vendor's Android app: v2 framing, bond-code handshake, the
  two-channel call-audio stream, and the FlashRecord download commands. The iOS
  transport was then confirmed from the vendor's iOS app bundle: an MFi External
  Accessory session on protocol `com.vision.voyager`.
- `scripts/recdot_wire.py` — reference encoder/decoder for those layouts, with
  hermetic tests that pin the exact wire bytes the notes claim; it is the
  independent implementation the Omi connector's golden fixtures will come from
  (its first golden vector is the advertisement a real RecDot broadcast to the
  user's iPhone)
- `scripts/generate_recdot_vectors.py` and `scripts/generate_g722_vectors.py` — write the
  JSON golden fixtures the Omi fork's Dart codec and G.722 decoder are tested against,
  from the Python reference codec and the bit-exact ITU G.722 build respectively
- Feature 002 (viaim RecDot native device) specification, plan, contracts and tasks
  under `specs/002-viaim-recdot-device/`; `scripts/check-article-iv.ps1` owns its paths
- Forge Workflow initialized with Forge Terminal Workflow Architect
- Specification, plan, and task breakdown for **External Audio Import & Transcript
  Reconciliation for Omi** under `specs/001-omi-audio-import/`
- Four-project skeleton: `worker/` (local daemon, holds all audio), `control-plane/`
  (operator-hosted, owns the Omi app credential), `web/` (one component library,
  two bundles), `omi-app/` (App Store listing artifacts)
- Tooling: ruff + mypy strict for both Python projects, ESLint flat config and
  Prettier for the web bundles, pytest with an Article V unit-test speed gate
  that fails any "unit" test exceeding 10 ms, Cypress with `cypress-real-events`
- `scripts/run-dev-clean.ps1` — clean-slate dev launcher that stops processes
  **only by recorded PID**, never by name pattern (Article II)
- `scripts/local-release.ps1` — local-only release pipeline (Article VIII); it
  refuses to release a version with no changelog entry
- Environment-only configuration loaders for both services, with secret-shaped
  values typed as `SecretStr` so they cannot leak through `repr()` (Article IX)
- Worker foundation: user-facing error taxonomy where every failure carries what
  happened and what to do (FR-064); structured logging with credential redaction
  applied at the handler so it cannot be bypassed (Article IX); OS-keychain
  credential store so the SQLite file carries no tokens
- `LinkedAccount` and an account-scoping session layer — every account-scoped
  query is narrowed before it reaches the database, making cross-account reads
  impossible rather than merely discouraged (FR-002, data-model Invariant 0)
- `ImportJob` with the full stage enum, and the resumable stage machine whose
  one invariant is that a stage's output is committed **before** the stage is
  marked complete — the basis of SC-006 (no duplicates) and SC-007 (never
  re-transcribes)
- Retry policy that distinguishes transient from terminal, so a recording that
  can never import does not exhaust the attempts one that can needs (FR-014a)
- Undo journal recording every write with its reversal strategy, and a preview
  that separates what undo *can* take back from what it cannot — an integration
  app cannot delete an Omi conversation, and FR-063 requires saying so
- Queue controls (pause, resume, cancel, retry) that refuse to interrupt a job
  part-way through writing to Omi, because that is how FR-060's half-applied
  state happens
- Worker daemon: loopback-only bind enforced in config, per-run token file,
  PID file for Article II safe-stop, and `GET /health`
- Alembic migrations for both stores, with SQLite batch mode so an existing
  user's store is migrated in place rather than recreated
- Control plane: PostgreSQL store, error envelopes, `ProxyAuditRecord`, and the
  rate-limit-aware Omi client — the only place the app credential is used
- Contract tests asserting each service matches its published OpenAPI, with an
  exemption list that names the task which removes each entry
- Typed TypeScript clients generated from both contracts, so a contract change
  becomes a compile error rather than a runtime surprise
- **Account linking (User Story 1, backend)**: Omi authorisation with a CSRF
  state check — Omi's flow has no code exchange, so without it anyone could send
  a user to the callback with a `uid` of their choosing; signed browser sessions;
  single-use, ten-minute pairing codes that store only the token hash; worker
  token authentication scoping every proxied call to exactly one account;
  revocation detection that **pauses** an account's queue rather than failing it;
  disconnect that destroys the authority to act
- Worker-side `LinkedAccount` creation on pairing, with the token in the OS
  keychain and only its reference in SQLite, plus account switching for a shared
  machine (FR-002)
- Scoped Omi conversation read proxy, returning the transcript segments
  reconciliation matches on
- Revocation handling on the worker: an account losing authorisation **pauses**
  its queued imports at the stage each had reached, and reconnecting resumes
  every one of them from there (FR-003)
- **User Story 1 is complete.** Two web bundles built from one component
  library — the hosted connect-and-pair page and the worker's pairing panel —
  with Cypress coverage using real keyboard and mouse events, and the Omi App
  Store manifest with a written justification for each of the four permissions
  requested (FR-005)

- **Import foundations (User Story 2, partial)**: `SourceRecording` identified by
  content hash so resubmitting a file is a no-op (FR-011); `Transcript`,
  `Utterance` and `Speaker` with a stored normalised form for anchor matching;
  the five transcription tiers declared as capabilities rather than names, so the
  router reasons about what a path *can do* rather than what it is called;
  `ImportIntent` with a derived idempotency key a fresh process can recompute
  after a crash
- ffprobe-based format detection that trusts the bytes rather than the extension,
  and names both the format found and the accepted ones when it refuses (FR-008)
- Recording-time determination following FR-027's stated fallback order, which
  **never** substitutes the import time and flags a filesystem timestamp from the
  last few hours for confirmation — that is almost always the moment a messaging
  app copied the file, not the moment it was recorded
- Migration adding the `import_job → source_recording` foreign key deferred in
  Phase 2, verified through a full upgrade/downgrade/upgrade round-trip

- **Phase 1 setup for the file-import feature.** The Omi monorepo is forked into
  `omi-fork/` — its own git repository with an `upstream` remote, pinned to commit
  `f12031d` on branch `feature/file-import`, and deliberately untracked here so the
  work can become a pull request against Omi's own history rather than a copy of
  their files inside ours. The pin is `f12031d` specifically because that is the
  commit every file:line reference in the spike was read against; all four key
  references were re-verified after pinning
- `scripts/check_function_length.py` — enforces the constitution's 40-line function
  rule, which **no** Dart linter can. Function-length checks live in
  `dart_code_metrics`, whose free tier was retired in 2024, so this is the one
  Article IV rule nothing off the shelf provides (the Article VII documented gap).
  It blanks comments and string literals before counting braces, so a brace inside
  a string cannot skew the result. Verified against Omi's own code rather than
  assumed: it passes the two short audio-source files and reports 10 long functions
  in `capture_controller.dart`, two of which were hand-checked line by line and
  matched exactly
- `scripts/test_check_function_length.py` — 12 tests for that checker, added when
  the pre-commit gate rightly refused to accept it without them. Hand-verification
  proved it worked on one file and nothing more, and this checker decides whether
  Article IV is enforced across the whole feature, so a bug in it fails silently.
  The cases are the ways a brace counter gets fooled: braces inside string literals
  (constant in Dart, where `'${value}'` appears everywhere), braces inside comments,
  control flow that reads exactly like a signature, expression bodies with no braces
  at all, and the exact 40-line boundary — an off-by-one there being both easy to
  write and impossible to notice in use
- `scripts/check-article-iv.ps1` and `omi-fork/app/analysis_options_transcriptboss.yaml`
  — our stricter lint rules scoped to the files this feature adds, never to Omi's
  codebase. Omi gates pull requests with an analyzer ratchet that fails any lint
  rule rising above a committed baseline; switching our rules on globally would
  either redden that gate or force a baseline rewrite across thousands of lines we
  did not write, sinking the upstream contribution
- `omi-fork/app/integration_test/import/fixtures.dart` — synthesises the
  deterministic fixtures (silence, a known-duration tone, a truncated file, an empty
  file) and locates the real-speech ones on the device. Real recordings are not
  committed: an hour of 16 kHz mono PCM16 is roughly 115 MB and a pull request
  carrying it would be refused

- **Phase 2, partial.** The Pigeon decode contract
  (`omi-fork/app/lib/audio_decoder_interface.dart`), and the import primitives:
  content identity, format detection, scratch storage, the domain model, and
  recording-time resolution. No new package dependencies were needed — `crypto`,
  `path`, `path_provider` and `file_picker` are all already in Omi's pubspec, which
  matters for the upstream contribution
- The decode bridge is **pull-based on purpose**: native decodes only when the
  caller asks for a chunk. A push-based decoder would race ahead of transcription
  and reintroduce exactly the unbounded-memory failure SC-005 exists to prevent
- `ImportJob.complete()` is the only route to a non-null `conversationId`. Making
  that a property of the type rather than a rule in prose is what stops a partial
  import presenting itself as a finished one (data-model Invariant 1)
- Format detection reads the bytes, never the extension — a `.wav` from a messaging
  app is very often a renamed `.m4a`, and handing the wrong container to a decoder
  produces silence or noise rather than an error. It also distinguishes video from
  audio inside an MPEG-4 container, because picking a video by mistake is something
  people actually do and "unsupported format" would not help them
- Scratch storage purges files abandoned by a previous run at startup. A process
  killed mid-import cannot clean up after itself, and at ~115 MB per hour of decoded
  audio the leak would fill a phone within days

- The AudioSource contract as a **shared, parameterised test suite** run against
  `PhoneMicSource` today. A contract suite that has never passed anything is just an
  assertion about code that does not exist yet; running it against the implementation
  the pipeline was actually built for proves the suite describes reality. The file
  source joins the same suite at T019 and must clear it without the suite being
  softened
- Android decoding via `MediaExtractor` + `MediaCodec`, with a windowed-sinc
  anti-aliasing resampler. Dropping every third sample to get from 48 kHz to 16 kHz
  would fold everything above 8 kHz back into the speech band as noise that was never
  there — which does not sound like distortion so much as a worse microphone, and
  would have surfaced as an unexplained transcript-quality drop against SC-004 and
  been blamed on the engine rather than on us. The filter carries its history across
  chunk boundaries, which is what contract obligation P-2 depends on
- The resampler is built from the decoder's **output** format, not the track's input
  format. A decoder may report the track's rate up front and then produce something
  else; using the input format is a bug that only appears on the devices where the
  two differ
- iOS decoding via `AVAudioFile` + `AVAudioConverter`. Unlike the Android side there
  is no hand-written resampler: `AVAudioConverter` does rate conversion with its own
  anti-aliasing. Because the two platforms are therefore built differently, T011 must
  compare each against a reference decode rather than against each other — two
  implementations agreeing would prove nothing if both were wrong the same way
- The converter's input block returns nil with `.endOfStream` so the converter flushes
  its own tail, mirroring `PcmResampler.drain()` on Android. Without it the last
  fraction of a second of every recording is discarded — small enough to pass testing,
  large enough to clip a final word
- **FR-002a: the two platforms do not decode the same formats.** Core Audio has no Ogg
  or Vorbis decoder, so an iPhone cannot read `.ogg` however valid the file is, while
  Android can. Accepting a file and then failing on it is exactly the "discovered
  after a long wait" outcome FR-003 exists to prevent, so format support is now
  platform-aware: the accepted list shown to a user contains only what the phone in
  their hand can decode, and a file refused for this reason is described as needing
  conversion rather than as damaged — the recording is fine, and saying otherwise
  sends them looking for a fault that does not exist
- `import_failures.dart` — every failure path in one place, so a new one has an
  obvious home and an obvious standard rather than growing an inline
  `throw Exception('decode failed')`. `ImportFailure` implements `Exception` so the
  decode and pump layers throw it directly, which removes the "and now translate the
  technical error" step there would otherwise be to forget

- **`FileImportSource` — the third `AudioSource`.** Deliberately a near-copy of
  `PhoneMicSource`: same 320-byte frames, same codec, same wrapping sync keys.
  Resisting the urge to be cleverer is the point, and the shared contract suite now
  runs against both. O-1 is asserted at its strictest — the frames a file produces
  are compared **byte-for-byte** against the frames the microphone produces from the
  same audio, including the padded tail, and including the case where the bytes
  arrive in different-sized chunks (a decoder never chunks like a microphone does)
- **The paced pump** (`import_pump.dart`), bounding audio *in flight* rather than
  elapsed time — 30 seconds, chosen to match the transcription model's own attention
  window rather than picked as a round number. Smaller chunks would give the engine
  less context and worse transcripts; larger ones would raise peak memory and slow
  cancellation without improving anything
- **The change to Omi's own code is 15 added lines in one file, with nothing
  modified or deleted**: two getters on `PurePollingSocket` reporting buffer depth
  and whether a pass is running. Live sources are self-pacing, so nothing ever needed
  to ask how full that buffer was; a file source has no such limit. Observation only,
  which is what FR-023 and SC-010 require

- **`ImportSession`** — the ordering, the guards, and knowing when to stop. Almost all
  of what it does is decide *not* to do something: transcription, conversation
  creation, titles, summaries and action items are all Omi's. It refuses early on a
  duplicate, a live recording in progress, or an empty file — each cheaper to detect
  than to discover — and only closes a session into a conversation once the whole
  recording has been transcribed, because a conversation that exists before the audio
  is finished is the half-built one FR-019 forbids
- `ImportRegistry` — content-hash record of completed imports, written **only** once a
  conversation exists. Recording it earlier would make a failed import look completed
  and block the retry that should follow, which is the same mistake as setting a
  conversation id before there is a conversation. Corrupt storage returns empty rather
  than throwing: the cost of starting over is one possible duplicate, the cost of
  throwing is that no import ever runs again on that device
- `ImportPickerPage`, whose real job is refusing well — anyone can show a file picker
- **`FR-006a`: an import needs connectivity to finish, even though transcription is
  local.** Transcription proceeding offline with the conversation pending is a normal
  state that the interface must show as such, not as a stall

- **The backlog queue** — strictly sequential, because two imports at once would
  contend for the single transcription pipeline and produce two interleaved, useless
  conversations. There is no throughput to win: the device transcribes at the rate it
  transcribes, and running two only splits it
- A failure is contained to the recording that caused it, which is the difference
  between a queue that survives a backlog and one found the next morning having
  stalled on the first damaged file. An already-imported recording is counted as
  **skipped, not failed** — the user has the conversation already, and showing it as
  an error would send them hunting a problem that does not exist
- **Device conditions read through a new Pigeon contract rather than a package.** The
  app already reads *watch* and *BLE device* battery but never the phone's own, and
  the obvious candidate — `battery_plus` — has no thermal API at all. Since thermal
  needed a platform call regardless, one contract covers both and the app gains no new
  dependency for an upstream reviewer to weigh
- Pause and resume use **different battery thresholds**. A single one makes the queue
  flap — pause at 20%, creep to 20.1%, resume, drop, pause again — which is worse than
  either state. Charging bypasses the rule entirely: overnight on a charger is exactly
  when a backlog should run
- Unknown readings mean *carry on*, never *stop*. Some devices decline to report
  battery level, and Android below 10 cannot report thermal state at all; treating
  silence as a reason to pause would leave the queue permanently stopped on those
  phones, which is a worse failure than occasionally importing on a lower battery
- **Recording-time resolution** following FR-014's order of evidence: what the file
  says about itself, then its name, then the filesystem, then asking. Embedded dates
  are now read at probe time on both platforms — `MediaMetadataRetriever` on Android,
  `AVAsset.creationDate` on iOS — because that is the only evidence of when a recording
  was made that survives the file being copied, shared or re-exported
- Implausible dates are rejected rather than carried forward: a container reporting
  1904 is a field that was never written (the QuickTime epoch), and a date in the
  future is a recorder with a wrong clock. Either would file a conversation on a day
  nothing happened
- Whether a time needs confirming is now decided by the resolver rather than inferred
  from its source, because for a filesystem timestamp the answer depends on *how
  recent* it is — one from the last few hours almost always records when a messaging
  app copied the file, not when the audio was captured
- The recording time is stored with the completed import and correctable afterwards
  (FR-015). It cannot become the conversation's own date — the T012 spike settled that
  — but keeping it means the information is not lost, and if Omi later accepts a
  `started_at` on creation nothing has to be re-derived from files the user may by then
  have deleted
- **Progress and a remaining-time estimate** built from throughput *measured as the
  import runs*, not a fixed multiplier — speed varies several-fold between a recent
  phone and an old one, between the small and large models, and between a cool device
  and one twenty minutes into a job. Early estimates are **withheld rather than shown
  badly**: the first seconds are dominated by model loading and buffer fill, and a
  confident wrong number is worse than none because the user plans around it
- `ImportController` owns the running import so it outlives the screen that started
  it. If the screen owned the work, navigating away would silently cancel an hour of
  transcription — the behaviour that makes a feature feel broken rather than slow.
  Cancelling stays deliberate (FR-017, FR-020)
- Memory-pressure backoff wired to Flutter's own `didHaveMemoryPressure`, so the pump
  responds to a real signal rather than a heuristic it could not calibrate. The budget
  shrinks but never below a one-second floor: the point of backing off is to survive
  the squeeze and finish, not to grind to a halt politely
- `ImportRecovery` fails every unfinished job at startup and **never resumes one**. The
  state that resuming would have to trust — how much audio reached the engine, what the
  server session holds, whether a conversation was half-created — is exactly the state
  a crash makes unreliable. Starting over costs a re-transcription on hardware that
  does it for free; resuming wrongly costs a conversation with a hole in it that the
  user cannot detect (FR-019, SC-007)
- **Bulk export of recordings to WAV** — "Export all as WAV" on the sync page's Manage
  Storage sheet decodes every recording still held on the phone and offers the whole
  batch to the system share sheet in one go. The app could already share one recording
  at a time, which is fine for one and unusable for fifty; a user who has accumulated
  fifty is exactly the user who most needs them off the phone. `WalBulkExporter` owns
  the rules that make an unattended run trustworthy: a recording that cannot be read is
  recorded as a failure and the run continues, progress is reported after every
  recording so a long decode is visibly alive rather than apparently frozen, and a
  cancelled run still returns everything it had finished. Decoding reuses the app's
  existing Opus/PCM→WAV path rather than growing a second one, and `share_plus` does
  the multi-file share it already supported (Article VII)
- A recording showing **"synced" does not mean its audio was kept**. Retention is gated
  on the account's Private Cloud Sync setting, which is off by default: with it off the
  backend transcribes and discards, so the conversation survives and the recording does
  not. This is why exporting from the phone is worth doing before clearing anything
- **Upstream contributions to BasedHardware/omi**, worked in git worktrees off current
  production rather than off our pinned fork, because Omi reviews against `main` and our
  fork is hundreds of commits behind it. The worktrees are ignored here; each is a full
  checkout of their tree and none of it is ours. What each branch is for:

  | Branch | Upstream | State |
  |---|---|---|
  | `feature/app-store-search` (`omi-prod/`) | [PR #11293](https://github.com/BasedHardware/omi/pull/11293) — search progress indicator that does not time out | Open, awaiting review |
  | `fix/app-search-empty-flash` (`omi-pr2/`) | [PR #11297](https://github.com/BasedHardware/omi/pull/11297) — search holds its searching state until the newest query lands | Open, review bot cleared |

  Issues raised rather than patched, because each needed a decision that was theirs to
  make: [#11292](https://github.com/BasedHardware/omi/issues/11292) app search fetches
  and enriches the whole catalog per query — **they merged the name-vs-description half
  themselves and handed the query-pushdown half back to us**, and a design proposal for
  it is open on that thread; [#11295](https://github.com/BasedHardware/omi/issues/11295)
  a conversation stuck in `processing` renders forever with no age or way to clear it;
  [#11296](https://github.com/BasedHardware/omi/issues/11296) "My Apps" filters by
  authorship so it is permanently empty for anyone who has not built an app. The last two
  are parked at *Someday* on their board.

### Changed

- **Re-planned the entire feature around file import into the Omi mobile app.**
  The original design put transcription on the user's PC. Two facts retired it:
  the recordings live on the phone, and the need is roughly 20 hours a *week*
  against a free cloud allowance of ~20 hours a *month*. What survives is the
  premise the project started from — Omi already runs unlimited free
  transcription on the phone — so the product is no longer a second engine but
  the missing doorway into the one already there.
- A spike against the Omi app (commit `f12031d`) established that its audio
  ingress is already an abstraction: `AudioSource` has two implementations
  (Bluetooth and phone microphone) and nothing in it refers to hardware. The
  pipeline is also not wall-clock locked — the transcript timeline advances by
  transcribed audio duration, not elapsed time — so a file can be fed faster
  than real time and still land correctly. Findings recorded with file:line
  evidence in `specs/001-omi-audio-import/research.md` Part 2.
- Rewrote `spec.md` (7 stories and 70 requirements → 5 stories and 23), `plan.md`,
  `data-model.md` (14 entities → 3), `quickstart.md` and `tasks.md`
  (188 tasks → 70). Replaced the four service contracts with a single
  `contracts/audio-source.md` stating what the new source and its pump owe the
  existing pipeline
- Transcript merging is now explicitly out of MVP scope at the user's direction —
  standalone import and a clean transcript is the deliverable. The anchor-matching
  design is retained because the reason it looked blocked was wrong: the on-device
  engine cannot separate speakers, but Omi's own conversation already marks which
  utterances are the user's, so an imported transcript never needs its own
  diarization
- Chose native platform decoders (`MediaCodec` / `AVAudioConverter`) over
  `ffmpeg_kit_flutter`, which was retired upstream in 2025 with its prebuilt
  binaries withdrawn and would add 9–40 MB for a capability both operating
  systems already ship. Nothing in the Omi app can currently decode an `.m4a`;
  its transcoders handle only the PCM and Opus its own hardware produces
- Reading Omi's own `AGENTS.md` and `app/AGENTS.md` changed four planned tasks:
  the native bridge is Pigeon rather than a hand-written method channel (there is
  a near-exact precedent in `lib/phone_mic_interface.dart`); an analyzer ratchet
  already exists and must not be rebuilt; every user-facing string must be
  localised across 49 locales with zero untranslated messages, which makes
  localisation a completion condition rather than polish; and `test/` must stay
  hermetic because CI runs all of it, with device tests confined to
  `integration_test/`. The last of these matches Article V's split exactly
- `test/unit/audio_source_test.dart` already exists upstream and pins every
  constant the new source must match — 320-byte frames at 16 kHz 16-bit mono,
  `pcm16`, sync keys wrapping at 255, `flush` zero-padding the tail and returning
  empty when drained. Contract obligation O-1 is therefore already an upstream
  test we can be measured against, so our tests extend that file's shape rather
  than inventing a parallel one
- Extended the existing PR template with per-Article constitution checks and an
  evidence section (Article X)

### Performance

- **The pre-commit test-file gate no longer walks the tree once per staged file.**
  It ran `find .` (bash) / `Get-ChildItem -Recurse` (PowerShell) for every candidate
  test filename of every newly added source file — fine in a small repo, pathological
  in one that also contains a vendored checkout. With the Omi monorepo under
  `omi-fork/`, **97% of the tree (11,776 of 12,173 files) belongs to a fork whose
  files can never be staged**, and a routine commit took minutes and had to be killed.
  Both hooks now build one index of test-shaped filenames and match against it,
  pruning `.git`, `omi-fork`, `vendor`, `third_party`, `node_modules`, `.venv`, and
  the usual cache and build directories. The index is built only when there is a new
  source file to check, so ordinary commits pay nothing for it.
- Measured: the indexing walk takes 0.063 s once, against 0.299 s for a *single* old
  unpruned `find`. Verified behaviourally as well as for speed — a new source file
  with no test is still blocked, and adding the matching test still satisfies the
  gate, both in well under a second, on both the bash and PowerShell hooks.
- `omi-fork/`, `vendor/` and `third_party/` were also added to the gate's
  build-output exclusion list, so vendored source is never asked to carry tests we
  would be writing for someone else's code.

### Removed

- **The desktop-worker build** — `worker/`, `control-plane/`, `web/` and
  `omi-app/`, 141 files. Preserved first on `chore/archive-desktop-worker`
  (commit `bd9fdff`), because none of it had ever been committed and a plain
  delete would have been unrecoverable. The transcription engine, the tier
  router and the worker daemon are genuinely dead — Omi's on-device engine
  replaces them — but the stage machine, undo journal, account-scoping layer and
  the anchor-matching design for User Story 5 all survive on that branch, along
  with 72 worker tests and 31 control-plane tests
- Stale ignore rules pointing at the removed directories

### Fixed

- **Corrected quickstart Scenario 2 before it could fail the feature for the wrong
  reason.** It asserted that a full import completes in airplane mode. It cannot:
  `createFromCustomConfig` wraps the on-device socket in a *composite* service —
  primary STT plus the Omi backend — so locally-produced text still travels to Omi
  over `v4/listen`, which is what makes the conversation exist at all. SC-002 says
  *audio* does not leave the device, and that holds exactly. The scenario now tests
  the network log, which is the half that actually proves it; airplane mode alone
  could only ever show a call was not *required*, never that one was not *made*.
- `ImportPump` depended on the concrete `DecodeSession`, whose private constructor made
  the pacing untestable — the one behaviour whose failure appears as the app being
  killed on someone else's phone rather than as a wrong result. Extracted the read-only
  `DecodedAudioReader` the pump actually needs.
- `_isPipelineFull` had two branches computing the same value, so the reservation for an
  already-running transcription pass did nothing. A pass holds a chunk the socket's
  buffer no longer reports, so half the budget is now genuinely reserved for it —
  without which the bound was exceeded by one chunk in the case that happens most of
  the time rather than rarely.
- The Article IV gate caught its own author: `runAudioSourceContract` was 132 lines.
  Split by obligation (O-1…O-5), which reads better than the original anyway.
- **The T012 spike failed, and the specification now says so.** An imported
  conversation's timestamp cannot be set from within the app: creation posts an
  empty body to `POST /v1/conversations` and the server stamps it, no request field
  anywhere carries a recording time, and none of the seven existing PATCH routes
  touches the date. The one convention that *does* honour a client-supplied time —
  the batch filename parsed by `BatchRecordingInfo` — belongs to the metered
  `/v2/sync-local-files` cloud path this feature exists to avoid, so taking it would
  sacrifice the whole point. FR-014 is reduced, FR-014b added, User Story 3 dropped
  from P2 to P3, and **SC-008 is recorded as unmet rather than reworded into
  something that passes**. The upstream fix is small — accept an optional
  `started_at` on creation, or add a PATCH route for it — and is raised with the
  Phase 8 contribution instead of being worked around

- The Article V unit-test speed gate charged the first test in a session for
  pytest's own lazy initialisation (~100–130 ms regardless of which test ran
  first), so a correct test failed the 10 ms budget. The first timed test is now
  exempt and every subsequent one is enforced strictly; verified by a deliberate
  50 ms test still being caught.
- The Omi client treated `Retry-After: 0` as absent and waited five seconds
  instead of retrying immediately — a falsy-zero bug from using `or` for a
  default. Caught by a test asserting the exact wait Omi asked for.
- A per-test asyncio event loop cost more than the whole 10 ms unit budget, so
  every async unit test failed the gate. The loop is now session-scoped.
- Resuming a paused import put it back at the first stage, which would have made
  the stage machine treat every completed stage as pending and transcribe the
  recording a second time — the exact cost SC-007 exists to prevent. Jobs now
  record the stage they were paused at and return to it.

### Security

- `UtcDateTime` column type on both stores. PostgreSQL columns default to
  `TIMESTAMP WITHOUT TIME ZONE` and SQLite has no timestamp type at all, so
  datetimes were coming back naive and silently poisoning every comparison — in
  a product whose entire domain is deciding whether two recordings happened at
  the same time. Writing a naive datetime is now refused outright rather than
  guessed at.
