// `Video` in the browser preview, on top of an HTML5 `<video>`.

import assets from "/static/assets.js";
import { ViewManager } from "/static/renderer.js";

function sourceUrl(source) {
  if (!source) return "";
  if (assets.isAssetUri(source)) return assets.resolve(source) || "";
  if (/^(https?:|data:|blob:)/.test(source)) return source;
  const path = source.startsWith("file://") ? source.slice("file://".length) : source;
  if (path.startsWith("/")) return `/file/${encodeURI(path.replace(/^\/+/, ""))}`;
  return assets.resolve(`asset://${path}`) || "";
}

const FITS = { contain: "contain", cover: "cover", stretch: "fill" };

function finite(value) {
  return Number.isFinite(value) ? value : 0;
}

class VideoManager extends ViewManager {
  create(view, props) {
    const el = document.createElement("div");
    el.className = "pn-view";
    el.style.overflow = "hidden";
    const video = document.createElement("video");
    video.playsInline = true;
    video.style.width = "100%";
    video.style.height = "100%";
    video.style.display = "block";
    el.appendChild(video);
    view.el = el;
    view.video = video;
    view.lastProgress = -Infinity;
    const emit = (name, ...args) => {
      if (view.hasEvent(name)) view.ctx.emit(view.tag, name, args);
    };
    const buffering = (value) => {
      if (view.buffering === value) return;
      view.buffering = value;
      emit("on_buffering", value);
    };
    const progress = () => {
      const position = finite(video.currentTime);
      emit("on_progress", position, finite(video.duration));
      view.lastProgress = position;
    };
    video.addEventListener("loadstart", () => buffering(true));
    video.addEventListener("loadedmetadata", () => {
      emit("on_ready", { duration: finite(video.duration), width: video.videoWidth, height: video.videoHeight });
    });
    video.addEventListener("canplay", () => buffering(false));
    video.addEventListener("waiting", () => buffering(true));
    video.addEventListener("playing", () => buffering(false));
    video.addEventListener("seeked", progress);
    video.addEventListener("timeupdate", () => {
      // `timeupdate` runs at the browser's own pace, about 4 Hz.
      const interval = Number(view.props.progress_interval) || 0.25;
      if (Math.abs(video.currentTime - view.lastProgress) >= interval) progress();
    });
    video.addEventListener("ended", () => emit("on_end"));
    video.addEventListener("error", () => {
      buffering(false);
      emit("on_error", video.error?.message || "The video couldn't load");
    });
    this.update(view, props);
  }

  update(view, changed) {
    super.update(view, changed);
    const { video } = view;
    if ("controls" in changed) video.controls = !!changed.controls;
    if ("loop" in changed) video.loop = !!changed.loop;
    if ("muted" in changed) video.muted = !!changed.muted;
    if ("volume" in changed) video.volume = Math.min(1, Math.max(0, Number(changed.volume ?? 1)));
    if ("resize_mode" in changed) video.style.objectFit = FITS[changed.resize_mode] || "contain";
    if ("poster" in changed) video.poster = sourceUrl(changed.poster);
    if ("autoplay" in changed) video.autoplay = !!changed.autoplay;
    if ("source" in changed) {
      const url = sourceUrl(changed.source);
      if (url) video.src = url;
      else video.removeAttribute("src");
      video.load();
    }
    // Loading a new source resets the rate, so apply it afterward.
    if ("rate" in changed || "source" in changed) {
      video.defaultPlaybackRate = video.playbackRate = Number(view.props.rate ?? 1) || 1;
    }
  }

  command(view, name, args) {
    const { video } = view;
    switch (name) {
      case "play":
        // A browser may refuse without a user gesture; the view stays paused.
        video.play()?.catch?.(() => {});
        return null;
      case "pause":
        video.pause();
        return null;
      case "seek":
        video.currentTime = Math.max(0, Number(args.seconds) || 0);
        return null;
      case "position":
        return finite(video.currentTime);
      default:
        return super.command(view, name, args);
    }
  }

  destroy(view) {
    view.video.pause();
    view.video.removeAttribute("src");
    view.video.load();
  }
}

export const components = { Video: VideoManager };
