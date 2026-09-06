# Quickstart: validating the RecDot device feature

Two layers of proof, per Article X. Hermetic tests are the only automated evidence; hardware
evidence is the user's iPhone via TestFlight and is written down, never implied.

## Prerequisites

- Fork worktree `omi-recdot/` on branch `feature/viaim-recdot` (see plan.md, Project Structure).
- Python 3.14 with the bit-exact `G722` package installed into the scratch tools dir
  (`pip install --target <dir> G722`), used only to generate fixtures.
- A Codemagic build of `personal/ci` with this branch merged, installed via TestFlight.
- The viaim app **force-quit** on the iPhone (iOS allows one accessory session per protocol).

## Layer 1 — hermetic (runs in Codemagic and upstream CI)

```
python scripts/generate_recdot_vectors.py   # writes app/test/fixtures/recdot_golden/*.json
python scripts/generate_g722_vectors.py     # writes app/test/fixtures/g722_golden/*.json
cd omi-recdot/app && ./test.sh              # Omi's own gate; includes the new tests
python scripts/check-article-iv.ps1 omi-recdot/app/lib/services/devices/connectors/viaim_recdot_connection.dart …
```

Expected: every `recdot_*_test.dart` and `g722_decoder_test.dart` passes; the two exhaustive
device-type map tests pass with the new enum entry; `analyze` count does not rise.

## Layer 2 — the user's iPhone (TestFlight)

| # | Scenario | Evidence to record |
|---|---|---|
| 1 | Pairing (Story 1) | Screenshot of the RecDot in the device list with battery; relaunch Omi; it reconnects unaided |
| 2 | Headset unaffected (FR-004) | Play music and take a short call with Omi connected; note no audio change |
| 3 | Live Teams call (Story 2, SC-002/3/4) | Ten calls ≥ 10 min, phone locked; for each: both sides present, attribution spot-check of 20 utterances, far-end quality report |
| 4 | Pause/resume (FR-009) | Pause mid-call; confirm nothing from the paused span appears |
| 5 | Link drop (FR-011) | Walk out of range 20 s mid-call; conversation shows a gap, capture resumed |
| 6 | FlashRecord (Story 3, SC-005/6) | Ten phone-off recordings; reconnect; each becomes a conversation dated at its true time; bud shows it deleted only after; induce 20 interruptions (case lid, kill app, incoming call) and count duplicates (must be 0) |
| 7 | Transfer refused during a call (FR-014) | Start a call while a transfer is waiting; it does not start; starts after |
| 8 | Passcode-protected clip (FR-019) | Set a passcode in the vendor app once; Omi lists it as protected and skips it |
| 9 | No off-device transcription (SC-007) | With on-device mode set, watch the network indicator / a proxy during a capture: no transcription request |
| 10 | Two recognisers (D-2 risk) | During a 30-min call, on-device polling buffer does not grow; phone does not throttle |

Each row's outcome, with the date and build number, goes into `CHANGELOG.md`'s entry for the
feature and the upstream PR body's "verification evidence" section.

## What is deliberately not proven here

Android. The Kotlin transport compiles in Codemagic and is covered only by the shared Dart tests.
Every document that mentions it says so.

## Evidence log

### Layer 1 — hermetic (2026-09-06, fork branch `feature/viaim-recdot` at upstream `1d91c471`)

| Check | Result |
|---|---|
| STAROT codec + G.722 decoder (`recdot_starot_codec_test`, `g722_decoder_test`) | 58 pass, G.722 bit-exact vs ITU reference |
| Typed commands (`recdot_commands_test`) | 13 pass |
| Device identity + factory mapping (`recdot_device_test`) | 12 pass |
| Link transport (`recdot_link_transport_test`) | 6 pass |
| Connector handshake (`recdot_connection_test`) | 6 pass |
| Discoverer (`recdot_discoverer_test`) | 4 pass |
| Golden-vector generators (`scripts` suite) | 53 pass |
| Omi analyzer ratchet (`app/scripts/analyze_ratchet.sh`) | passed; `use_super_parameters` improved 6→4 |
| Article IV gate (`scripts/check-article-iv.ps1`) | passed, 15 files |
| `flutter analyze lib` errors | 0 (after firebase bootstrap) |
| Regression (`device_provider_test`, exhaustive-map guards, full `test/unit`) | pass; only the 2 pre-existing Windows-env flakes (l10n path, temp-file lock) fail |

**Not run locally**: `app/test.sh` end-to-end (needs the firebase/env bootstrap Codemagic performs); iOS compilation. Both are the Codemagic build's job.

### Layer 2 — TestFlight (pending — needs the user's iPhone)

**Build branch is ready.** `personal/recdot-ci` (fork, commit 67dc848) = current upstream + the
RecDot support + the personal dogfood Codemagic config, without the 001 file-import feature. The
steps that need the user:

1. Push the branch to the fork:
   ```
   git -C C:/ProjectsWin/TranscriptBoss/omi-recdot push fork personal/recdot-ci
   ```
2. In Codemagic, run the `ios-personal-dogfood` workflow against `personal/recdot-ci`.
3. Install the build from TestFlight; force-quit the viaim app first (iOS allows one accessory
   session per protocol).
4. Record rows 1 and 2 of the Layer 2 table with the build number.

Note: the dogfood workflow is manually triggered, so any branch works; no push to `personal/ci`
itself is needed.
