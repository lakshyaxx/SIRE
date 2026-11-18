import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { InlineSpeech, safeSpeechText, type SpeechUpdate } from "./speech";

export function RecordVoice({
  disabled,
  onRecording,
  onStart,
  microphoneId,
}: {
  microphoneId?: string;
  onStart?: () => void;
  disabled: boolean;
  onRecording: (file: File, requestId: string) => Promise<void>;
}) {
  const [acquiring, setAcquiring] = useState(false);
  const mounted = useRef(true);
  const [ready, setReady] = useState(false);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const node = useRef<AudioWorkletNode | null>(null);
  const chunks = useRef<Float32Array[]>([]);
  const started = useRef(0);
  const job = useRef("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  function readiness() {
    api<{ asr_ready: boolean }>("/voice/capabilities")
      .then((r) => setReady(r.asr_ready))
      .catch((e) => setError(e.message));
  }
  useEffect(() => {
    mounted.current = true;
    readiness();
    return () => {
      mounted.current = false;
      stream.current?.getTracks().forEach((t) => t.stop());
      void context.current?.close();
      if (timer.current) clearInterval(timer.current);
    };
  }, []);
  async function stop(keep: boolean) {
    if (!recording || !context.current) return;
    const rate = context.current.sampleRate;
    setRecording(false);
    if (timer.current) clearInterval(timer.current);
    node.current?.disconnect();
    stream.current?.getTracks().forEach((t) => t.stop());
    await context.current.close();
    context.current = null;
    const blocks = chunks.current;
    chunks.current = [];
    if (!keep) return;
    const length = blocks.reduce((total, block) => total + block.length, 0);
    if (!length) {
      setError(
        "No audio samples were captured. Check microphone permission or type the question.",
      );
      return;
    }
    const buffer = new ArrayBuffer(44 + length * 2);
    const view = new DataView(buffer);
    const write = (offset: number, text: string) => {
      for (let i = 0; i < text.length; i++)
        view.setUint8(offset + i, text.charCodeAt(i));
    };
    write(0, "RIFF");
    view.setUint32(4, 36 + length * 2, true);
    write(8, "WAVE");
    write(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    write(36, "data");
    view.setUint32(40, length * 2, true);
    let position = 44;
    for (const block of blocks)
      for (const sample of block) {
        const value = Math.max(-1, Math.min(1, sample));
        view.setInt16(
          position,
          value < 0 ? value * 32768 : value * 32767,
          true,
        );
        position += 2;
      }
    job.current = crypto.randomUUID();
    setProcessing(true);
    try {
      await onRecording(
        new File(
          [buffer],
          `recording-${new Date().toISOString().replaceAll(":", "-")}.wav`,
          { type: "audio/wav" },
        ),
        job.current,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProcessing(false);
    }
  }
  // Timer uses a ref to the current stop closure so the recording state cannot become stale.
  const stopRef = useRef(stop);
  stopRef.current = stop;
  async function start() {
    if (acquiring) return;
    onStart?.();
    setAcquiring(true);
    setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Microphone capture requires a supported secure browser context. Type the question instead.",
        );
      const media = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          ...(microphoneId ? { deviceId: { exact: microphoneId } } : {}),
        },
        video: false,
      });
      if (!mounted.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const audio = new AudioContext();
      context.current = audio;
      await audio.resume();
      chunks.current = [];
      const source = audio.createMediaStreamSource(media);
      const script =
        "class Capture extends AudioWorkletProcessor { process(inputs) { const samples=inputs[0]?.[0]; if(samples)this.port.postMessage(samples.slice()); return true; }} registerProcessor('sire-capture',Capture);";
      const url = URL.createObjectURL(
        new Blob([script], { type: "text/javascript" }),
      );
      try {
        await audio.audioWorklet.addModule(url);
      } finally {
        URL.revokeObjectURL(url);
      }
      const processor = new AudioWorkletNode(audio, "sire-capture");
      node.current = processor;
      processor.port.onmessage = (event) =>
        chunks.current.push(event.data as Float32Array);
      const silent = audio.createGain();
      silent.gain.value = 0;
      source.connect(processor);
      processor.connect(silent);
      silent.connect(audio.destination);
      started.current = performance.now();
      setSeconds(0);
      setRecording(true);
      timer.current = setInterval(() => {
        const elapsed = (performance.now() - started.current) / 1000;
        setSeconds(Math.floor(elapsed));
        if (elapsed >= 59) void stopRef.current(true);
      }, 250);
    } catch (e) {
      stream.current?.getTracks().forEach((t) => t.stop());
      void context.current?.close();
      setError((e as Error).message);
    } finally {
      setAcquiring(false);
    }
  }
  return (
    <div className="voice-controls">
      {recording ? (
        <>
          <span role="status">Microphone recording · {seconds}s / 60s</span>
          <button
            type="button"
            className="secondary"
            onClick={() => stop(true)}
          >
            Stop & transcribe locally
          </button>
          <button type="button" onClick={() => stop(false)}>
            Discard recording
          </button>
        </>
      ) : processing ? (
        <>
          <span role="status">Transcribing recorded speech locally…</span>
          <button
            type="button"
            onClick={() =>
              api("/voice/cancel", { request_id: job.current }).catch((e) =>
                setError(e.message),
              )
            }
          >
            Cancel transcription
          </button>
        </>
      ) : (
        <button
          type="button"
          className="secondary"
          disabled={disabled || !ready || acquiring}
          onClick={start}
        >
          {ready ? "Record a question" : "Local speech not ready"}
        </button>
      )}
      {!ready && (
        <button type="button" onClick={readiness}>
          Recheck speech
        </button>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <small>
        Recording starts only after your browser permission. Review/edit the
        transcript, then use Send.
      </small>
    </div>
  );
}

export function ReadReply({
  text,
  disabled = false,
  autoSpeak = false,
  volume = 0.8,
  speakerId,
}: {
  text: string;
  disabled?: boolean;
  autoSpeak?: boolean;
  volume?: number;
  speakerId?: string;
}) {
  const playbackId = useRef(crypto.randomUUID());
  const audio = useRef<HTMLAudioElement | null>(null);
  const service = useRef<InlineSpeech | null>(null);
  const utterance = useRef<SpeechSynthesisUtterance | null>(null);
  const [state, setState] = useState<SpeechUpdate>({ state: "idle" });
  const [engine, setEngine] = useState(() => {
    try {
      return sessionStorage.getItem("sire-speech-provider") || "neural";
    } catch {
      return "neural";
    }
  });
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const autoStarted = useRef(false);
  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent("sire:playback-state", {
        detail: { id: playbackId.current, state: state.state },
      }),
    );
    return () => {
      window.dispatchEvent(
        new CustomEvent("sire:playback-state", {
          detail: { id: playbackId.current, state: "idle" },
        }),
      );
    };
  }, [state.state]);
  useEffect(() => {
    if (!audio.current) return;
    service.current = new InlineSpeech(audio.current, setState);
    const stop = () => {
      service.current?.stop();
      if (utterance.current) {
        window.speechSynthesis?.cancel();
        utterance.current = null;
      }
    };
    const list = () =>
      setVoices(
        window.speechSynthesis
          ?.getVoices()
          .filter(
            (voice) =>
              voice.localService && voice.lang.toLowerCase().startsWith("en"),
          ) || [],
      );
    list();
    window.speechSynthesis?.addEventListener("voiceschanged", list);
    window.addEventListener("sire:stop-speech", stop);
    return () => {
      stop();
      window.removeEventListener("sire:stop-speech", stop);
      window.speechSynthesis?.removeEventListener("voiceschanged", list);
    };
  }, []);
  function start() {
    window.dispatchEvent(new Event("sire:stop-speech"));
    setState({ state: "buffering" });
    if (engine === "browser") {
      const voice = window.speechSynthesis
        ?.getVoices()
        .find(
          (item) =>
            item.localService && item.lang.toLowerCase().startsWith("en"),
        );
      if (!voice) {
        setState({
          state: "error",
          error:
            "No installed local English browser voice is available. Select local neural speech.",
        });
        return;
      }
      const speech = new SpeechSynthesisUtterance(safeSpeechText(text));
      speech.voice = voice;
      speech.volume = volume;
      utterance.current = speech;
      speech.onstart = () =>
        setState({
          state: "speaking",
          model: `Installed browser voice: ${voice.name}`,
        });
      speech.onend = () => {
        utterance.current = null;
        setState({ state: "idle" });
      };
      speech.onerror = (event) => {
        utterance.current = null;
        if (event.error !== "interrupted" && event.error !== "canceled")
          setState({
            state: "error",
            error:
              "Installed browser speech failed. Choose local neural TTS or use text.",
          });
      };
      window.speechSynthesis.speak(speech);
    } else
      void service.current
        ?.speak(text)
        .catch((error) => setState({ state: "error", error: error.message }));
  }
  useEffect(() => {
    if (autoSpeak && !autoStarted.current) {
      autoStarted.current = true;
      start();
    }
    if (!autoSpeak) autoStarted.current = false;
  }, [autoSpeak]);
  useEffect(() => {
    if (!audio.current) return;
    audio.current.volume = volume;
    const sink = audio.current as HTMLAudioElement & {
      setSinkId?: (id: string) => Promise<void>;
    };
    if (speakerId && sink.setSinkId)
      void sink
        .setSinkId(speakerId)
        .catch((reason) => setState({ state: "error", error: reason.message }));
  }, [speakerId, volume]);
  const active = ["buffering", "speaking", "paused", "ready"].includes(
    state.state,
  );
  function pause() {
    if (engine === "browser") {
      window.speechSynthesis.pause();
      setState({ state: "paused" });
    } else service.current?.pause();
  }
  function resume() {
    if (engine === "browser") {
      window.speechSynthesis.resume();
      setState({ state: "speaking" });
    } else void service.current?.resume();
  }
  return (
    <div className="reply-speech">
      <button
        type="button"
        className="text-button"
        disabled={disabled || active}
        onClick={start}
        aria-label="Speak answer"
      >
        Speak answer
      </button>
      {(voices.length > 0 || engine === "browser") && (
        <select
          aria-label="Speech provider"
          value={engine}
          disabled={active}
          onChange={(event) => {
            setEngine(event.target.value);
            try {
              sessionStorage.setItem(
                "sire-speech-provider",
                event.target.value,
              );
            } catch {}
          }}
        >
          <option value="neural">Local Kokoro neural voice</option>
          <option value="browser" disabled={!voices.length}>
            Installed browser voice (English)
            {!voices.length ? " ? unavailable" : ""}
          </option>
        </select>
      )}
      {active && (
        <>
          <span role="status">
            {state.state}
            {state.chunk ? ` ? part ${state.chunk}/${state.total}` : ""}
          </span>
          {state.state === "speaking" ? (
            <button type="button" onClick={pause}>
              Pause
            </button>
          ) : (
            (state.state === "paused" || state.state === "ready") && (
              <button type="button" onClick={resume}>
                Play / resume
              </button>
            )
          )}
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event("sire:stop-speech"))}
          >
            Stop speech
          </button>
        </>
      )}
      <audio
        ref={audio}
        controls
        hidden={engine === "browser" || !active}
        aria-label="Inline reply playback"
      />
      {state.model && <small>{state.model}</small>}
      {state.error && (
        <p role="alert" className="error">
          {state.error}
        </p>
      )}
      <small>
        English speech stays local. Stop or tap the microphone to interrupt.
        Review the displayed answer for exact figures.
      </small>
    </div>
  );
}
