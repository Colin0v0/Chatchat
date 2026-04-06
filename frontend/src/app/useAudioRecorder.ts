import { useCallback, useEffect, useRef, useState } from "react";

export interface RecordingCaptureResult {
  audioBlob: Blob | null;
}

function resolveMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"];
  return candidates.find((item) => MediaRecorder.isTypeSupported(item)) ?? "";
}

function createRecorder(stream: MediaStream): MediaRecorder {
  const mimeType = resolveMimeType();
  return mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
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
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    } catch (error) {
      const message = toRecordingError(error);
      setRecordingError(message);
      throw new Error(message);
    }

    const recorder = createRecorder(stream);
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
    streamRef.current = stream;
    recorder.start(250);
    setIsRecording(true);
  }, [isRecording]);

  const stopRecording = useCallback(async (): Promise<RecordingCaptureResult> => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      recorderRef.current = null;
      setIsRecording(false);
      cleanupStream();
      shouldDiscardRef.current = false;
      chunksRef.current = [];
      return { audioBlob: null };
    }

    return new Promise<RecordingCaptureResult>((resolve) => {
      const handleStop = () => {
        recorderRef.current = null;
        setIsRecording(false);
        cleanupStream();

        if (shouldDiscardRef.current) {
          shouldDiscardRef.current = false;
          chunksRef.current = [];
          resolve({ audioBlob: null });
          return;
        }

        const audioBlob =
          chunksRef.current.length > 0
            ? new Blob(chunksRef.current, {
                type: recorder.mimeType || "audio/webm",
              })
            : null;
        chunksRef.current = [];
        resolve({ audioBlob });
      };

      recorder.addEventListener("stop", handleStop, { once: true });
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
