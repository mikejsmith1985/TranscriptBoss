# Feature Specification: viaim RecDot as a Native Omi Device

**Feature Branch**: `feature/viaim-recdot-device`

**Created**: 2026-09-06

**Status**: Draft

**Input**: User description: "viaim RecDot as a native Omi device. The user records ~20 h/week with viaim RecDot earbuds and runs Teams meetings on their iPhone. They want to pair the RecDot in Omi exactly like an Omi pendant, have live audio of BOTH sides of a call (far end and their own mic, which the buds deliver as two separate channels) flow into Omi's existing on-device transcription pipeline with speaker attribution, and have recordings made without the phone (FlashRecord, stored on the buds) sync into Omi as conversations when the buds reconnect. iOS first, validated by the user on TestFlight; Android written in parallel for parity but never tested by us; nothing goes upstream until the user has validated on TestFlight. FlashRecord transfer must never run during a call and must delete on the bud only after Omi has persisted the audio; live capture must not disturb the call's own audio."

---

## Why This Feature Exists

The user already owns the recorder they want: viaim RecDot earbuds that hear both sides of a
call because they sit at the audio endpoint. What they do not want is the vendor's app. Omi
already does unlimited free on-device transcription and already treats third-party wearables
as first-class devices. This feature closes the gap between the two so the RecDot becomes, to
the user, "my Omi device".

The earlier feature (`001-omi-audio-import`) remains the fallback: export a file from the vendor
app, import it into Omi. It works, but it is a chore repeated twenty hours a week. This feature
removes the chore.

