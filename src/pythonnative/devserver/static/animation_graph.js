// The browser evaluates the same expression contract as UIKit and Android.
export class AnimationGraph {
  constructor(renderer) {
    this.renderer = renderer;
    this.graphs = new Map(); this.values = new Map(); this.previous = new Map(); this.outputs = new Map();
  }
  install(graph) {
    const ids = new Set(graph.nodes.map(node => node.id));
    for (const [key, old] of this.graphs) if (old.nodes.some(node => ids.has(node.id))) this.graphs.delete(key);
    if (graph.bindings.length) this.graphs.set(graph.id, graph);
    for (const node of graph.nodes) {
      if (!this.values.has(node.id)) this.values.set(node.id, node.value || 0);
      if (!this.previous.has(node.id)) this.previous.set(node.id, node.previous || 0);
    }
    this.collect(); this.evaluate();
  }
  collect() {
    const live = new Set([...this.graphs.values()].flatMap(graph => graph.nodes.map(node => node.id)));
    for (const map of [this.values, this.previous, this.outputs]) for (const key of map.keys()) if (!live.has(key)) map.delete(key);
  }
  forget(tag) {
    for (const [id, graph] of this.graphs) {
      graph.bindings = graph.bindings.filter(binding => binding[0] !== tag);
      if (!graph.bindings.length) this.graphs.delete(id);
    }
    this.collect();
  }
  set(id, value) { this.values.set(id, value); this.evaluate(); }
  event(tag, name, args) {
    const props = this.renderer.views.get(tag)?.props;
    const fields = name.startsWith('gesture:')
      ? props?.gestures?.[Number(name.slice(8))]?.animated_events?.[args[0]?.state]
      : props?._pn_animated_events?.[name];
    if (!fields || !args[0]) return;
    for (const [field, id] of Object.entries(fields)) if (typeof args[0][field] === 'number') this.values.set(id, args[0][field]);
    this.evaluate();
  }
  evaluate() {
    for (const graph of this.graphs.values()) {
      for (const node of graph.nodes) {
        const [a = 0, b = 0] = (node.inputs || []).map(input => input.node ? this.values.get(input.node) || 0 : input.constant);
        let value = 0;
        switch (node.kind) {
          case 'value': value = this.values.get(node.id); break;
          case 'add': value = a + b; break;
          case 'subtract': value = a - b; break;
          case 'multiply': value = a * b; break;
          case 'divide': value = b ? a / b : 0; break;
          case 'modulo': value = b ? a % b : 0; break;
          case 'negate': value = -a; break;
          case 'diff_clamp':
            value = Math.min(node.maximum, Math.max(node.minimum, (this.values.get(node.id) || 0) + a - (this.previous.get(node.id) || 0)));
            this.previous.set(node.id, a); break;
          case 'interpolate': value = this.interpolate(node, a); break;
        }
        this.values.set(node.id, Number.isFinite(value) ? value : 0);
        if (!node.color) this.outputs.set(node.id, this.values.get(node.id));
      }
      for (const [tag, prop, id] of graph.bindings) {
        const view = this.renderer.views.get(tag);
        if (view) this.renderer.animator.set(view, prop, this.outputs.get(id));
      }
    }
  }
  interpolate(node, incoming) {
    let x = incoming;
    const first = node.ranges[0], last = node.ranges.at(-1);
    const mode = x < first ? node.left : x > last ? node.right : 'extend';
    if (mode === 'identity') return x;
    if (mode === 'clamp') x = Math.min(last, Math.max(first, x));
    let index = 0;
    while (index < node.ranges.length - 2 && x >= node.ranges[index + 1]) index++;
    const span = node.ranges[index + 1] - node.ranges[index];
    const t = span ? (x - node.ranges[index]) / span : 0;
    const from = node.outputs[index], to = node.outputs[index + 1];
    if (node.color) {
      this.outputs.set(node.id, '#' + from.map((value, i) => Math.round(value + (to[i] - value) * Math.min(1, Math.max(0, t))).toString(16).padStart(2, '0')).join(''));
      return 0;
    }
    return from + (to - from) * t;
  }
}
