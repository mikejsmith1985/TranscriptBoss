// Unit tests for the pure transcript helpers (no browser, no model).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildCopilotPrompt, buildSegments, cleanSegmentText, computeRms, findQuietSplitIndex,
  formatTimestamp, formatTranscript, isSilent, mergeSegments, resampleToTarget,
} from '../app/transcript.js';

const SPEAKERS = { me: 'Mike', them: 'Others' };

test('resampleToTarget halves length when going from 32 kHz to 16 kHz and averages pairs', () => {
  const output = resampleToTarget(Float32Array.from([1, 3, 5, 7]), 32000, 16000);
  assert.deepEqual([...output], [2, 6]);
});

test('resampleToTarget returns a copy when rates already match', () => {
  const input = Float32Array.from([0.5, -0.5]);
  const output = resampleToTarget(input, 16000, 16000);
  assert.deepEqual([...output], [0.5, -0.5]);
  assert.notEqual(output, input);
});

test('computeRms and isSilent distinguish silence from speech-level audio', () => {
  assert.equal(computeRms(new Float32Array(0)), 0);
  assert.equal(isSilent(new Float32Array(100)), true);
  assert.equal(isSilent(new Float32Array(100).fill(0.1)), false);
});

test('findQuietSplitIndex picks the quietest window in range', () => {
  const samples = new Float32Array(100).fill(0.5);
  samples.fill(0, 60, 70);
  assert.equal(findQuietSplitIndex(samples, 40, 100, 10), 60);
});

test('findQuietSplitIndex falls back to the end when the range is too short', () => {
  assert.equal(findQuietSplitIndex(new Float32Array(50), 45, 50, 10), 50);
});

test('cleanSegmentText strips sound tags and drops hallucinated filler', () => {
  assert.equal(cleanSegmentText(' [BLANK_AUDIO] '), '');
  assert.equal(cleanSegmentText(' Thank you. '), '');
  assert.equal(cleanSegmentText('(music) Let us start the demo.'), 'Let us start the demo.');
});

test('buildSegments offsets timestamps by chunk start and drops empty text', () => {
  const result = { chunks: [{ timestamp: [1, 3], text: ' Hello team.' }, { timestamp: [3, 4], text: ' [BLANK_AUDIO]' }] };
  assert.deepEqual(buildSegments(result, 'them', 60, 30), [{ source: 'them', startSeconds: 61, endSeconds: 63, text: 'Hello team.' }]);
});

test('buildSegments handles a missing end timestamp on the final segment', () => {
  const result = { chunks: [{ timestamp: [2, null], text: 'Wrapping up.' }] };
  assert.equal(buildSegments(result, 'me', 0, 10)[0].endSeconds, 10);
});

test('mergeSegments orders by time and joins close same-speaker lines only', () => {
  const merged = mergeSegments([
    { source: 'me', startSeconds: 10, endSeconds: 12, text: 'Second.' },
    { source: 'me', startSeconds: 0, endSeconds: 9, text: 'First.' },
    { source: 'them', startSeconds: 13, endSeconds: 15, text: 'Reply.' },
  ]);
  assert.deepEqual(merged.map(segment => segment.text), ['First. Second.', 'Reply.']);
});

test('formatTimestamp pads hours, minutes and seconds', () => {
  assert.equal(formatTimestamp(3725.9), '01:02:05');
  assert.equal(formatTimestamp(-4), '00:00:00');
});

test('formatTranscript labels speakers and includes the meeting header', () => {
  const text = formatTranscript(
    [{ source: 'them', startSeconds: 5, endSeconds: 7, text: 'Can you own the API ticket?' },
      { source: 'me', startSeconds: 8, endSeconds: 9, text: 'Yes, by Friday.' }],
    { meetingTitle: 'Standup', startedAt: new Date('2026-11-16T14:00:00Z'), speakerNames: SPEAKERS },
  );
  assert.match(text, /^Meeting: Standup/);
  assert.match(text, /\[00:00:05\] Others: Can you own the API ticket\?/);
  assert.match(text, /\[00:00:08\] Mike: Yes, by Friday\./);
});

test('buildCopilotPrompt asks for action items and appends the transcript', () => {
  const prompt = buildCopilotPrompt('TRANSCRIPT BODY', SPEAKERS);
  assert.match(prompt, /Action items/);
  assert.match(prompt, /"Others" is several different people/);
  assert.ok(prompt.endsWith('TRANSCRIPT BODY'));
});