**What was established before writing this** (`protocol.md` in this directory): how the buds
identify themselves, how they are reached from an iPhone, how call audio is delivered (two
separate channels: far end and the user's own microphone), and how stored recordings are listed,
downloaded, and deleted. Nothing in this specification depends on a fact that is still unknown.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pair the RecDot like an Omi device (Priority: P1)

I open Omi's device screen with my RecDot connected to my phone as a headset. The RecDot is
listed alongside any Omi hardware, with its battery level. I tap it once and it becomes my
connected device: it shows as connected on the home screen, reconnects on its own the next time
I put the buds in, and never asks me to open the vendor app.

**Why this priority**: Everything else in this feature sits behind "it is in the device list and
it connects". Without it, none of the capture stories can even start.

**Independent Test**: With the RecDot paired to the phone as a headset, open Omi, find it in the
device list, connect, kill and relaunch Omi, and confirm it reconnects unaided.

**Acceptance Scenarios**:

1. **Given** the RecDot is connected to the phone as a headset, **When** the user opens Omi's
   find-device flow, **Then** the RecDot appears with its own name and image and a battery level.
2. **Given** the RecDot is listed, **When** the user selects it, **Then** it becomes the connected
   device and the home screen shows it as connected with battery for each bud and the case.
3. **Given** the RecDot was the connected device, **When** Omi is relaunched or the buds are taken
   out of the case later, **Then** Omi reconnects without any user action.
4. **Given** the buds are out of range or in the case, **When** the user looks at Omi, **Then**
   it shows the RecDot as disconnected rather than stalled, and resumes when it returns.
5. **Given** the RecDot is connected to Omi, **When** the user plays music or takes a call,
   **Then** the buds keep working as an ordinary headset with no change in audio.

---

### User Story 2 - Capture both sides of a call, live (Priority: P1)

I am on a Teams call on my iPhone with the RecDot in my ears and Omi in the background. When the
call ends, Omi has a conversation containing what I said and what the other people said, with my
words attributed to me and theirs to them, produced by the same free on-device transcription Omi
uses for its own hardware. The call itself sounded and behaved exactly as it would have without
Omi.

**Why this priority**: This is the user's core use and the one thing no other earbud can do on an
iPhone. Twenty hours a week of meetings is the whole reason for the feature.

**Independent Test**: Hold a real Teams call on the iPhone with Omi connected to the RecDot; the
resulting conversation contains both parties' words, correctly attributed, and the other party
reports no change in call quality.

**Acceptance Scenarios**:

1. **Given** the RecDot is connected to Omi, **When** a call starts on the phone, **Then** Omi
   begins capturing both sides without the user touching the phone.
2. **Given** a capture is running, **When** the user speaks and the far end speaks, **Then** the
   transcript attributes the user's words to the user and the far end's words to the other party.
3. **Given** a capture is running, **When** the call ends, **Then** Omi closes the conversation
   the way it closes one recorded by its own hardware: transcript, title, summary, action items.
4. **Given** a capture is running, **When** the phone is locked or Omi is in the background,
   **Then** capture continues and the conversation is complete when the user returns.
5. **Given** a call is in progress, **When** Omi is capturing, **Then** the call's audio, mute,
   and volume behave exactly as they do with Omi disconnected.
6. **Given** the buds briefly drop and reconnect mid-call, **When** the link returns, **Then**
   capture resumes and the gap is reported in the conversation rather than silently lost.
7. **Given** Omi is connected but the user does not want a call captured, **When** they pause
   capture in Omi, **Then** nothing from that call reaches a conversation until they resume.

---

### User Story 3 - Sync recordings made without the phone (Priority: P2)

I pressed the button on the case and recorded a conversation with the phone in my bag, or the
phone was off. Later, when the buds reconnect to my phone, Omi notices there are recordings on
the buds, pulls them across, and each one becomes a conversation dated when it was recorded.
Omi frees the space on the buds only once the recording is safely stored on the phone.

**Why this priority**: This is the second reason the user bought the buds, and it is what makes
"twenty hours a week" possible without carrying the phone everywhere. It is P2 only because it
depends on Story 1 and is useless until pairing is reliable.

**Independent Test**: Make a recording with the case button and the phone off; power the phone on,
let the buds reconnect to Omi, and confirm a conversation appears with the recording's true time,
and that the recording is gone from the buds only after that conversation exists.

**Acceptance Scenarios**:

1. **Given** recordings are stored on the buds, **When** the buds connect to Omi, **Then** Omi
   tells the user how many recordings are waiting and their total length.
2. **Given** waiting recordings, **When** no call or live capture is in progress, **Then** Omi
   transfers them one at a time and shows progress for each.
3. **Given** a transfer completes, **When** the audio is safely stored on the phone, **Then** and
   only then is that recording removed from the buds.
4. **Given** a transfer is interrupted (call arrives, buds go back in the case, app is killed),
   **When** the buds reconnect, **Then** the transfer resumes from where it stopped and no
   duplicate conversation is created.
5. **Given** a transferred recording, **When** its conversation is created, **Then** the
   conversation carries the recording's true start time, not the transfer time, to the extent the
   platform allows, and states the limitation if it cannot.
6. **Given** a call starts while a transfer is running, **When** the buds are needed for the call,
   **Then** the transfer stops cleanly, the call is unaffected, and the transfer resumes later.
7. **Given** a recording on the buds is protected by a passcode, **When** Omi lists it, **Then**
   the user is told it is protected and it is skipped rather than failing silently.

---

### User Story 4 - Capture an in-person conversation with the buds (Priority: P3)

I am in a meeting room, not on a call. I start a capture in Omi and the buds' own microphones
record the room, the way an Omi pendant would.

**Why this priority**: Valuable, but the phone's own microphone already covers this case in Omi
today, and the buds' room-recording mode is a different audio path from the call path. It ships
after Stories 1 to 3 are proven.

**Independent Test**: Start a capture from Omi with no call active; a conversation with the room's
speech appears, produced from the buds' microphones rather than the phone's.

**Acceptance Scenarios**:

1. **Given** the RecDot is connected and no call is active, **When** the user starts a capture in
   Omi, **Then** the buds' microphones are the audio source and a conversation results.
2. **Given** an in-person capture is running, **When** a call arrives, **Then** the capture yields
   to the call and the call-capture behaviour of Story 2 takes over.

---

### User Story 5 - Android parity, unverified by us (Priority: P3)

An Android user of Omi with the same buds gets the same capabilities. We write it so the code is
complete and consistent with the iOS behaviour, but we cannot test it on hardware.

**Why this priority**: Omi is a two-platform app and an upstream contribution is expected to carry
both. The user will never own an Android device, so validation is Omi's or its users'.

**Independent Test**: The automated tests that cover the shared behaviour pass, the Android build
compiles, and the contribution states plainly that Android was not exercised on hardware.

**Acceptance Scenarios**:

1. **Given** the shared behaviour is covered by automated tests, **When** they run, **Then** they
   pass for both platforms' code paths.
2. **Given** the contribution is offered upstream, **When** a reviewer reads it, **Then** it says
   which platform was exercised on hardware and which was not.

---

### Edge Cases

**Pairing and connection**
- The buds are paired to the phone but only one bud is out of the case.
- Two sets of the same earbuds are nearby.
- The vendor's own app is installed and running on the same phone.
- The buds are connected to a second device (a laptop) at the same time.
- The buds' firmware is newer or older than the one the protocol was recovered from.

**Live capture**
- The far end is silent for a long time, or the user is muted in the call app.
- The call app switches audio to the phone speaker mid-call.
- The battery on one bud runs out mid-call.
- The user starts a second capture while one is running.
- The phone's own live capture (built-in mic or an Omi pendant) is already running.

**Stored recordings**
- The buds report a recording whose length does not match what was transferred.
- The phone runs out of storage during a transfer.
- The same recording is offered again after it was already transferred.
- A recording is longer than the buds' usual maximum.
- The recording lives on the bud that is not the one currently talking to the phone.

**Result**
- The transcript is empty or nonsense (wrong language, poor audio).
- The other party's channel arrives but the user's does not, or vice versa.

---

## Requirements *(mandatory)*

### Functional Requirements

**Pairing and presence**

- **FR-001**: Omi MUST list a RecDot that is paired to the phone as a headset in its device
  discovery, with a distinct name and image, without requiring the vendor's app.
- **FR-002**: Omi MUST show the RecDot's battery for each bud and the case, before and after
  connecting.
- **FR-003**: Omi MUST reconnect to a previously selected RecDot without user action whenever it
  becomes available.
- **FR-004**: Omi MUST show the RecDot as disconnected, not stalled, when it is unavailable, and
  MUST never disturb the buds' ordinary headset behaviour while connected.
- **FR-005**: Omi MUST treat a RecDot as one device even though it is two buds and a case.

**Live call capture**

- **FR-006**: Omi MUST capture both the user's own voice and the far end of a call from the buds
  while a call is in progress on the same phone, without touching the call's own audio path.
- **FR-007**: Omi MUST keep the two sides as separate channels through to transcription so that
  the transcript attributes each utterance to the user or to the other party.
- **FR-008**: Captured audio MUST be transcribed by the same on-device engine Omi uses for its own
  hardware, with no audio leaving the phone and no per-recording cost.
- **FR-009**: Omi MUST start capture automatically when a call begins and end it when the call
  ends, and MUST let the user pause and resume capture at any time.
- **FR-010**: Capture MUST continue while the phone is locked or Omi is in the background.
- **FR-011**: A brief loss of the buds' link MUST resume capture on return, and the gap MUST be
  recorded in the conversation rather than silently dropped.
- **FR-012**: A conversation from a captured call MUST be indistinguishable in kind from one
  recorded by Omi's own hardware: transcript, title, summary, action items, and identification of
  the device that recorded it.

**Stored recordings**

- **FR-013**: On connection, Omi MUST discover recordings stored on the buds and tell the user how
  many are waiting and their total length.
- **FR-014**: Omi MUST NOT transfer stored recordings while a call or a live capture is in
  progress, and MUST stop a running transfer cleanly if a call begins.
- **FR-015**: Omi MUST remove a recording from the buds only after its audio has been durably
  stored on the phone, never before.
- **FR-016**: An interrupted transfer MUST resume from where it stopped and MUST NOT produce a
  duplicate conversation.
- **FR-017**: A stored recording's conversation MUST carry the recording's true start time where
  the platform allows, and MUST state the limitation to the user where it does not.
- **FR-018**: Omi MUST verify a transferred recording's length against what the buds reported and
  MUST tell the user, rather than creating a conversation, when they disagree beyond tolerance.
- **FR-019**: Passcode-protected recordings MUST be reported to the user and skipped.

**In-person capture**

- **FR-020**: With no call active, the user MUST be able to start a capture whose audio source is
  the buds' own microphones.

**Living alongside the rest of Omi**

- **FR-021**: A RecDot capture MUST NOT run at the same time as another live Omi capture on the
  same phone; where they contend, the one already running wins and the user is told.
- **FR-022**: The change MUST NOT alter the behaviour of any existing Omi device or capture path.
- **FR-023**: Every failure the user can encounter MUST be reported as what happened and what to
  do next, never as a code alone.

**Platforms and contribution**

- **FR-024**: The feature MUST ship on iOS first and MUST be validated by the user on a TestFlight
  build before anything is offered upstream.
- **FR-025**: The Android counterpart MUST be implemented for parity, covered by the shared
  automated tests, and MUST be labelled as not exercised on hardware wherever the work is
  described.
- **FR-026**: The behaviour that depends on the buds' protocol MUST be covered by automated tests
  that run without any hardware, using recorded examples of the buds' traffic.

### Key Entities

- **RecDot device**: One logical device made of two buds and a case; identity, per-part battery,
  connection state, and which bud is currently the one talking to the phone.
- **Call capture session**: One captured call; its two audio channels, start and end, pause
  state, any link gaps, and the conversation it produced.
- **Stored recording**: One recording on the buds; which bud holds it, its index, length, start
  time, kind (call or room), passcode protection, and transfer progress on the phone.
- **Transfer**: The act of moving one stored recording to the phone; resumable position,
  verification result, and whether deletion on the buds has been authorised.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with a RecDot paired to their phone can make it their Omi device in under one
  minute without reading documentation or opening the vendor's app.
- **SC-002**: Across ten real calls of at least ten minutes on the iPhone, every resulting
  conversation contains both parties' words, and at least 95% of utterances are attributed to the
  correct side.
- **SC-003**: The other party on those calls reports no change in audio quality, and the user
  reports no change in mute or volume behaviour, in 10 out of 10 calls.
- **SC-004**: Capture survives the phone being locked for the whole call in 10 out of 10 calls.
- **SC-005**: Ten recordings made with the phone off all appear as conversations after the buds
  reconnect, none is deleted from the buds before its conversation exists, and none is
  duplicated across 20 induced interruptions.
- **SC-006**: A one-hour stored recording transfers and becomes a conversation in under fifteen
  minutes of the buds being connected and idle.
- **SC-007**: No audio leaves the phone for transcription and no per-recording charge occurs,
  verified by observing that no transcription request is made off-device.
- **SC-008**: Omi's existing automated tests continue to pass, and no existing device's behaviour
  changes.
- **SC-009**: Every protocol-dependent behaviour has an automated test that runs with no hardware
  attached.

---

## Assumptions

- The RecDot is already paired to the phone as an ordinary headset; Omi does not perform that
  pairing.
- The vendor's app is not running while Omi is using the buds. Only one app can hold the buds'
  data channel at a time; the user chooses Omi.
- The buds accept commands from any app that speaks their protocol. The protocol notes found no
  authentication step; if firmware later adds one, this feature does not attempt to defeat it.
- The user's own microphone channel is the user; the far-end channel is "the other party".
  Distinguishing several far-end speakers from one another is Omi's existing behaviour and is not
  extended here.
- Recordings made in the buds' "room" mode and in "call" mode are both supported for transfer;
  on-device transcription treats them alike.
- On-device transcription quality is what Omi already provides: small model, no word timings.
- The conversation time limitation from feature 001 still applies: the platform cannot yet file
  a conversation at a past time. The true recording time is stored and shown, and the gap is
  stated to the user.
- The only phone available for validation is the user's iPhone via TestFlight; Android is
  never validated by us.

## Dependencies

- `protocol.md` in this directory: the observed facts this feature is built on.
- A build of the Omi app containing this change, delivered to the user's iPhone through
  TestFlight. Upstream acceptance is Omi's decision and the plan does not depend on it.
- Omi's existing device, capture, storage-sync, and on-device transcription machinery, used
  unchanged.
- The Omi upstream contribution standard (`omi-fork/AGENTS.md` and its component guides), which
  governs the fork code.

## Out of Scope

- Any change to the buds' firmware.
- Reaching the buds over Bluetooth Low Energy for data; the buds do not offer it.
- App Store distribution of an app that talks to an accessory certified for Apple devices, which
  requires the accessory maker's consent. TestFlight distribution to the user does not.
- The buds' translation, captioning, and voice-assistant features.
- Merging a captured call with a conversation Omi's own hardware recorded of the same meeting.
- Separating several far-end speakers from one another.
