// Runs on the browser's audio thread: mixes each input to mono and hands batches of samples to the page.

// Sending every 128-sample render quantum would flood the page; batch roughly a quarter second instead.
const BATCH_SIZE_SAMPLES = 12288;

/** Collects mono audio frames and posts them to the main thread in batches. */
class RecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.batch = new Float32Array(BATCH_SIZE_SAMPLES);
    this.batchLength = 0;
    this.port.onmessage = event => { if (event.data === 'flush') this.postBatch(); };
  }

  /** Sends whatever has been collected so far and starts a new batch. */
  postBatch() {
    if (this.batchLength === 0) return;
    this.port.postMessage(this.batch.slice(0, this.batchLength));
    this.batchLength = 0;
  }

  /** Called by the browser for every 128-sample block of audio. */
  process(inputs) {
    const channels = inputs[0];
    if (!channels || channels.length === 0) return true;
    const frameCount = channels[0].length;
    for (let i = 0; i < frameCount; i++) {
      let mixed = 0;
      for (const channel of channels) mixed += channel[i];
      this.batch[this.batchLength++] = mixed / channels.length;
      if (this.batchLength === BATCH_SIZE_SAMPLES) this.postBatch();
    }
    return true;
  }
}

registerProcessor('recorder-processor', RecorderProcessor);
