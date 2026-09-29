// Bundled-asset resolution for the browser preview.
//
// Plays the role of `PNAssets` (Swift) and `Assets` (Kotlin): turns
// `asset://images/logo.png` into a URL the page can load, picking the
// density variant closest to `devicePixelRatio` from the manifest the dev
// server generates at `/assets/pn_assets.json`, and declares the bundled
// fonts through `/assets/fonts.css`. `refresh()` runs whenever the dev
// server reports that files under `app/assets/` changed.

const SCHEME = "asset://";

class AssetRegistry {
  constructor() {
    this.manifest = { files: [], variants: {}, fonts: [] };
    this.fileSet = new Set();
    this.generation = 0;
    this.listeners = new Set();
    this.fontLink = null;
    this.ready = this.refresh();
  }

  /** Re-read the manifest and font CSS; notifies listeners when done. */
  async refresh() {
    this.generation += 1;
    try {
      const response = await fetch(`/assets/pn_assets.json?v=${this.generation}`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        this.manifest = {
          files: Array.isArray(data.files) ? data.files : [],
          variants: data.variants && typeof data.variants === "object" ? data.variants : {},
          fonts: Array.isArray(data.fonts) ? data.fonts : [],
        };
        this.fileSet = new Set(this.manifest.files);
      }
    } catch (error) {
      // The server may not be up yet; the empty manifest stays in place.
    }
    this.installFonts();
    for (const listener of this.listeners) {
      try {
        listener(this.generation);
      } catch (error) {
        console.error(error);
      }
    }
  }

  installFonts() {
    const href = `/assets/fonts.css?v=${this.generation}`;
    if (!this.fontLink) {
      this.fontLink = document.createElement("link");
      this.fontLink.rel = "stylesheet";
      document.head.appendChild(this.fontLink);
    }
    this.fontLink.href = href;
  }

  /** Subscribe to manifest changes; returns an unsubscribe function. */
  onChange(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  isAssetUri(value) {
    return typeof value === "string" && value.startsWith(SCHEME);
  }

  /** The asset path (`images/logo.png`) named by a URI, or null. */
  pathOf(uri) {
    if (!this.isAssetUri(uri)) return null;
    return uri.slice(SCHEME.length).replace(/^\/+/, "");
  }

  /**
   * The variant path to load for `path` at the current pixel ratio.
   * Prefers an exact match, then the nearest denser variant, then the
   * densest available; falls back to the path itself.
   */
  variantFor(path, scale = window.devicePixelRatio || 1) {
    const group = this.manifest.variants[path];
    if (!group) return path;
    const scales = Object.keys(group).map(Number).filter((n) => Number.isFinite(n));
    if (!scales.length) return path;
    if (group[String(scale)] != null) return group[String(scale)];
    const exact = scales.find((s) => Math.abs(s - scale) < 1e-6);
    if (exact != null) return group[keyFor(group, exact)];
    const above = scales.filter((s) => s > scale).sort((a, b) => a - b);
    const chosen = above.length ? above[0] : Math.max(...scales);
    return group[keyFor(group, chosen)];
  }

  /** The scale of the variant that `variantFor` would choose. */
  scaleOf(path, scale = window.devicePixelRatio || 1) {
    const variant = this.variantFor(path, scale);
    const match = /@(\d+(?:\.\d+)?)x\.[^.]+$/.exec(variant);
    return match ? Number(match[1]) : 1;
  }

  /** URL for an `asset://` URI (or null when the value isn't one). */
  resolve(uri, scale) {
    const path = this.pathOf(uri);
    if (path == null) return null;
    const variant = this.variantFor(path, scale);
    return `/assets/${encodeURI(variant)}?v=${this.generation}`;
  }

  exists(path) {
    return this.fileSet.has(path);
  }
}

function keyFor(group, scale) {
  for (const key of Object.keys(group)) if (Number(key) === scale) return key;
  return String(scale);
}

export const assets = new AssetRegistry();
export default assets;
