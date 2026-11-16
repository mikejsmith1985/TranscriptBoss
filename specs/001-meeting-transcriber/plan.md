# Plan 001 — Meeting Transcriber

## Framework-first gate
- Speech-to-text: transformers.js (`@huggingface/transformers` 4.3.2) running Whisper via ONNX Runtime Web — no custom ML code.
- Capture: browser `getDisplayMedia` (system audio) + `getUserMedia` (mic) + `AudioWorklet`.
- Custom component justified: `AudioChunker` — no framework slices live streams into ≤30 s Whisper windows at quiet points.

## Architecture
| File | Role |
|---|---|
| `index.html` | Minimal UI: setup → recording (timer only) → done (export) |
| `app/main.js` | UI controller and session state |
| `app/capture.js` | Streams → worklet → per-speaker chunker → 16 kHz chunks |
| `app/recorder-worklet.js` | Audio-thread mono mixdown and batching |
| `app/transcriber-worker.js` | Loads Whisper once; transcribes chunks sequentially off the main thread |
| `app/transcript.js` | Pure helpers: resample, silence gate, cleanup, merge, format, Copilot prompt |
| `vendor/` | transformers.js bundle (unminified; the minified build trips GitHub's secret scanner with a false positive) + ORT wasm, self-hosted so corporate filters don't block a CDN |
| `check/` | Browser readiness check |

## Models
- Accurate: `onnx-community/whisper-small.en` — WebGPU: encoder fp16 (fp32 without shader-f16), decoder q4.
- Fast: `onnx-community/whisper-base.en`. CPU fallback uses q8 for both.

## Testing
- Unit: `npm test` (node:test) for `app/transcript.js`.
- End-to-end: verified in real Chrome with fake media (60 s system clip + mic clip), both models, CPU path. WebGPU path verified only by the browser check on the target laptop. Cypress suite not yet added.
