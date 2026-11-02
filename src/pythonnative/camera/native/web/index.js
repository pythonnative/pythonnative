// `CameraView` and `Camera` in the browser preview, on getUserMedia.

import { ViewManager } from "/static/renderer.js";

const views = new Map();

// The BarcodeDetector API's names, where they differ from the contract's.
const DETECTOR_FORMATS = {
  aztec: "aztec",
  codabar: "codabar",
  code128: "code_128",
  code39: "code_39",
  code93: "code_93",
  data_matrix: "data_matrix",
  ean13: "ean_13",
  ean8: "ean_8",
  itf14: "itf",
  pdf417: "pdf417",
  qr: "qr_code",
  upc_a: "upc_a",
  upc_e: "upc_e",
};
const SCAN_INTERVAL_MS = 250;
const BARCODE_REPEAT_MS = 1500;

function failure(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

class CameraViewManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    el.style.background = "#000";
    el.style.overflow = "hidden";
    const video = document.createElement("video");
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.style.cssText = "position:absolute;inset:0;width:100%;height:100%;object-fit:cover";
    const label = document.createElement("div");
    label.style.cssText = "position:absolute;inset:0;display:none;align-items:center;justify-content:center;color:#fff;font:13px system-ui;text-align:center;padding:16px";
    const overlay = document.createElement("div");
    overlay.style.cssText = "position:absolute;inset:0";
    el.append(video, label, overlay);
    view.el = el;
    view.camera = { video, label, overlay, stream: null, recorder: null, chunks: [], startedAt: 0, seen: new Map(), scanTimer: null, generation: 0 };
    views.set(view.tag, view);
    this.update(view, props);
    this.start(view);
  }

  container(view) {
    return view.camera.overlay;
  }

  update(view, changed) {
    super.update(view, changed);
    if (view.camera.mounted && "facing" in changed) this.start(view);
    if (view.camera.mounted && "barcode_types" in changed) this.scan(view);
    if (view.camera.mounted && ("zoom" in changed || "flash" in changed)) this.applyTrack(view);
    view.camera.mounted = true;
  }

  async start(view) {
    const camera = view.camera;
    const generation = ++camera.generation;
    this.stopStream(camera);
    if (!navigator.mediaDevices?.getUserMedia) {
      this.fail(view, "unavailable", "This browser has no getUserMedia, or the page isn't served over a secure origin.", "Camera unavailable");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: view.props.facing === "front" ? "user" : "environment" },
      });
      if (generation !== camera.generation) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      camera.stream = stream;
      camera.video.srcObject = stream;
      camera.label.style.display = "none";
      await camera.video.play().catch(() => {});
      this.applyTrack(view);
      this.scan(view);
      if (view.hasEvent("on_ready")) view.ctx.emit(view.tag, "on_ready", []);
    } catch (error) {
      if (generation !== camera.generation) return;
      const denied = error?.name === "NotAllowedError" || error?.name === "SecurityError";
      this.fail(
        view,
        denied ? "permission_denied" : "unavailable",
        String(error?.message || error),
        denied ? "Camera permission denied" : "Camera unavailable",
      );
    }
  }

  fail(view, code, message, label) {
    view.camera.label.textContent = label;
    view.camera.label.style.display = "flex";
    if (view.hasEvent("on_error")) view.ctx.emit(view.tag, "on_error", [{ code, message }]);
  }

  /** Zoom and the torch are optional constraints most desktop webcams lack. */
  applyTrack(view) {
    const track = view.camera.stream?.getVideoTracks()[0];
    const capabilities = track?.getCapabilities?.();
    if (!capabilities) return;
    const advanced = {};
    if (capabilities.zoom) {
      const zoom = Number(view.props.zoom ?? 1);
      advanced.zoom = Math.max(capabilities.zoom.min, Math.min(zoom, capabilities.zoom.max));
    }
    if (capabilities.torch) advanced.torch = view.props.flash === "torch";
    if (Object.keys(advanced).length) track.applyConstraints({ advanced: [advanced] }).catch(() => {});
  }

  /** Scanning needs the BarcodeDetector API, which only some browsers have. */
  scan(view) {
    const camera = view.camera;
    clearInterval(camera.scanTimer);
    camera.scanTimer = null;
    camera.seen.clear();
    const types = view.props.barcode_types || [];
    if (!types.length || !camera.stream || !("BarcodeDetector" in window)) return;
    const contract = Object.fromEntries(types.map((type) => [DETECTOR_FORMATS[type], type]));
    const detector = new window.BarcodeDetector({ formats: Object.keys(contract) });
    camera.scanTimer = setInterval(async () => {
      if (camera.video.readyState < 2) return;
      let found = [];
      try {
        found = await detector.detect(camera.video);
      } catch {
        return;
      }
      const now = performance.now();
      for (const barcode of found) {
        const type = contract[barcode.format];
        if (!type) continue;
        const key = `${type}:${barcode.rawValue}`;
        const last = camera.seen.get(key);
        camera.seen.set(key, now);
        if ((last === undefined || now - last >= BARCODE_REPEAT_MS) && view.hasEvent("on_barcode")) {
          view.ctx.emit(view.tag, "on_barcode", [{ type, data: barcode.rawValue }]);
        }
      }
    }, SCAN_INTERVAL_MS);
  }

  stopStream(camera) {
    clearInterval(camera.scanTimer);
    camera.scanTimer = null;
    camera.stream?.getTracks().forEach((track) => track.stop());
    camera.stream = null;
    camera.video.srcObject = null;
  }

  destroy(view) {
    view.camera.generation += 1;
    if (view.camera.recorder?.state === "recording") view.camera.recorder.stop();
    this.stopStream(view.camera);
    views.delete(view.tag);
  }
}

