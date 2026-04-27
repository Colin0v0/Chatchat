import { useCallback, useEffect, useRef, useState } from "react";

export interface RecordingCaptureResult {
  audioBlob: Blob | null;
}

const MEDIA_RECORDER_AUDIO_BITS_PER_SECOND = 128_000;
const MIN_RELIABLE_MEDIA_RECORDER_BYTES = 1024;
const MIN_PCM_CAPTURE_DURATION_MS = 250;
const MIN_PCM_RMS_DBFS = -65;
const PCM_CAPTURE_WORKLET_NAME = "chatchat-pcm-capture";
const PCM_CAPTURE_WORKLET_SOURCE = `
class ChatchatPcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (input && input.length > 0) {
      const chunk = new Float32Array(input.length);
      chunk.set(input);
      this.port.postMessage(chunk, [chunk.buffer]);
    }
    return true;
  }
}

registerProcessor("${PCM_CAPTURE_WORKLET_NAME}", ChatchatPcmCaptureProcessor);
`;

interface PcmCaptureResult {
  audioBlob: Blob | null;
  durationMs: number;
  rmsDbfs: number;
}

interface PcmCapture {
  stop: () => Promise<PcmCaptureResult>;
}

type WindowWithWebkitAudioContext = Window &
  typeof globalThis & {
    webkitAudioContext?: typeof AudioContext;
  };

function resolveMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((item) => MediaRecorder.isTypeSupported(item)) ?? "";
}

function createRecorder(stream: MediaStream): MediaRecorder {
  const mimeType = resolveMimeType();
  const optionCandidates: MediaRecorderOptions[] = mimeType
    ? [
        { mimeType, audioBitsPerSecond: MEDIA_RECORDER_AUDIO_BITS_PER_SECOND },
        { mimeType },
        { audioBitsPerSecond: MEDIA_RECORDER_AUDIO_BITS_PER_SECOND },
      ]
    : [{ audioBitsPerSecond: MEDIA_RECORDER_AUDIO_BITS_PER_SECOND }];

  for (const options of optionCandidates) {
    try {
      return new MediaRecorder(stream, options);
    } catch {
      // Some browsers report support but still fail to construct recorder with options.
    }
  }

  return new MediaRecorder(stream);
}

function createRawAudioConstraints(): MediaTrackConstraints | boolean {
  const supported = navigator.mediaDevices.getSupportedConstraints?.() ?? {};
  const constraints: MediaTrackConstraints = {};

  if (supported.channelCount) {
    constraints.channelCount = { ideal: 1 };
  }
  if (supported.echoCancellation) {
    constraints.echoCancellation = { ideal: false };
  }
  if (supported.noiseSuppression) {
    constraints.noiseSuppression = { ideal: false };
  }
  if (supported.autoGainControl) {
    constraints.autoGainControl = { ideal: false };
  }
  if (supported.sampleRate) {
    constraints.sampleRate = { ideal: 48000 };
  }
  if (supported.sampleSize) {
    constraints.sampleSize = { ideal: 16 };
  }

  return Object.keys(constraints).length > 0 ? constraints : true;
}

