import { useCallback, useEffect, useState } from "react";

export type DevicePermission =
  | "unknown"
  | "requesting"
  | "granted"
  | "denied"
  | "unavailable";

export function useMediaDevices() {
  const [inputs, setInputs] = useState<MediaDeviceInfo[]>([]);
  const [outputs, setOutputs] = useState<MediaDeviceInfo[]>([]);
  const [permission, setPermission] = useState<DevicePermission>(
    navigator.mediaDevices ? "unknown" : "unavailable",
  );
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [level, setLevel] = useState(0);

  const refresh = useCallback(async () => {
    if (!navigator.mediaDevices) {
      setPermission("unavailable");
      return;
    }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      setInputs(devices.filter((device) => device.kind === "audioinput"));
      setOutputs(devices.filter((device) => device.kind === "audiooutput"));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Audio devices could not be listed.",
      );
    }
  }, []);

  useEffect(() => {
    void refresh();
    if (!navigator.mediaDevices) return;
    navigator.mediaDevices.addEventListener("devicechange", refresh);
    return () =>
      navigator.mediaDevices.removeEventListener("devicechange", refresh);
  }, [refresh]);

  const testMicrophone = useCallback(
    async (deviceId?: string) => {
      if (!navigator.mediaDevices) {
        setPermission("unavailable");
        return;
      }
      setPermission("requesting");
      setTesting(true);
      setError(null);
      let stream: MediaStream | null = null;
      let context: AudioContext | null = null;
      let frame = 0;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: deviceId ? { deviceId: { exact: deviceId } } : true,
          video: false,
        });
        setPermission("granted");
        await refresh();
        context = new AudioContext();
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        context.createMediaStreamSource(stream).connect(analyser);
        const values = new Uint8Array(analyser.frequencyBinCount);
        const started = performance.now();
        await new Promise<void>((resolve) => {
          const measure = () => {
            analyser.getByteFrequencyData(values);
            setLevel(
              Math.min(
                1,
                values.reduce((sum, value) => sum + value, 0) /
                  values.length /
                  96,
              ),
            );
            if (performance.now() - started < 3000)
              frame = requestAnimationFrame(measure);
            else resolve();
          };
          measure();
        });
      } catch (reason) {
        if (
          reason instanceof DOMException &&
          (reason.name === "NotAllowedError" || reason.name === "SecurityError")
        ) {
          setPermission("denied");
          setError("Microphone access denied.");
        } else {
          setPermission("unavailable");
          setError(
            reason instanceof Error
              ? reason.message
              : "Microphone test failed.",
          );
        }
      } finally {
        cancelAnimationFrame(frame);
        stream?.getTracks().forEach((track) => track.stop());
        if (context) await context.close();
        setLevel(0);
        setTesting(false);
      }
    },
    [refresh],
  );

  return {
    inputs,
    outputs,
    permission,
    error,
    testing,
    level,
    refresh,
    testMicrophone,
  };
}
