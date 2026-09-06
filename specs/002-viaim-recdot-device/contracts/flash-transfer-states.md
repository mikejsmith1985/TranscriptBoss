# Contract: FlashRecord transfer state machine

Governs `TransferJob` (data-model.md). Every transition that talks to the bud is persisted
before the command is sent, so a crash never leaves the bud and the phone disagreeing about
whether a recording is safe to delete.

## States and transitions

| From | Event | To | Side effect |
|---|---|---|---|
| — | `0x5A37` list entry received | `listed` | Job created if no job with the same identity exists at `imported` or later |
| `listed` | connected, idle, no call, no live capture, bud is master | `downloading` | `0x5A39` with offset from scratch file (0 on first run) |
| `listed` | entry `isProtected` | `protected` | User told; no command sent |
| `downloading` | `0x5A3A` chunk, offset matches | `downloading` | Decode per channel, append to scratch, persist `offsetBytes` |
| `downloading` | `0x5A3A` chunk, offset gap | `interrupted` | `0x5A39` cancel; user told; resumes later from the scratch file's length |
| `downloading` | `0x5A3A` channel 255 | `received` | — |
| `downloading` | 3 s silence, disconnect, `0x5A3B` any reason, call starts, app killed | `interrupted` | `0x5A39` cancel if the link is up; scratch kept |
| `received` | duration within tolerance of bud-reported length | `verified` | — |
| `received` | outside tolerance | `mismatch` | User told; scratch kept for a retry from 0 |
| `verified` | import job created with true time and identity | `importing` | 001 import job runs (paced, on-device) |
| `importing` | import job durable-persist callback | `imported` | Conversation exists; scratch deleted |
| `importing` | import job failed | `interrupted` | Retry re-uses scratch; never re-downloads |
| `imported` | link up, idle | `deletingOnBud` | `0x5A38` for (side, index) |
| `deletingOnBud` | ACK status 0 | `done` | — |
| `deletingOnBud` | ACK status ≠ 0 or timeout, < 3 attempts | `imported` | Retry next idle window |
| `deletingOnBud` | 3rd failure | `abandoned` | User told the bud still holds it |
| `interrupted` | connected, idle, no call | `downloading` | resume from `offsetBytes` |

## Invariants (tested)

1. `0x5A38` is only ever sent from `deletingOnBud`, which is only reachable from `imported`.
2. `downloading` is unreachable while any live capture session exists.
3. A job whose identity already reached `imported` is never created again (idempotency).
4. `offsetBytes` after restart equals the scratch file's decoded length converted back to
   G.722 bytes (÷16, halved in 8 kHz mode, doubled for two-way), never a value trusted from memory.
5. If `offsetBytes` > `lengthBytes`, the scratch is discarded and the job restarts from 0.