function camera(tag) {
  const view = views.get(tag);
  if (!view) throw failure("not_ready", `No CameraView with tag ${tag} is mounted`);
  if (!view.camera.stream) throw failure("not_ready", "The camera isn't running");
  return view.camera;
}

export const components = { CameraView: CameraViewManager };

export function modules() {
  return {
    Camera: {
      // No system capture screen on a desktop browser, so this is a cancel, as on a device with no camera.
      take_photo() {
        return null;
      },
      take_picture({ tag, quality }) {
        const { video } = camera(tag);
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext("2d").drawImage(video, 0, 0);
        return new Promise((resolve, reject) => {
          canvas.toBlob(
            (blob) => {
              if (!blob) return reject(failure("capture_failed", "The browser returned no image"));
              resolve({ path: URL.createObjectURL(blob), width: canvas.width, height: canvas.height });
            },
            "image/jpeg",
            quality,
          );
        });
      },
      async start_recording({ tag, audio }) {
        const state = camera(tag);
        if (state.recorder?.state === "recording") throw failure("busy", "This CameraView is already recording");
        const tracks = [...state.stream.getVideoTracks()];
        let microphone = null;
        if (audio) {
          microphone = await navigator.mediaDevices.getUserMedia({ audio: true }).catch((error) => {
            throw failure("permission_denied", String(error?.message || error));
          });
          tracks.push(...microphone.getAudioTracks());
        }
        state.microphone = microphone;
        state.chunks = [];
        state.recorder = new MediaRecorder(new MediaStream(tracks));
        state.recorder.ondataavailable = (event) => state.chunks.push(event.data);
        await new Promise((resolve) => {
          state.recorder.onstart = resolve;
          state.recorder.start();
        });
        state.startedAt = performance.now();
        return null;
      },
      stop_recording({ tag }) {
        const state = camera(tag);
        const recorder = state.recorder;
        if (recorder?.state !== "recording") throw failure("not_recording", "This CameraView isn't recording");
        const duration = (performance.now() - state.startedAt) / 1000;
        return new Promise((resolve) => {
          recorder.onstop = () => {
            state.microphone?.getTracks().forEach((track) => track.stop());
            state.microphone = null;
            const blob = new Blob(state.chunks, { type: recorder.mimeType });
            resolve({ path: URL.createObjectURL(blob), duration });
          };
          recorder.stop();
        });
      },
    },
  };
}
