// Pure helpers that shape raw audio and Whisper output into a clean, speaker-labelled transcript.

/** Whisper models expect 16 kHz mono audio. */
export const TARGET_SAMPLE_RATE = 16000;
/** Audio quieter than this (root-mean-square, 0-1 scale) is treated as silence and never sent to Whisper. */
export const SILENCE_RMS_THRESHOLD = 0.004;
/** Consecutive lines from the same speaker closer than this many seconds are joined into one paragraph. */
export const MERGE_GAP_SECONDS = 2.5;

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
// Whisper invents these phrases on near-silent audio; a segment that is only one of them is dropped.
const HALLUCINATED_PHRASES = new Set(['you', 'thank you', 'thanks for watching', 'bye']);
// Bracketed or parenthesised sound tags such as [BLANK_AUDIO] or (music).
const SOUND_TAG_PATTERN = /\[[^\]]*\]|\([^)]*\)/g;

/** Converts audio from the capture device's sample rate to Whisper's 16 kHz by averaging each output window. */
export function resampleToTarget(samples, fromRate, toRate = TARGET_SAMPLE_RATE) {
  if (fromRate === toRate) return Float32Array.from(samples);
  const ratio = fromRate / toRate;
  const outputLength = Math.floor(samples.length / ratio);
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const windowStart = Math.floor(i * ratio);
    const windowEnd = Math.min(samples.length, Math.max(windowStart + 1, Math.floor((i + 1) * ratio)));
    let total = 0;
    for (let j = windowStart; j < windowEnd; j++) total += samples[j];
    output[i] = total / (windowEnd - windowStart);
  }
  return output;
}

/** Measures loudness so silent stretches can be skipped instead of transcribed. */
export function computeRms(samples) {
  if (samples.length === 0) return 0;
  let sumOfSquares = 0;
  for (const sample of samples) sumOfSquares += sample * sample;
  return Math.sqrt(sumOfSquares / samples.length);
}

/** True when a chunk has no meaningful sound, so it should not be transcribed. */
export function isSilent(samples) {
  return computeRms(samples) < SILENCE_RMS_THRESHOLD;
}

/**
 * Finds the quietest point between two indexes so chunks are cut between words, not through them.
 * Returns the start index of the quietest window.
 */
export function findQuietSplitIndex(samples, minIndex, maxIndex, windowSize) {
  const searchEnd = Math.min(maxIndex, samples.length) - windowSize;
  if (searchEnd <= minIndex) return Math.min(maxIndex, samples.length);
  let quietestIndex = minIndex;
  let quietestEnergy = Infinity;
  for (let start = minIndex; start <= searchEnd; start += windowSize) {
    const energy = computeRms(samples.subarray(start, start + windowSize));
    if (energy < quietestEnergy) { quietestEnergy = energy; quietestIndex = start; }
  }
  return quietestIndex;
}

/** Removes sound tags and known Whisper hallucinations; returns an empty string when nothing real remains. */
export function cleanSegmentText(rawText) {
  const withoutTags = (rawText ?? '').replace(SOUND_TAG_PATTERN, ' ').replace(/\s+/g, ' ').trim();
  const comparable = withoutTags.toLowerCase().replace(/[.!?,]/g, '').trim();
  if (comparable === '' || HALLUCINATED_PHRASES.has(comparable)) return '';
  return withoutTags;
}

/** Turns one Whisper result into timeline segments placed at the chunk's position in the meeting. */
export function buildSegments(whisperResult, source, chunkStartSeconds, chunkDurationSeconds) {
  const timedChunks = whisperResult?.chunks?.length
    ? whisperResult.chunks
    : [{ timestamp: [0, chunkDurationSeconds], text: whisperResult?.text ?? '' }];
  return timedChunks
    .map(timedChunk => {
      const [relativeStart, relativeEnd] = timedChunk.timestamp ?? [0, chunkDurationSeconds];
      return {
        source,
        startSeconds: chunkStartSeconds + (relativeStart ?? 0),
        endSeconds: chunkStartSeconds + (relativeEnd ?? chunkDurationSeconds),
        text: cleanSegmentText(timedChunk.text),
      };
    })
    .filter(segment => segment.text !== '');
}

/** Orders segments by time and joins back-to-back lines from the same speaker. */
export function mergeSegments(segments) {
  const ordered = [...segments].sort((first, second) => first.startSeconds - second.startSeconds);
  const merged = [];
  for (const segment of ordered) {
    const previous = merged.at(-1);
    const isSameSpeakerContinuing = previous
      && previous.source === segment.source
      && segment.startSeconds - previous.endSeconds <= MERGE_GAP_SECONDS;
    if (isSameSpeakerContinuing) {
      previous.text = `${previous.text} ${segment.text}`;
      previous.endSeconds = Math.max(previous.endSeconds, segment.endSeconds);
    } else {
      merged.push({ ...segment });
    }
  }
  return merged;
}

/** Formats seconds as HH:MM:SS for transcript timestamps. */
export function formatTimestamp(totalSeconds) {
  const wholeSeconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(wholeSeconds / SECONDS_PER_HOUR);
  const minutes = Math.floor((wholeSeconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  const seconds = wholeSeconds % SECONDS_PER_MINUTE;
  return [hours, minutes, seconds].map(part => String(part).padStart(2, '0')).join(':');
}

/** Produces the plain-text transcript with a header, one timestamped line per speaker turn. */
export function formatTranscript(segments, { meetingTitle, startedAt, speakerNames }) {
  const header = [
    `Meeting: ${meetingTitle || 'Untitled meeting'}`,
    `Date: ${startedAt.toLocaleString()}`,
    `Speakers: "${speakerNames.me}" is the note-taker; "${speakerNames.them}" is everyone else on the call.`,
  ];
  const lines = mergeSegments(segments).map(segment => {
    const speakerLabel = segment.source === 'me' ? speakerNames.me : speakerNames.them;
    return `[${formatTimestamp(segment.startSeconds)}] ${speakerLabel}: ${segment.text}`;
  });
  return [...header, '', ...lines].join('\n');
}

/** Wraps the transcript in instructions that ask Microsoft Copilot for minutes and an action-item table. */
export function buildCopilotPrompt(transcriptText, speakerNames) {
  return [
    'You are helping a Scrum Master write meeting minutes. Using ONLY the transcript below, produce:',
    '1. Summary — 3 to 5 bullet points.',
    '2. Decisions made — bullet list; write "None recorded" if there were none.',
    '3. Action items — a table with columns: Action | Owner | Due date | Notes. Use names spoken in the meeting;',
    '   write "Unassigned" when no owner was stated and "Not stated" when no date was given. Do not guess.',
    '4. Open questions, risks and blockers.',
    `Note: "${speakerNames.them}" is several different people mixed together — identify individuals from context only when it is clear.`,
    'If something in the transcript is unclear or may have been misheard, flag it rather than guessing.',
    '',
    '--- TRANSCRIPT ---',
    transcriptText,
  ].join('\n');
}
