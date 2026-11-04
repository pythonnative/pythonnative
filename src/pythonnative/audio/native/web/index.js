// `Audio` in the browser preview: `HTMLAudioElement` and `MediaRecorder`.

import assets from "/static/assets.js";

function sourceUrl(source) {
  if (assets.isAssetUri(source)) return assets.resolve(source) || "";
  if (/^(https?:|data:|blob:)/.test(source)) return source;
  const path = source.startsWith("file://") ? source.slice("file://".length) : source;
  if (path.startsWith("/")) return `/file/${encodeURI(path.replace(/^\/+/, ""))}`;
  return assets.resolve(`asset://${path}`) || "";
}

function finite(value) {
  return Number.isFinite(value) ? value : 0;
}

export function modules(host) {
  const sounds = new Map();
  const recordings = new Map();
  let nextId = 1;

  const sound = (id) => {
    const element = sounds.get(id);
    if (!element) throw new Error(`No loaded sound ${id}`);
    return element;
  };
  const recording = (id) => {
    const active = recordings.get(id);
    if (!active) throw new Error(`No active recording ${id}`);
    return active;
  };
  const elapsed = (active) => active.elapsed + (active.resumedAt ? performance.now() - active.resumedAt : 0);

  return {
    Audio: {
      load_sound({ source, volume, rate, looping }) {
        return new Promise((resolve, reject) => {
          const url = sourceUrl(source);
          if (!url) return reject(new Error(`Can't find sound source: ${source}`));
          const element = new Audio();
          element.preload = "auto";
          element.volume = volume;
          element.defaultPlaybackRate = element.playbackRate = rate;
          element.loop = looping;
          element.addEventListener("loadedmetadata", () => {
            const id = nextId++;
            sounds.set(id, element);
            element.addEventListener("ended", () => {
              element.currentTime = 0;
              host.moduleEvent("Audio", "sound_ended", { id });
            });
            resolve(id);
          }, { once: true });
          element.addEventListener("error", () => reject(new Error(element.error?.message || "The sound couldn't load")), { once: true });
          element.src = url;
        });
      },
      play_sound({ id }) {
        // A browser may refuse without a user gesture; the sound stays paused.
        sound(id).play()?.catch?.(() => {});
        return null;
      },
      pause_sound({ id }) {
        sound(id).pause();
        return null;
      },
      stop_sound({ id }) {
        const element = sound(id);
        element.pause();
        element.currentTime = 0;
        return null;
      },
      seek_sound({ id, seconds }) {
        sound(id).currentTime = Math.max(0, seconds);
        return null;
      },
      set_sound_volume({ id, volume }) {
        sound(id).volume = Math.min(1, Math.max(0, volume));
        return null;
      },
      set_sound_rate({ id, rate }) {
        sound(id).playbackRate = rate;
        return null;
      },
      set_sound_looping({ id, looping }) {
        sound(id).loop = looping;
        return null;
      },
      sound_position({ id }) {
        return finite(sound(id).currentTime);
      },
      sound_duration({ id }) {
        return finite(sound(id).duration);
      },
      unload_sound({ id }) {
        const element = sounds.get(id);
        if (element) {
          element.pause();
          element.removeAttribute("src");
          element.load();
          sounds.delete(id);
        }
        return null;
      },
      async start_recording() {
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
          throw new Error("This browser can't record audio");
        }
        if (recordings.size) throw new Error("A recording is already running");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        const chunks = [];
        recorder.addEventListener("dataavailable", (event) => chunks.push(event.data));
        const context = new AudioContext();
        const analyser = context.createAnalyser();
        context.createMediaStreamSource(stream).connect(analyser);
        recorder.start();
        const id = nextId++;
        recordings.set(id, { recorder, stream, chunks, context, analyser, elapsed: 0, resumedAt: performance.now() });
        return id;
      },
      pause_recording({ id }) {
        const active = recording(id);
        active.recorder.pause();
        active.elapsed = elapsed(active);
        active.resumedAt = 0;
        return null;
      },
      resume_recording({ id }) {
        const active = recording(id);
        active.recorder.resume();
        active.resumedAt = performance.now();
        return null;
      },
      recording_metering({ id }) {
        const { analyser } = recording(id);
        const samples = new Float32Array(analyser.fftSize);
        analyser.getFloatTimeDomainData(samples);
        const power = samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length;
        return power > 0 ? Math.max(-160, 10 * Math.log10(power)) : -160;
      },
      stop_recording({ id }) {
        const active = recording(id);
        recordings.delete(id);
        const duration = elapsed(active) / 1000;
        return new Promise((resolve) => {
          active.recorder.addEventListener("stop", () => {
            active.stream.getTracks().forEach((track) => track.stop());
            active.context.close();
            const blob = new Blob(active.chunks, { type: active.recorder.mimeType });
            resolve({ path: URL.createObjectURL(blob), duration });
          }, { once: true });
          active.recorder.stop();
        });
      },
      set_mode() {
        return null;
      },
    },
  };
}
