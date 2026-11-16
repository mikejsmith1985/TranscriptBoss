// Background worker that loads Whisper once and transcribes audio chunks in order, entirely on this computer.

import { env, pipeline } from '../vendor/transformers.js';
import { TARGET_SAMPLE_RATE } from './transcript.js';

/** Speech models offered in the app; both are English-only, which is faster and more accurate for English meetings. */
const MODEL_OPTIONS = {
  accurate: 'onnx-community/whisper-small.en',
  fast: 'onnx-community/whisper-base.en',
};

// The speech engine's runtime files are served from this site instead of a public CDN, so corporate filters don't block them.
env.allowLocalModels = false;
env.backends.onnx.wasm.wasmPaths = {
  mjs: new URL('../vendor/ort-wasm-simd-threaded.asyncify.mjs', import.meta.url).href,
  wasm: new URL('../vendor/ort-wasm-simd-threaded.asyncify.wasm', import.meta.url).href,
};

let transcriber = null;
let queue = Promise.resolve();

/** Picks GPU when available (much faster); half-precision only when the GPU supports it. */
async function chooseRuntime() {
  const adapter = await navigator.gpu?.requestAdapter?.().catch(() => null);
  if (!adapter) return { device: 'wasm', dtype: { encoder_model: 'q8', decoder_model_merged: 'q8' } };
  const encoderPrecision = adapter.features.has('shader-f16') ? 'fp16' : 'fp32';
  return { device: 'webgpu', dtype: { encoder_model: encoderPrecision, decoder_model_merged: 'q4' } };
}

/** Downloads (first time only; the browser caches it) and prepares the chosen model. */
async function loadModel(modelKey) {
  const modelId = MODEL_OPTIONS[modelKey] ?? MODEL_OPTIONS.accurate;
  const runtime = await chooseRuntime();
  transcriber = await pipeline('automatic-speech-recognition', modelId, {
    ...runtime,
    progress_callback: progress => {
      if (progress.status === 'progress') self.postMessage({ type: 'progress', file: progress.file, loaded: progress.loaded, total: progress.total });
    },
  });
  // A one-second silent warm-up compiles the GPU shaders now rather than during the first real chunk.
  await transcriber(new Float32Array(TARGET_SAMPLE_RATE));
  self.postMessage({ type: 'ready', device: runtime.device, modelId });
}

/** Transcribes one chunk with segment timestamps and reports the result. */
async function transcribeChunk({ chunkId, samples }) {
  const result = await transcriber(samples, { return_timestamps: true });
  self.postMessage({ type: 'result', chunkId, result: { text: result.text, chunks: result.chunks } });
}

self.onmessage = event => {
  const message = event.data;
  // Chained so chunks are always processed one at a time, in arrival order.
  queue = queue.then(async () => {
    try {
      if (message.type === 'load') await loadModel(message.modelKey);
      if (message.type === 'transcribe') await transcribeChunk(message);
    } catch (error) {
      self.postMessage({ type: 'error', chunkId: message.chunkId, message: error?.message ?? String(error) });
    }
  });
};
