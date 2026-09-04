// Color parsing that matches PNColor.swift / Colors.kt: `#RGB`, `#RGBA`,
// `#RRGGBB`, `#AARRGGBB` (alpha first, the PythonNative convention),
// `rgb()` / `rgba()`, CSS names, raw ARGB integers, `"transparent"`, and
// `{"light": c, "dark": c}` dynamic colors resolved for the current
// scheme. Returns a CSS color string or null.

const COLOR_KEY = /(^|_)(color|colour)$/;

export function isColorProp(key) {
  return COLOR_KEY.test(key) || key === "tint" || key === "shadow_color";
}

export function color(value, scheme = "light") {
  if (value == null) return null;
  if (typeof value === "object" && !Array.isArray(value)) {
    const light = value.light ?? value.default;
    const dark = value.dark;
    if (light == null && dark == null) return null;
    const pick = scheme === "dark" ? (dark ?? light) : (light ?? dark);
    return color(pick, scheme);
  }
  if (typeof value === "number") return fromARGB(value);
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text) return null;
  const lower = text.toLowerCase();
  if (lower === "transparent" || lower === "clear" || lower === "none") return "transparent";
  if (text.startsWith("#")) return parseHex(text.slice(1));
  if (lower.startsWith("rgb")) return text;
  if (/^[0-9a-f]{6}$|^[0-9a-f]{8}$/i.test(text)) return parseHex(text);
  // Any other CSS color the browser knows (named colors and beyond).
  return CSS.supports("color", text) ? text : null;
}

function fromARGB(value) {
  let argb = Math.trunc(value);
  if (argb < 0) argb += 0x1_0000_0000;
  const a = ((argb >>> 24) & 0xff) / 255;
  const r = (argb >>> 16) & 0xff;
  const g = (argb >>> 8) & 0xff;
  const b = argb & 0xff;
  return `rgba(${r}, ${g}, ${b}, ${round(a)})`;
}

function parseHex(digits) {
  let hex = digits;
  switch (hex.length) {
    case 3:
      hex = "FF" + [...hex].map((c) => c + c).join("");
      break;
    case 4: {
      const e = [...hex].map((c) => c + c);
      hex = e[3] + e[0] + e[1] + e[2];
      break;
    }
    case 6:
      hex = "FF" + hex;
      break;
    case 8:
      break;
    default:
      return null;
  }
  if (!/^[0-9a-f]{8}$/i.test(hex)) return null;
  return fromARGB(parseInt(hex, 16));
}

function round(v) {
  return Math.round(v * 1000) / 1000;
}
