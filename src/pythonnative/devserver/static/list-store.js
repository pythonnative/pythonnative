/** Revisioned keyed list metadata and a prefix-sum index for viewport lookup. */
export class ListStore {
  constructor() {
    this.revision = 0; this.keys = []; this.rows = new Map(); this.indices = new Map();
    this.stickyIndices = []; this.measured = new Map(); this.tree = [0];
  }
  prepare(packet) {
    const invalid = () => { throw new Error("Invalid or stale list patch"); };
    if (!packet || Object.keys(packet).sort().join() !== "base,changes,revision" ||
        !Number.isSafeInteger(packet.base) || packet.base !== this.revision || packet.revision !== this.revision + 1 || !Array.isArray(packet.changes)) invalid();
    let order = null, reset = false;
    const changed = new Map(), deleted = new Set();
    const exists = key => typeof key === "string" && !deleted.has(key) && (changed.has(key) || !reset && this.rows.has(key));
    const editable = () => order || (order = [...this.keys]);
    const row = values => {
      if (!Array.isArray(values) || values.length !== 4) invalid();
      const [key, revision, extent, sticky] = values;
      if (typeof key !== "string" || !key || !Number.isSafeInteger(revision) || revision < 1 || !Number.isFinite(extent) || extent <= 0 || typeof sticky !== "boolean") invalid();
      return {key, revision, extent, sticky};
    };
    for (const change of packet.changes) {
      if (!Array.isArray(change)) invalid();
      const [code, a, b] = change;
      if (code === "reset" && change.length === 2 && Array.isArray(a)) {
        if (reset || order || changed.size || deleted.size) invalid();
        reset = true; order = [];
        for (const value of a) { const item = row(value); if (changed.has(item.key)) invalid(); changed.set(item.key, item); order.push(item.key); }
      } else if (code === "i" && change.length === 3) {
        const item = row(b);
        if (!Number.isSafeInteger(a) || a < 0 || a > (order || this.keys).length || exists(item.key)) invalid();
        editable().splice(a, 0, item.key); changed.set(item.key, item); deleted.delete(item.key);
      } else if (code === "u" && change.length === 2) {
        const item = row(a); if (!exists(item.key)) invalid(); changed.set(item.key, item);
      } else if (code === "d" && change.length === 2 && exists(a)) {
        const keys = editable(); keys.splice(keys.indexOf(a), 1); changed.delete(a); deleted.add(a);
      } else if (code === "m" && change.length === 3 && exists(a)) {
        if (!Number.isSafeInteger(b) || b < 0 || b >= (order || this.keys).length) invalid();
        const keys = editable(); keys.splice(keys.indexOf(a), 1); keys.splice(b, 0, a);
      } else invalid();
    }
    return {base: packet.base, revision: packet.revision, order, reset, changed, deleted};
  }
  publish(patch) {
    if (patch.base !== this.revision) throw new Error("List changed before publication");
    let stickyChanged = false;
    if (patch.reset) { this.rows.clear(); this.measured.clear(); }
    for (const key of patch.deleted) { this.rows.delete(key); this.measured.delete(key); }
    for (const [key, row] of patch.changed) {
      const old = this.rows.get(key);
      stickyChanged ||= old?.sticky !== row.sticky;
      if (!patch.order && old && !this.measured.has(key)) this.add(this.indices.get(key), row.extent - old.extent);
      this.rows.set(key, row);
    }
    if (patch.order) {
      this.keys = patch.order;
      this.indices = new Map(this.keys.map((key, i) => [key, i]));
      this.tree = new Array(this.keys.length + 1).fill(0);
      for (let i = 1; i < this.tree.length; i++) {
        const key = this.keys[i - 1];
        this.tree[i] += this.measured.get(key) || this.rows.get(key).extent;
        const parent = i + (i & -i); if (parent < this.tree.length) this.tree[parent] += this.tree[i];
      }
    }
    if (patch.order || stickyChanged) this.stickyIndices = this.keys.flatMap((key, i) => this.rows.get(key).sticky ? [i] : []);
    this.revision = patch.revision;
  }
  apply(packet) { this.publish(this.prepare(packet)); }
  add(index, delta) { for (let i = index + 1; i < this.tree.length; i += i & -i) this.tree[i] += delta; }
  measure(key, extent) {
    const row = this.rows.get(key); if (!row || !Number.isFinite(extent) || extent <= 0) return;
    const before = this.measured.get(key) || row.extent;
    if (Math.abs(before - extent) < 0.01) return;
    this.measured.set(key, extent); this.add(this.indices.get(key), extent - before);
  }
  offset(index) { let total = 0; for (let i = Math.min(index, this.keys.length); i > 0; i -= i & -i) total += this.tree[i]; return total; }
  indexAt(offset) {
    let index = 0, total = 0, step = 1;
    while (step * 2 < this.tree.length) step *= 2;
    for (; step; step = Math.floor(step / 2)) {
      const next = index + step;
      if (next < this.tree.length && total + this.tree[next] <= offset) { index = next; total += this.tree[next]; }
    }
    return Math.min(index, Math.max(0, this.keys.length - 1));
  }
  sticky(index) {
    let low = 0, high = this.stickyIndices.length;
    while (low < high) { const mid = (low + high) >>> 1; if (this.stickyIndices[mid] <= index) low = mid + 1; else high = mid; }
    return low ? this.stickyIndices[low - 1] : -1;
  }
}
