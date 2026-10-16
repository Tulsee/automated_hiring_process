import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Camera access and recording, kept in one place.
 *
 * The browser media APIs are wrapped rather than used inline so the interview
 * flow can be tested without a real camera, and so the stream is released
 * exactly once — a live camera light left on after the interview ends is the
 * kind of bug a candidate notices and a developer does not.
 *
 * One stream is acquired for the whole interview and reused; a fresh
 * `MediaRecorder` is created per question, because a recorder cannot be
 * restarted once stopped.
 */

/** Codecs in preference order; the first the browser admits to is used. */
const MIME_TYPES = [
  "video/webm;codecs=vp9,opus",
  "video/webm;codecs=vp8,opus",
  "video/webm",
  "video/mp4",
];

export function pickMimeType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;

  return (
    MIME_TYPES.find((type) => MediaRecorder.isTypeSupported?.(type)) ?? null
  );
}

export type CameraState = "idle" | "requesting" | "ready" | "denied";

export interface MediaRecorderApi {
  stream: MediaStream | null;
  cameraState: CameraState;
  error: Error | null;
  recording: boolean;
  requestCamera: () => Promise<boolean>;
  start: () => boolean;
  /** Resolves with the recording once the recorder has flushed. */
  stop: () => Promise<Blob | null>;
  release: () => void;
}

export function useMediaRecorder(): MediaRecorderApi {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [error, setError] = useState<Error | null>(null);
  const [recording, setRecording] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const requestCamera = useCallback(async () => {
    if (streamRef.current) return true;

    setCameraState("requesting");
    setError(null);

    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });

      streamRef.current = media;
      setStream(media);
      setCameraState("ready");

      return true;
    } catch (caught: unknown) {
      // A denial and an absent camera land here alike; the message is what
      // the candidate needs, so it is passed through.
      setError(
        caught instanceof Error
          ? caught
          : new Error("Could not access the camera"),
      );
      setCameraState("denied");

      return false;
    }
  }, []);

  const start = useCallback(() => {
    const media = streamRef.current;

    if (!media) {
      setError(new Error("The camera is not ready yet"));

      return false;
    }

    const mimeType = pickMimeType();

    if (!mimeType) {
      setError(new Error("This browser cannot record video"));

      return false;
    }

    chunksRef.current = [];

    const recorder = new MediaRecorder(media, { mimeType });

    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data?.size > 0) chunksRef.current.push(event.data);
    };

    recorderRef.current = recorder;

    recorder.start();
    setRecording(true);

    return true;
  }, []);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;

    if (!recorder || recorder.state === "inactive") {
      setRecording(false);

      return Promise.resolve(null);
    }

    return new Promise<Blob | null>((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "video/webm",
        });

        recorderRef.current = null;
        chunksRef.current = [];
        setRecording(false);

        resolve(blob);
      };

      recorder.stop();
    });
  }, []);

  const release = useCallback(() => {
    const recorder = recorderRef.current;

    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }

    recorderRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    setStream(null);
    setRecording(false);
    setCameraState("idle");
  }, []);

  // Turn the camera off when the flow unmounts, whatever state it was in.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, []);

  return {
    stream,
    cameraState,
    error,
    recording,
    requestCamera,
    start,
    stop,
    release,
  };
}

/**
 * A countdown that calls `onElapsed` once it reaches zero.
 *
 * Used for both the preparation window and each question's own limit, so the
 * two behave identically and only the duration differs.
 */
export function useCountdown(
  seconds: number | null,
  onElapsed: () => void,
): number | null {
  // Progress is tagged with the run it belongs to, so `remaining` can be
  // *derived* and the hook never has to reset state from inside an effect.
  // A tag mismatch means a new countdown has started but not yet ticked, which
  // reads as the full duration — correct, and with no flash of a stale value.
  const [progress, setProgress] = useState<{
    runFor: number | null;
    elapsed: number;
  }>({ runFor: seconds, elapsed: 0 });

  const elapsedRef = useRef(onElapsed);

  useEffect(() => {
    elapsedRef.current = onElapsed;
  });

  useEffect(() => {
    if (seconds === null) return;

    // Each tick is measured against a start timestamp rather than accumulated,
    // so a throttled background tab cannot make the countdown drift.
    const startedAt = Date.now();

    const id = setInterval(() => {
      const gone = Math.floor((Date.now() - startedAt) / 1000);

      setProgress({ runFor: seconds, elapsed: gone });

      if (gone >= seconds) {
        clearInterval(id);
        elapsedRef.current();
      }
    }, 250);

    return () => clearInterval(id);
  }, [seconds]);

  if (seconds === null) return null;

  const elapsed = progress.runFor === seconds ? progress.elapsed : 0;

  return Math.max(0, seconds - elapsed);
}
