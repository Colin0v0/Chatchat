import { useCallback, useEffect, useRef, useState } from "react";

function resolveMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((item) => MediaRecorder.isTypeSupported(item)) ?? "";
}

function createRecorder(stream: MediaStream): MediaRecorder {
  const mimeType = resolveMimeType();
  if (mimeType) {
    return new MediaRecorder(stream, { mimeType });
  }
  return new MediaRecorder(stream);
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
    if (typeof window === "undefined" || !("MediaRecorder" in window)) {
      throw new Error("This browser does not support audio recording.");
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Audio input is not available in this browser.");
    }

    setRecordingError(null);
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
    recorder.start();
    setIsRecording(true);
  }, [isRecording]);

  const stopRecording = useCallback(async () => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      setIsRecording(false);
      cleanupStream();
      return null;
    }

    return new Promise<Blob | null>((resolve) => {
      const handleStop = () => {
        recorderRef.current = null;
        setIsRecording(false);
        cleanupStream();

        if (shouldDiscardRef.current || chunksRef.current.length === 0) {
          chunksRef.current = [];
          shouldDiscardRef.current = false;
          resolve(null);
          return;
        }

        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        chunksRef.current = [];
        resolve(blob);
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
