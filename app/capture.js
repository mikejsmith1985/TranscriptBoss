// Captures the meeting's system audio (other people) and the microphone (you) and slices each into ~30 s chunks.

import { TARGET_SAMPLE_RATE, findQuietSplitIndex, isSilent, resampleToTarget } from './transcript.js';

/** Whisper reads at most 30 s at a time, so chunks never exceed this. */
const MAX_CHUNK_SECONDS = 30;
/** Chunks are cut at the quietest moment between this point and the 30 s limit, to avoid splitting words. */
const MIN_CHUNK_SECONDS = 26;
/** Length of the window used to find a quiet moment to cut at. */
const QUIET_WINDOW_SECONDS = 0.1;
/** Trailing audio shorter than this when recording stops is ignored. */
const MIN_FINAL_CHUNK_SECONDS = 0.5;
/** Time allowed for the audio thread to hand over its last batch when recording stops. */
const FINAL_BATCH_WAIT_MS = 300;
const WORKLET_URL = new URL('./recorder-worklet.js', import.meta.url);

/** Accumulates audio for one speaker source and emits Whisper-sized chunks. */
class AudioChunker {
  constructor(source, sampleRate, onChunk) {
    this.source = source;
    this.sampleRate = sampleRate;
    this.onChunk = onChunk;
    this.pending = [];
    this.pendingLength = 0;
    this.emittedSamples = 0;
  }

  /** Adds newly captured samples and emits a chunk once 30 s have built up. */
  addSamples(samples) {
    this.pending.push(samples);
    this.pendingLength += samples.length;
    if (this.pendingLength >= MAX_CHUNK_SECONDS * this.sampleRate) this.emitChunk(false);
  }

  /** Emits whatever audio remains, used when recording stops. */
  flush() {
    if (this.pendingLength >= MIN_FINAL_CHUNK_SECONDS * this.sampleRate) this.emitChunk(true);
    this.pending = [];
    this.pendingLength = 0;
  }

  /** Cuts the buffered audio at a quiet point, resamples it, and hands it on unless it is silent. */
  emitChunk(isFinal) {
    const allSamples = new Float32Array(this.pendingLength);
    let writeOffset = 0;
    for (const part of this.pending) { allSamples.set(part, writeOffset); writeOffset += part.length; }
    const splitIndex = isFinal ? allSamples.length : findQuietSplitIndex(
      allSamples,
      Math.floor(MIN_CHUNK_SECONDS * this.sampleRate),
      Math.floor(MAX_CHUNK_SECONDS * this.sampleRate),
      Math.floor(QUIET_WINDOW_SECONDS * this.sampleRate),
    );
    const chunkSamples = allSamples.subarray(0, splitIndex);
    const remainder = allSamples.slice(splitIndex);
    this.pending = remainder.length ? [remainder] : [];
    this.pendingLength = remainder.length;
    const startSeconds = this.emittedSamples / this.sampleRate;
    this.emittedSamples += chunkSamples.length;
    const resampled = resampleToTarget(chunkSamples, this.sampleRate, TARGET_SAMPLE_RATE);
    if (isSilent(resampled)) return;
    this.onChunk({ source: this.source, startSeconds, durationSeconds: resampled.length / TARGET_SAMPLE_RATE, samples: resampled });
  }
}

/** Asks Chrome for screen share with system audio; the video is required by Chrome but never shown or stored. */
async function requestSystemAudio() {
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: 1 },
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    systemAudio: 'include',
    selfBrowserSurface: 'exclude',
    surfaceSwitching: 'exclude',
  });
  if (stream.getAudioTracks().length === 0) {
    stream.getTracks().forEach(track => track.stop());
    throw new Error('No system audio. Choose "Entire screen" and turn on "Also share system audio".');
  }
  return stream;
}

/** Asks for the microphone; returns null if the user declines so recording can continue without it. */
async function requestMicrophone() {
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch {
    return null;
  }
}

/** Routes one audio stream through the recorder worklet into a chunker for that speaker. */
function connectSource(audioContext, stream, source, onChunk, silentSink) {
  const chunker = new AudioChunker(source, audioContext.sampleRate, onChunk);
  const workletNode = new AudioWorkletNode(audioContext, 'recorder-processor');
  workletNode.port.onmessage = event => chunker.addSamples(event.data);
  audioContext.createMediaStreamSource(stream).connect(workletNode);
  workletNode.connect(silentSink);
  return { chunker, workletNode };
}

/**
 * Starts capturing. Calls onChunk for every speech chunk and onEnded if Chrome's sharing is stopped externally.
 * Returns a controller with stop() and whether the microphone was included.
 */
export async function startCapture({ onChunk, onEnded }) {
  const systemStream = await requestSystemAudio();
  const microphoneStream = await requestMicrophone();
  const audioContext = new AudioContext();
  await audioContext.audioWorklet.addModule(WORKLET_URL);
  // A muted gain keeps the audio graph running without playing anything back through the speakers.
  const silentSink = audioContext.createGain();
  silentSink.gain.value = 0;
  silentSink.connect(audioContext.destination);
  const connections = [connectSource(audioContext, systemStream, 'them', onChunk, silentSink)];
  if (microphoneStream) connections.push(connectSource(audioContext, microphoneStream, 'me', onChunk, silentSink));

  let isStopped = false;
  const stop = async () => {
    if (isStopped) return;
    isStopped = true;
    connections.forEach(connection => connection.workletNode.port.postMessage('flush'));
    // Give the audio thread a moment to deliver its final batch before closing.
    await new Promise(resolve => setTimeout(resolve, FINAL_BATCH_WAIT_MS));
    connections.forEach(connection => connection.chunker.flush());
    [systemStream, microphoneStream].filter(Boolean).forEach(stream => stream.getTracks().forEach(track => track.stop()));
    await audioContext.close();
  };
  systemStream.getAudioTracks()[0].addEventListener('ended', () => { if (!isStopped) onEnded(); });
  systemStream.getVideoTracks()[0]?.addEventListener('ended', () => { if (!isStopped) onEnded(); });
  return { stop, hasMicrophone: Boolean(microphoneStream) };
}
