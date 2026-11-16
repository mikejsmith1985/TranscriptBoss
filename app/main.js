// Page controller: wires the buttons to audio capture, the background transcriber, and the Copilot export.

import { startCapture } from './capture.js';
import { buildCopilotPrompt, buildSegments, formatTimestamp, formatTranscript } from './transcript.js';

const STORAGE_KEYS = { name: 'transcriptboss.name', model: 'transcriptboss.model' };
const ONE_SECOND_MS = 1000;
const PERCENT = 100;
const COPIED_FEEDBACK_MS = 2000;

const elements = Object.fromEntries(
  ['setupPanel', 'recordingPanel', 'donePanel', 'modelStatus', 'meetingTitle', 'yourName', 'modelChoice',
    'startButton', 'stopButton', 'elapsed', 'queueStatus', 'errorMessage', 'transcriptOutput',
    'copyButton', 'downloadButton', 'newButton'].map(id => [id, document.getElementById(id)]),
);

const worker = new Worker(new URL('./transcriber-worker.js', import.meta.url), { type: 'module' });
const session = { capture: null, startedAt: null, timerId: null, chunks: new Map(), segments: [], nextChunkId: 0, isRecording: false, isStopping: false, hasUnsavedTranscript: false };
const downloadProgress = new Map();

/** Reads a saved setting; storage can be unavailable on locked-down browsers, so failures fall back to the default. */
function readSetting(key, fallback) {
  try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; }
}

/** Saves a setting when storage is available. */
function writeSetting(key, value) {
  try { localStorage.setItem(key, value); } catch { /* settings simply won't persist */ }
}

/** Shows exactly one of the three panels. */
function showPanel(panelName) {
  ['setupPanel', 'recordingPanel', 'donePanel'].forEach(name => { elements[name].hidden = name !== panelName; });
}

/** Displays an error under the controls. */
function showError(message) {
  elements.errorMessage.textContent = message;
  elements.errorMessage.hidden = !message;
}

/** Updates the small "chunks waiting" line so you know when the transcript will be ready. */
function updateQueueStatus() {
  const waiting = session.chunks.size;
  elements.queueStatus.textContent = waiting === 0 ? 'Up to date' : `${waiting} chunk${waiting === 1 ? '' : 's'} waiting`;
  const isCaptureFinished = !session.isRecording && !session.isStopping;
  if (isCaptureFinished && waiting === 0 && session.startedAt) finishTranscript();
}

/** Shows overall model download progress across all model files. */
function reportDownload({ file, loaded, total }) {
  downloadProgress.set(file, { loaded, total });
  let loadedBytes = 0;
  let totalBytes = 0;
  downloadProgress.forEach(entry => { loadedBytes += entry.loaded ?? 0; totalBytes += entry.total ?? 0; });
  const percent = totalBytes ? Math.floor((loadedBytes / totalBytes) * PERCENT) : 0;
  elements.modelStatus.textContent = `Preparing speech model (first time only)… ${percent}%`;
}

/** Records a finished chunk's text on the meeting timeline. */
function acceptResult(chunkId, result) {
  const chunk = session.chunks.get(chunkId);
  if (!chunk) return;
  session.segments.push(...buildSegments(result, chunk.source, chunk.startSeconds, chunk.durationSeconds));
  session.chunks.delete(chunkId);
  updateQueueStatus();
}

worker.onmessage = event => {
  const message = event.data;
  if (message.type === 'progress') reportDownload(message);
  if (message.type === 'ready') elements.modelStatus.textContent = `Speech model ready (${message.device === 'webgpu' ? 'GPU' : 'CPU'}).`;
  if (message.type === 'result') acceptResult(message.chunkId, message.result);
  if (message.type === 'error') {
    showError(`Transcription problem: ${message.message}`);
    if (message.chunkId !== undefined) { session.chunks.delete(message.chunkId); updateQueueStatus(); }
  }
};

/** Sends a captured chunk to the background transcriber. */
function queueChunk(chunk) {
  const chunkId = session.nextChunkId++;
  session.chunks.set(chunkId, { source: chunk.source, startSeconds: chunk.startSeconds, durationSeconds: chunk.durationSeconds });
  worker.postMessage({ type: 'transcribe', chunkId, samples: chunk.samples }, [chunk.samples.buffer]);
  updateQueueStatus();
}

