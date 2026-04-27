const SPEECH_UNLOCK_TEXT = "。";

let speechUnlockPending = false;
let speechUnlockReady = false;

export function canUseSpeechSynthesis() {
  return (
    typeof window !== "undefined"
    && "speechSynthesis" in window
    && "SpeechSynthesisUtterance" in window
  );
}

export function resumeSpeechSynthesis() {
  if (!canUseSpeechSynthesis()) {
    return false;
  }

  try {
    window.speechSynthesis.resume();
    return true;
  } catch {
    return false;
  }
}

export function unlockSpeechSynthesis() {
  if (!canUseSpeechSynthesis()) {
    return false;
  }

  resumeSpeechSynthesis();
  if (speechUnlockReady || speechUnlockPending) {
    return true;
  }

  try {
    const utterance = new SpeechSynthesisUtterance(SPEECH_UNLOCK_TEXT);
    speechUnlockPending = true;
    utterance.lang = "zh-CN";
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 0;
    utterance.onend = () => {
      speechUnlockPending = false;
      speechUnlockReady = true;
    };
    utterance.onerror = () => {
      speechUnlockPending = false;
    };

    window.speechSynthesis.speak(utterance);
    resumeSpeechSynthesis();
    return true;
  } catch {
    speechUnlockPending = false;
    return false;
  }
}

export function speakSpeechUtterance(utterance: SpeechSynthesisUtterance) {
  if (!canUseSpeechSynthesis()) {
    return false;
  }

  try {
    resumeSpeechSynthesis();
    window.speechSynthesis.speak(utterance);
    speechUnlockReady = true;
    return true;
  } catch {
    return false;
  }
}