async function getMicrophoneStream(): Promise<MediaStream> {
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: createRawAudioConstraints(),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "OverconstrainedError") {
      return navigator.mediaDevices.getUserMedia({ audio: true });
    }
    throw error;
  }
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function encodePcmWav(chunks: Float32Array[], sampleRate: number): Blob | null {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  if (sampleCount <= 0 || sampleRate <= 0) {
    return null;
  }

  const bytesPerSample = 2;
  const channelCount = 1;
  const dataSize = sampleCount * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channelCount, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * channelCount * bytesPerSample, true);
  view.setUint16(32, channelCount * bytesPerSample, true);
  view.setUint16(34, bytesPerSample * 8, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (const chunk of chunks) {
    for (let index = 0; index < chunk.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, chunk[index]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += bytesPerSample;
    }
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function appendPcmChunk(
  chunk: Float32Array,
  stats: { sampleCount: number; squareSum: number },
  chunks: Float32Array[],
) {
  chunks.push(chunk);
  stats.sampleCount += chunk.length;
  for (let index = 0; index < chunk.length; index += 1) {
    stats.squareSum += chunk[index] * chunk[index];
  }
}

function finishPcmCapture(
  chunks: Float32Array[],
  stats: { sampleCount: number; squareSum: number },
  sampleRate: number,
): PcmCaptureResult {
  const durationMs =
    stats.sampleCount > 0 ? Math.round((stats.sampleCount / sampleRate) * 1000) : 0;
  const rms = stats.sampleCount > 0 ? Math.sqrt(stats.squareSum / stats.sampleCount) : 0;
  const rmsDbfs = rms > 0 ? 20 * Math.log10(rms) : Number.NEGATIVE_INFINITY;
  return {
    audioBlob: encodePcmWav(chunks, sampleRate),
    durationMs,
    rmsDbfs,
  };
}

function createAudioContext(AudioContextCtor: typeof AudioContext): AudioContext {
  try {
    return new AudioContextCtor({ sampleRate: 48000 });
  } catch {
    return new AudioContextCtor();
  }
}

async function closeAudioContext(context: AudioContext) {
  if (context.state !== "closed") {
    try {
      await context.close();
    } catch {
      // Closing can reject if the browser already tore the context down.
    }
  }
}

async function installPcmCaptureWorklet(context: AudioContext) {
  const moduleBlob = new Blob([PCM_CAPTURE_WORKLET_SOURCE], { type: "text/javascript" });
  const moduleUrl = URL.createObjectURL(moduleBlob);
  try {
    await context.audioWorklet.addModule(moduleUrl);
  } finally {
    URL.revokeObjectURL(moduleUrl);
  }
}

async function createAudioWorkletPcmCapture(
  context: AudioContext,
  stream: MediaStream,
): Promise<PcmCapture> {
  await installPcmCaptureWorklet(context);

  const source = context.createMediaStreamSource(stream);
  const processor = new AudioWorkletNode(context, PCM_CAPTURE_WORKLET_NAME, {
    numberOfInputs: 1,
    numberOfOutputs: 1,
  });
  const sink = context.createGain();
  const chunks: Float32Array[] = [];
  const stats = { sampleCount: 0, squareSum: 0 };
  let stopped = false;

  sink.gain.value = 0;
  processor.port.onmessage = (event: MessageEvent<Float32Array | ArrayBuffer>) => {
    if (stopped) {
      return;
    }
    const chunk =
      event.data instanceof Float32Array
        ? event.data
        : event.data instanceof ArrayBuffer
          ? new Float32Array(event.data)
          : null;
    if (chunk) {
      appendPcmChunk(chunk, stats, chunks);
    }
  };

  source.connect(processor);
  processor.connect(sink);
  sink.connect(context.destination);
  await context.resume();

  return {
    stop: async () => {
      stopped = true;
      processor.port.onmessage = null;
      processor.port.close();
      try {
        source.disconnect();
        processor.disconnect();
        sink.disconnect();
      } catch {
        // Already disconnected.
      }
      await closeAudioContext(context);
      return finishPcmCapture(chunks, stats, context.sampleRate);
    },
  };
}

async function createScriptProcessorPcmCapture(
  context: AudioContext,
  stream: MediaStream,
): Promise<PcmCapture> {
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const sink = context.createGain();
    const chunks: Float32Array[] = [];
    const stats = { sampleCount: 0, squareSum: 0 };
    let stopped = false;

    sink.gain.value = 0;
    processor.onaudioprocess = (event) => {
      if (stopped) {
        return;
      }
      const input = event.inputBuffer.getChannelData(0);
      const chunk = new Float32Array(input.length);
      chunk.set(input);
      appendPcmChunk(chunk, stats, chunks);
    };

    source.connect(processor);
    processor.connect(sink);
    sink.connect(context.destination);
    await context.resume();

    return {
      stop: async () => {
        stopped = true;
        processor.onaudioprocess = null;
        try {
          source.disconnect();
          processor.disconnect();
          sink.disconnect();
        } catch {
          // Already disconnected.
        }
        await closeAudioContext(context);

        return finishPcmCapture(chunks, stats, context.sampleRate);
      },
    };
}

async function createPcmCapture(stream: MediaStream): Promise<PcmCapture | null> {
  const AudioContextCtor =
    window.AudioContext ?? (window as WindowWithWebkitAudioContext).webkitAudioContext;
  if (!AudioContextCtor) {
    return null;
  }

  let audioContext: AudioContext | null = null;
  try {
    audioContext = createAudioContext(AudioContextCtor);
    if (audioContext.audioWorklet) {
      try {
        return await createAudioWorkletPcmCapture(audioContext, stream);
      } catch {
        await closeAudioContext(audioContext);
        audioContext = null;
      }
    }

    audioContext = createAudioContext(AudioContextCtor);
    return await createScriptProcessorPcmCapture(audioContext, stream);
  } catch {
    if (audioContext && audioContext.state !== "closed") {
      await closeAudioContext(audioContext);
    }
    return null;
  }
}

function isMicrosoftEdge(): boolean {
  if (typeof navigator === "undefined") {
    return false;
  }
  return /\sedg(a|ios)?\//i.test(navigator.userAgent);
}

function isAudiblePcmCapture(result: PcmCaptureResult | null): result is PcmCaptureResult {
  return (
    result !== null
    && result.audioBlob !== null
    && result.durationMs >= MIN_PCM_CAPTURE_DURATION_MS
    && result.rmsDbfs >= MIN_PCM_RMS_DBFS
  );
}

function chooseCapturedAudioBlob(
  mediaBlob: Blob | null,
  pcmCapture: PcmCaptureResult | null,
): Blob | null {
  const reliableMediaBlob =
    mediaBlob && mediaBlob.size >= MIN_RELIABLE_MEDIA_RECORDER_BYTES ? mediaBlob : null;

  if (isAudiblePcmCapture(pcmCapture) && (isMicrosoftEdge() || !reliableMediaBlob)) {
    return pcmCapture.audioBlob;
  }

  if (reliableMediaBlob) {
    return reliableMediaBlob;
  }

  return isAudiblePcmCapture(pcmCapture) ? pcmCapture.audioBlob : null;
}

function toRecordingError(error: unknown): string {
  if (!(error instanceof DOMException)) {
    return "Failed to access the microphone.";
  }

  switch (error.name) {
    case "NotAllowedError":
      return "Microphone permission was denied.";
    case "NotFoundError":
      return "No microphone was found on this device.";
    case "NotReadableError":
      return "The microphone is busy or unavailable.";
    case "SecurityError":
      return "Voice input requires HTTPS or localhost.";
    case "OverconstrainedError":
      return "The selected microphone settings are not supported.";
    default:
      return "Failed to access the microphone.";
  }
}

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const pcmCaptureRef = useRef<PcmCapture | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const shouldDiscardRef = useRef(false);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const startRecording = useCallback(async () => {
    if (isRecording) {
      return;
    }
    if (typeof window === "undefined" || !window.isSecureContext) {
      throw new Error("Voice input requires HTTPS or localhost.");
    }
    if (!("MediaRecorder" in window)) {
      throw new Error("This browser does not support audio recording.");
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone access is not available in this browser.");
    }

    setRecordingError(null);

    let stream: MediaStream;
    try {
      stream = await getMicrophoneStream();
    } catch (error) {
      const message = toRecordingError(error);
      setRecordingError(message);
      throw new Error(message);
    }

    streamRef.current = stream;
    let recorder: MediaRecorder;
    let pcmCapture: PcmCapture | null = null;
    try {
      recorder = createRecorder(stream);
      pcmCapture = await createPcmCapture(stream);
    } catch (error) {
      cleanupStream();
      const message =
        error instanceof Error ? error.message : "This browser does not support audio recording.";
      setRecordingError(message);
      throw new Error(message);
    }

    chunksRef.current = [];
    shouldDiscardRef.current = false;

    recorder.addEventListener("dataavailable", (event: BlobEvent) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    });
    recorder.addEventListener("error", () => {
      setRecordingError("Audio recording failed.");
    });

    recorderRef.current = recorder;
    pcmCaptureRef.current = pcmCapture;
    try {
      recorder.start(250);
    } catch (error) {
      recorderRef.current = null;
      pcmCaptureRef.current = null;
      if (pcmCapture) {
        await pcmCapture.stop();
      }
      cleanupStream();
      const message = error instanceof Error ? error.message : "Audio recording failed to start.";
      setRecordingError(message);
      throw new Error(message);
    }
    setIsRecording(true);
  }, [cleanupStream, isRecording]);

  const stopRecording = useCallback(async (): Promise<RecordingCaptureResult> => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      recorderRef.current = null;
      setIsRecording(false);
      const pcmCapture = pcmCaptureRef.current;
      pcmCaptureRef.current = null;
      if (pcmCapture) {
        await pcmCapture.stop();
      }
      cleanupStream();
      shouldDiscardRef.current = false;
      chunksRef.current = [];
      return { audioBlob: null };
    }

    return new Promise<RecordingCaptureResult>((resolve) => {
      const handleStop = async () => {
        const pcmCapture = pcmCaptureRef.current;
        pcmCaptureRef.current = null;
        const pcmCaptureResult = pcmCapture ? await pcmCapture.stop() : null;
        recorderRef.current = null;
        setIsRecording(false);
        cleanupStream();

        if (shouldDiscardRef.current) {
          shouldDiscardRef.current = false;
          chunksRef.current = [];
          resolve({ audioBlob: null });
          return;
        }

        const mediaBlob =
          chunksRef.current.length > 0
            ? new Blob(chunksRef.current, {
                type: recorder.mimeType || "audio/webm",
              })
            : null;
        chunksRef.current = [];
        const audioBlob = chooseCapturedAudioBlob(mediaBlob, pcmCaptureResult);
        resolve({ audioBlob });
      };

      recorder.addEventListener("stop", handleStop, { once: true });
      try {
        recorder.requestData();
      } catch {
        // Ignore: not all recorder states support requestData.
      }
      recorder.stop();
    });
  }, [cleanupStream]);

  const cancelRecording = useCallback(() => {
    shouldDiscardRef.current = true;
    void stopRecording();
  }, [stopRecording]);

  useEffect(() => {
    return () => {
      shouldDiscardRef.current = true;
      void stopRecording();
    };
  }, [stopRecording]);

  return {
    cancelRecording,
    isRecording,
    recordingError,
    startRecording,
    stopRecording,
  };
}