/** Begins a meeting: opens the share picker, then records quietly in the background. */
async function startMeeting() {
  showError('');
  writeSetting(STORAGE_KEYS.name, elements.yourName.value.trim());
  try {
    session.capture = await startCapture({ onChunk: queueChunk, onEnded: stopMeeting });
  } catch (error) {
    showError(error?.name === 'NotAllowedError' ? 'Screen share was cancelled.' : error.message);
    return;
  }
  Object.assign(session, { startedAt: new Date(), segments: [], isRecording: true, hasUnsavedTranscript: true });
  if (!session.capture.hasMicrophone) showError('Microphone not available — only other people will be transcribed.');
  showPanel('recordingPanel');
  const tickElapsed = () => { elements.elapsed.textContent = formatTimestamp((Date.now() - session.startedAt) / ONE_SECOND_MS); };
  tickElapsed();
  session.timerId = setInterval(tickElapsed, ONE_SECOND_MS);
  updateQueueStatus();
}

/** Stops recording; the transcript appears once the last chunks are processed. */
async function stopMeeting() {
  if (!session.isRecording) return;
  // isStopping holds the transcript back until the final partial chunk has been queued.
  Object.assign(session, { isRecording: false, isStopping: true });
  clearInterval(session.timerId);
  elements.stopButton.disabled = true;
  elements.stopButton.textContent = 'Finishing transcript…';
  await session.capture.stop();
  session.isStopping = false;
  updateQueueStatus();
}

/** Speaker labels used in the transcript, with the user's own name when provided. */
function speakerNames() {
  return { me: elements.yourName.value.trim() || 'Me', them: 'Others' };
}

/** Builds the final transcript and shows the export buttons. */
function finishTranscript() {
  elements.transcriptOutput.value = formatTranscript(session.segments, {
    meetingTitle: elements.meetingTitle.value.trim(), startedAt: session.startedAt, speakerNames: speakerNames(),
  });
  showPanel('donePanel');
}

/** Copies the Copilot-ready prompt and transcript to the clipboard. */
async function copyForCopilot() {
  await navigator.clipboard.writeText(buildCopilotPrompt(elements.transcriptOutput.value, speakerNames()));
  session.hasUnsavedTranscript = false;
  elements.copyButton.textContent = 'Copied ✓';
  setTimeout(() => { elements.copyButton.textContent = 'Copy for Copilot'; }, COPIED_FEEDBACK_MS);
}

/** Saves the prompt and transcript as a .txt file, for meetings too long to paste into Copilot. */
function downloadTranscript() {
  const content = buildCopilotPrompt(elements.transcriptOutput.value, speakerNames());
  const safeTitle = (elements.meetingTitle.value.trim() || 'meeting').replace(/[^a-z0-9-_ ]/gi, '').replace(/\s+/g, '-');
  const datePart = session.startedAt.toISOString().slice(0, 10);
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([content], { type: 'text/plain' }));
  link.download = `${datePart}-${safeTitle}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
  session.hasUnsavedTranscript = false;
}

/** Clears everything for the next meeting. */
function resetForNewMeeting() {
  if (session.hasUnsavedTranscript && !confirm('This transcript has not been copied or downloaded. Discard it?')) return;
  Object.assign(session, { startedAt: null, segments: [], hasUnsavedTranscript: false });
  elements.meetingTitle.value = '';
  elements.transcriptOutput.value = '';
  elements.stopButton.disabled = false;
  elements.stopButton.textContent = 'Stop';
  showError('');
  showPanel('setupPanel');
}

elements.yourName.value = readSetting(STORAGE_KEYS.name, '');
elements.modelChoice.value = readSetting(STORAGE_KEYS.model, 'accurate');
elements.modelChoice.addEventListener('change', () => { writeSetting(STORAGE_KEYS.model, elements.modelChoice.value); location.reload(); });
elements.startButton.addEventListener('click', startMeeting);
elements.stopButton.addEventListener('click', stopMeeting);
elements.copyButton.addEventListener('click', copyForCopilot);
elements.downloadButton.addEventListener('click', downloadTranscript);
elements.newButton.addEventListener('click', resetForNewMeeting);
// Audio and transcripts live only in this tab, so warn before closing it with unsaved work.
window.addEventListener('beforeunload', event => { if (session.isRecording || session.hasUnsavedTranscript) event.preventDefault(); });
worker.postMessage({ type: 'load', modelKey: elements.modelChoice.value });
