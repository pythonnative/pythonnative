// The browser preview's half of Motion (RFC 0009), without the WebAssembly
// core: write and transaction decoding, the `exit` op (both owners, and the
// insert indices that skip exiting views), `remove` writes, paint writes and
// transform precedence, the CoreHost ordering of page-owned exits,
// shared-element flights, and FLIP item animations on a VirtualList. A fake
// host stands in for the core where the renderer calls it.
import {Renderer, platformIndex, motionTiming, cssEasing, springTiming, presetKeyframes, moveKeyframes, sharedPaint, rectIn} from '../../src/pythonnative/devserver/static/renderer.js';
import {CoreHost, decodeTransaction, decodeWrites} from '../../src/pythonnative/devserver/static/core/mount.js';

const assert = (condition, message) => { if (!condition) throw Error(`motion: ${message}`); };
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const frames = (n = 2) => new Promise(resolve => { const step = () => (n-- <= 0 ? resolve() : requestAnimationFrame(step)); step(); });
const until = async (condition, what, ms = 3000) => { for (const end = performance.now() + ms; !condition(); await sleep(10)) if (performance.now() > end) throw Error(`motion: timed out waiting for ${what}`); };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** Little-endian bytes in the core's wire format (`include/pn_core.h`). */
class Writer {
  constructor() { this.bytes = []; }
  u8(v) { this.bytes.push(v & 0xff); return this; }
  u16(v) { return this.raw(2, (d) => d.setUint16(0, v, true)); }
  u32(v) { return this.raw(4, (d) => d.setUint32(0, v, true)); }
  i64(v) { return this.raw(8, (d) => d.setBigInt64(0, BigInt(v), true)); }
  f64(v) { return this.raw(8, (d) => d.setFloat64(0, v, true)); }
  raw(size, write) { const d = new DataView(new ArrayBuffer(size)); write(d); this.bytes.push(...new Uint8Array(d.buffer)); return this; }
  str(text) { const utf8 = new TextEncoder().encode(text); this.u32(utf8.length); this.bytes.push(...utf8); return this; }
  value(v) {
    if (v === null) return this.u8(0);
    if (v === false) return this.u8(1);
    if (v === true) return this.u8(2);
    if (Number.isInteger(v)) return this.u8(3).i64(v);
    if (typeof v === 'number') return this.u8(4).f64(v);
    if (typeof v === 'string') return this.u8(5).str(v);
    if (Array.isArray(v)) { this.u8(6).u32(v.length); for (const item of v) this.value(item); return this; }
    const entries = Object.entries(v); this.u8(7).u32(entries.length);
    for (const [key, item] of entries) { this.str(key); this.value(item); }
    return this;
  }
  done() { return Uint8Array.from(this.bytes); }
}

/** One transaction's bytes: `ops` are `[code, ...fields]` written in order. */
function transactionBytes(surface, revision, id, ops) {
  const w = new Writer().u32(0x544d4e50).u16(1).u16(0).i64(surface).i64(revision).i64(id).u32(ops.length);
  for (const op of ops) {
    const [code] = op; w.u8(code);
    if (code === 1) w.i64(op[1]).str(op[2]).value(op[3]);
    else if (code === 3) w.i64(op[1]).i64(op[2]).u32(op[3]);
    else if (code === 5) w.i64(op[1]);
    else if (code === 6) { w.i64(op[1]); for (const n of op[2]) w.f64(n); }
    else if (code === 8) w.i64(op[1]).u8(op[2]);
  }
  return w.done();
}

/** A stand-in for `CoreHost` as the renderer sees it. */
function fakeHost(lists = {}) {
  const host = {
    finished: [], pairs: [],
    core: {
      reportContainer() {}, invalidate() {}, reportIntrinsic() {},
      listApply: (s, tag) => lists[tag]?.patches.shift() ?? null,
      listRevision: (s, tag) => lists[tag]?.revision ?? 0,
      listCount: (s, tag) => lists[tag]?.keys.length ?? 0,
      listKey: (s, tag, i) => lists[tag]?.keys[i] ?? null,
      listExtent: (s, tag, i) => lists[tag]?.extent ?? 0,
      listSticky: () => false, listStickyAt: () => -1, listRowRevision: () => 0,
    },
    event() {}, pointer() {}, forgetGestures() {}, commandResult() {},
    exitFinished(surface, tag) { host.finished.push([surface, tag]); },
    sharedElements(surface, from, to) { return host.pairs.filter(pair => pair.from === from && pair.to === to); },
  };
  return host;
}

function makeRenderer(overlay, host) {
  const renderer = new Renderer({scheme: () => 'light', overlays: () => overlay, bottomInset: () => 0, frameWidth: () => 390,
    pointInFrame: () => ({x: 0, y: 0}), pointInWindow: () => ({x: 0, y: 0}), statusBar() {}});
  if (host) renderer.attach(host);
  return renderer;
}

/** Apply decoded-shape ops as one transaction. */
const apply = (renderer, ops) => renderer.applyTransaction({surface: 1, revision: 1, id: 1, ops});
const create = (tag, component, props = {}) => ({kind: 'create', tag, component, props});
const insert = (parent, tag, index) => ({kind: 'insert', parent, tag, index});
const frame = (tag, x, y, w, h) => ({kind: 'frame', tag, frame: [x, y, w, h]});
const order = (view) => view.children.map(child => child.tag).join();
const domOrder = (el) => [...el.children].map(child => child.dataset.pnTag).filter(Boolean).join();

export async function runMotionTests() {
  const stage = document.createElement('div');
  stage.style.cssText = 'position:relative;width:390px;height:600px;overflow:hidden';
  document.body.append(stage);
  // -- decoding ------------------------------------------------------------
  const writes = new Writer().u32(4)
    .u8(0).i64(7).str('opacity').value(0.5)
    .u8(0).i64(7).str('transform').value([{translate_x: 12}])
    .u8(1).i64(8).f64(1).f64(2).f64(30).f64(40)
    .u8(2).u32(3).i64(10).i64(11).i64(9).done();
  assert(same(decodeWrites(writes), [
    {kind: 'prop', tag: 7, prop: 'opacity', value: 0.5},
    {kind: 'prop', tag: 7, prop: 'transform', value: [{translate_x: 12}]},
    {kind: 'frame', tag: 8, frame: [1, 2, 30, 40]},
    {kind: 'remove', tags: [10, 11, 9]},
  ]), `motion writes decode: ${JSON.stringify(decodeWrites(writes))}`);
  assert(same(decodeWrites(new Writer().u32(1).u8(0).i64(3).str('background_color').value(null).done()), [{kind: 'prop', tag: 3, prop: 'background_color', value: null}]), 'a null prop write decodes');
  let unknownKind = null;
  try { decodeWrites(new Writer().u32(1).u8(9).done()); } catch (error) { unknownKind = error; }
  assert(unknownKind && /kind 9/.test(unknownKind.message), 'an unknown write kind is an error');
  const exitTransaction = decodeTransaction(transactionBytes(1, 4, 5, [[5, 3], [8, 4, 0], [8, 6, 1]]));
  assert(same(exitTransaction.ops, [{kind: 'delete', tag: 3}, {kind: 'exit', tag: 4, owner: 0}, {kind: 'exit', tag: 6, owner: 1}]), `exit ops decode: ${JSON.stringify(exitTransaction.ops)}`);

  // -- insert indices skip exiting siblings ----------------------------------
  const kids = (...flags) => flags.map(exiting => ({exiting}));
  assert(platformIndex(kids(false, true, false), 0) === 0 && platformIndex(kids(false, true, false), 1) === 2 && platformIndex(kids(false, true, false), 2) === 3, 'indices map past an exiting sibling');
  assert(platformIndex(kids(true, false), 0) === 1 && platformIndex(kids(true, true), 0) === 2 && platformIndex([], 0) === 0 && platformIndex(kids(false), 5) === 1, 'leading, all-exiting, empty, and past-the-end indices');

  // -- timing ----------------------------------------------------------------
  assert(cssEasing('ease_in_out') === 'cubic-bezier(0.42, 0, 0.58, 1)' && cssEasing([0.1, 0.2, 0.3, 1]) === 'cubic-bezier(0.1, 0.2, 0.3, 1)' && cssEasing(null) === 'cubic-bezier(0.42, 0, 0.58, 1)' && cssEasing('linear') === 'linear', 'named and bezier easings');
  assert(cssEasing({samples: [0, 0.5, 1]}) === 'linear(0, 0.5, 1)' && cssEasing('bounce').startsWith('linear(0, '), 'sampled curves become linear()');
  assert(same(motionTiming(null, {duration: 260, easing: 'ease_in_out'}), {duration: 260, easing: 'cubic-bezier(0.42, 0, 0.58, 1)', delay: 0}), 'a missing transition uses the platform default push');
  assert(same(motionTiming({duration: 120, delay: 30, easing: 'linear'}), {duration: 120, easing: 'linear', delay: 30}), 'duration, delay, and easing');
  const spring = springTiming({duration: 450, damping_ratio: 0.9});
  assert(spring.easing.startsWith('linear(0, ') && spring.easing.endsWith(', 1)') && spring.duration >= 300 && spring.duration < 1500, `a damped spring settles in about its duration: ${spring.duration}`);
  const bouncy = springTiming({stiffness: 300, damping: 8, mass: 1});
  assert(bouncy.easing.split(',').some(sample => parseFloat(sample) > 1.05), 'an underdamped spring overshoots');
  assert(!springTiming({stiffness: 300, damping: 8, overshoot_clamping: true}).easing.split(',').some(sample => parseFloat(sample.replace('linear(', '')) > 1), 'overshoot clamping stops at the target');
  assert(motionTiming({spring: {duration: 450, damping_ratio: 0.9}, delay: 10}).duration === spring.duration, 'a spring wins over duration');
  assert(same(presetKeyframes('slide_in', 'left'), [{translate: '-100% 0'}, {translate: '0 0'}]) && same(presetKeyframes('fade_out', null, 0.8), [{opacity: 0.8}, {opacity: 0}]) && presetKeyframes('keyframes') === null, 'row presets');
  assert(same(moveKeyframes('linear', -40, false), [{translate: '0 -40px'}, {translate: '0 0'}]) && same(moveKeyframes('linear', 12, true), [{translate: '12px 0'}, {translate: '0 0'}]), 'FLIP moves along the list axis');
  const [paintFrom, paintTo] = sharedPaint({source_style: {border_radius: 8, background_color: '#FF112233'}, target_style: {border_radius: 0}}, ['border_radius', 'background_color', 'opacity'], 'light');
  assert(same(paintFrom, {borderRadius: '8px', backgroundColor: 'rgba(17, 34, 51, 1)'}) && same(paintTo, {borderRadius: '0px', backgroundColor: 'transparent'}), `shared paint blends the keys either end sets: ${JSON.stringify([paintFrom, paintTo])}`);

  // -- exit owner 0, motion writes, remove ----------------------------------
  const overlay = document.createElement('div'); overlay.style.cssText = 'position:absolute;inset:0;pointer-events:none'; stage.append(overlay);
  let host = fakeHost();
  let renderer = makeRenderer(overlay, host);
  apply(renderer, [create(1, 'View', {}), create(2, 'View', {}), create(3, 'View', {transform: [{rotate: 45}], background_color: '#ff0000', opacity: 0.9}),
    create(4, 'View', {}), create(30, 'View', {}), insert(1, 2, 0), insert(1, 3, 1), insert(1, 4, 2), insert(3, 30, 0),
    frame(1, 0, 0, 300, 300), frame(2, 0, 0, 10, 10), frame(3, 0, 10, 10, 10), frame(4, 0, 20, 10, 10)]);
  const parent = renderer.views.get(1), leaving = renderer.views.get(3);
  stage.append(parent.el);
  apply(renderer, [{kind: 'exit', tag: 3, owner: 0}]);
  assert(leaving.exiting && leaving.el.parentNode === parent.el && leaving.el.style.pointerEvents === 'none' && leaving.el.inert, 'an exiting view keeps its place without touches');
  assert(renderer.views.has(30) && renderer.views.get(30).el.parentNode === leaving.el && host.finished.length === 0, 'its subtree stays mounted and the core owns the exit');
  apply(renderer, [create(5, 'View', {}), insert(1, 5, 1), create(6, 'View', {}), insert(1, 6, 3)]);
  assert(order(parent) === '2,3,5,4,6' && domOrder(parent.el) === '2,3,5,4,6', `inserts skip the exiting sibling: ${order(parent)} / ${domOrder(parent.el)}`);
  apply(renderer, [insert(1, 2, 2)]);
  assert(order(parent) === '3,5,4,2,6', `a move counts only live siblings: ${order(parent)}`);

  // Paint writes go through the static path; transform replaces the static list.
  assert(leaving.el.style.transform === 'rotate(45deg)', 'the static transform applies');
  renderer.applyWrites([{kind: 'prop', tag: 3, prop: 'transform', value: [{translate_x: 10}, {scale: 0.5}]}, {kind: 'prop', tag: 3, prop: 'opacity', value: 0.25}]);
  assert(leaving.el.style.transform === 'translateX(10px) scale(0.5)' && leaving.el.style.opacity === '0.25' && leaving.baseOpacity === 0.25, `a transform write replaces the static transform: ${leaving.el.style.transform}`);
  renderer.applyWrites([{kind: 'prop', tag: 3, prop: 'background_color', value: '#FF00FF00'}, {kind: 'prop', tag: 3, prop: 'border_radius', value: 6}]);
  assert(leaving.el.style.backgroundColor === 'rgb(0, 255, 0)' && leaving.el.style.borderRadius === '6px' && leaving.props.background_color === '#ff0000' && !('border_radius' in leaving.props), 'color and radius writes paint without touching the committed props');
  renderer.applyWrites([{kind: 'prop', tag: 3, prop: 'transform', value: null}, {kind: 'prop', tag: 3, prop: 'opacity', value: null}, {kind: 'prop', tag: 3, prop: 'background_color', value: null}]);
  assert(leaving.el.style.transform === '' && leaving.el.style.opacity === '' && leaving.el.style.backgroundColor === '', 'null restores the platform default');
  renderer.applyWrites([{kind: 'prop', tag: 3, prop: 'transform', value: [{translate_y: 4}]}]);
  apply(renderer, [{kind: 'update', tag: 3, props: {transform: [{rotate: 90}]}, removed: [], recreate: false}]);
  assert(leaving.el.style.transform === 'rotate(90deg)', 'a later static update of the key applies (the core re-sends its motion value after)');
  renderer.applyWrites([{kind: 'frame', tag: 3, frame: [5, 6, 70, 80]}, {kind: 'prop', tag: 999, prop: 'opacity', value: 0}]);
  assert(leaving.el.style.left === '5px' && leaving.el.style.top === '6px' && leaving.el.style.width === '70px' && leaving.el.style.height === '80px' && leaving.frame.w === 70, 'a frame write sets the frame; unknown tags are skipped');
  renderer.applyWrites([{kind: 'remove', tags: [30, 3, 404]}]);
  assert(!renderer.views.has(3) && !renderer.views.has(30) && !leaving.el.isConnected && order(parent) === '5,4,2,6', 'a remove write destroys the subtree and tolerates missing tags');
  apply(renderer, [create(7, 'View', {}), insert(1, 7, 0)]);
  assert(order(parent) === '7,5,4,2,6', 'indices are plain again once nothing exits');
  parent.el.remove();

  // -- exit owner 1: a modal dismisses before the core removes it ---------------
  apply(renderer, [create(40, 'Modal', {visible: true}), create(41, 'View', {}), insert(40, 41, 0)]);
  const modal = renderer.views.get(40);
  assert(modal.backdrop.isConnected && modal.sheet.contains(renderer.views.get(41).el), 'the modal presents its content');
  apply(renderer, [{kind: 'exit', tag: 40, owner: 1}]);
  assert(modal.backdrop.isConnected && modal.backdrop.classList.contains('pn-modal-out') && renderer.views.get(41).el.isConnected && host.finished.length === 0, 'a leaving modal keeps its content while it dismisses');
  await until(() => host.finished.length === 1, 'the modal exit to finish', 1500);
  assert(same(host.finished[0], [1, 40]) && !modal.backdrop.isConnected, 'the modal reports its exit once the dismissal ends');
  renderer.applyWrites([{kind: 'remove', tags: [41, 40]}]);
  assert(!renderer.views.has(40) && !renderer.views.has(41), 'the remove write destroys the modal');
  apply(renderer, [create(42, 'Modal', {visible: false}), {kind: 'exit', tag: 42, owner: 1}]);
  assert(same(host.finished[1], [1, 42]), 'a hidden modal finishes its exit at once');
  renderer.applyWrites([{kind: 'remove', tags: [42]}]);

  // -- exit owner 1: a popped screen animates out, then the core removes it -----
  host.finished = [];
  apply(renderer, [create(20, 'ScreenStack', {}), create(21, 'Screen', {}), insert(20, 21, 0), create(22, 'Screen', {}), insert(20, 22, 1),
    create(23, 'View', {}), insert(22, 23, 0), frame(20, 0, 0, 300, 500)]);
  const stack = renderer.views.get(20); stage.append(stack.el);
  const [below, top] = stack.children;
  await sleep(350);
  assert(below.el.style.display === 'none' && top.el.style.display === '', 'the stack shows its top screen');
  apply(renderer, [{kind: 'exit', tag: 22, owner: 1}]);
  assert(top.el.isConnected && top.el.style.display === '' && below.el.style.display === '' && renderer.views.get(23).el.parentNode === top.el, 'a popped screen keeps its content on stage over the revealed one');
  assert(stack.titleEl.textContent === '' && stack.back.style.display === 'none' && host.finished.length === 0, 'the bar follows the revealed screen');
  await frames(2);
  assert(top.el.classList.contains('pn-screen-right'), 'the popped screen slides out');
  await until(() => host.finished.length === 1, 'the pop to finish', 1500);
  assert(same(host.finished[0], [1, 22]), 'the pop reports its exit when the transition ends');
  renderer.applyWrites([{kind: 'remove', tags: [23, 22]}]);
  assert(!top.el.isConnected && order(stack) === '21' && stack.topTag === 21, 'the remove write takes the screen off the stack');
  // A replace: the new screen covers the leaving one, which finishes once covered.
  apply(renderer, [create(24, 'Screen', {}), insert(20, 24, 1), frame(24, 0, 0, 300, 456)]);
  await sleep(350);
  host.finished = [];
  apply(renderer, [{kind: 'exit', tag: 24, owner: 1}, create(25, 'Screen', {}), insert(20, 25, 1)]);
  assert(order(stack) === '21,24,25' && renderer.views.get(24).el.style.display === '', `the replacing screen goes above the leaving one: ${order(stack)}`);
  await until(() => host.finished.length === 1, 'the replaced screen to finish', 1500);
  assert(same(host.finished[0], [1, 24]), 'the replaced screen finishes once the push lands');
  renderer.applyWrites([{kind: 'remove', tags: [24]}]);
  // A screen below the top leaves at once.
  host.finished = [];
  apply(renderer, [{kind: 'exit', tag: 21, owner: 1}]);
  assert(same(host.finished, [[1, 21]]), 'an off-stage screen finishes its exit at once');
  renderer.applyWrites([{kind: 'remove', tags: [21]}]);

  // -- shared elements fly in the overlay with the screens' timing --------------
  apply(renderer, [create(50, 'View', {shared_tag: 'photo', background_color: '#ff0000', border_radius: 8}), insert(25, 50, 0), frame(50, 10, 20, 40, 40)]);
  host.pairs = [{from: 25, to: 26, name: 'photo', source: 50, target: 51, transition: {duration: 300, easing: 'linear'},
    source_style: {border_radius: 8, background_color: '#FFFF0000'}, target_style: {border_radius: 0, background_color: '#FF0000FF'}}];
  const source = renderer.views.get(50);
  apply(renderer, [create(26, 'Screen', {}), insert(20, 26, 2), frame(26, 0, 0, 300, 456),
    create(52, 'View', {}), insert(26, 52, 0), create(51, 'View', {shared_tag: 'photo'}), insert(26, 51, 1), frame(52, 0, 0, 300, 100), frame(51, 0, 100, 300, 200)].map(op => op.kind === 'insert' && op.tag === 26 ? {...op, index: 1} : op));
  const target = renderer.views.get(51), pushed = renderer.views.get(26);
  const layer = overlay.querySelector('.pn-flight-layer');
  assert(layer && target.el.parentNode === layer && target.flight && source.el.style.visibility === 'hidden', 'the target flies in the overlay while the source hides');
  const keyframes = target.flight.animation.effect.getKeyframes();
  const sourceRect = rectIn(source.el, layer);
  assert(Math.abs(parseFloat(keyframes[0].left) - sourceRect.x) < 0.01 && Math.abs(parseFloat(keyframes[0].top) - sourceRect.y) < 0.01 && keyframes[0].width === '40px' && keyframes[1].width === '300px' && keyframes[1].height === '200px',
    `the flight starts on the source and ends on the target: ${JSON.stringify(keyframes)} ${JSON.stringify(sourceRect)}`);
  assert(keyframes[0].borderRadius === '8px' && /0, 0, 255/.test(keyframes[1].backgroundColor), `paint blends from the source style to the target style: ${JSON.stringify(keyframes)}`);
  assert(pushed.el.style.transitionDuration === '300ms' && pushed.el.style.transitionTimingFunction === 'linear', 'the screens move with the flight timing');
  apply(renderer, [frame(51, 0, 110, 300, 200)]);
  assert(target.el.parentNode === layer && target.frame.y === 110, 'a frame during the flight waits for the landing');
  await until(() => !target.flight, 'the flight to land', 1500);
  assert(target.el.parentNode === pushed.el && domOrder(pushed.el) === '52,51' && target.el.style.top === '110px' && source.el.style.visibility === '' && !layer.isConnected, 'the target lands in its parent at its index and frame');
  await sleep(100);
  assert(pushed.el.style.transitionDuration === '', 'the screens take their own timing back');
  // A pop flies back from the leaving screen to the revealed one.
  host.pairs = [{from: 26, to: 25, name: 'photo', source: 51, target: 50, transition: null, source_style: {}, target_style: {}}];
  host.finished = [];
  apply(renderer, [{kind: 'exit', tag: 26, owner: 1}]);
  assert(source.flight && source.el.parentNode === overlay.querySelector('.pn-flight-layer') && target.el.style.visibility === 'hidden', 'a pop flies the revealed screen\'s element');
  await until(() => host.finished.length === 1 && !source.flight, 'the pop with a flight to finish', 2000);
  assert(source.el.parentNode === renderer.views.get(25).el && target.el.style.visibility === '', 'the pop lands');
  renderer.applyWrites([{kind: 'remove', tags: [51, 52, 26]}]);
  apply(renderer, [{kind: 'delete', tag: 50}, {kind: 'delete', tag: 25}, {kind: 'delete', tag: 20}]);
  stack.el.remove();

  // -- CoreHost: a page-owned exit finishes only after its transaction mounted ---
  const calls = [], queue = [];
  let pending = [];
  const core = {
    setPlatform() {}, setReduceMotion() {}, reset() {}, work() {}, animationFrame: () => false,
    mountNext: () => queue.shift() || null,
    mountFinished: (id) => calls.push(['mountFinished', Number(id)]),
    exitFinished: (surface, tag) => { calls.push(['exitFinished', surface, tag]); pending.push({kind: 'remove', tags: [tag]}); },
    takeWrites: () => { const out = pending; pending = []; if (out.length) calls.push(['writes', out.length]); return out; },
    sharedElements: () => [],
  };
  const hostRenderer = makeRenderer(overlay, null);
  const coreHost = new CoreHost(core, hostRenderer, {send() {}});
  queue.push({bytes: transactionBytes(1, 1, 1, [[1, 60, 'Modal', {visible: false}]]), id: 1n});
  coreHost.drain();
  queue.push({bytes: transactionBytes(1, 2, 2, [[8, 60, 1]]), id: 2n});
  coreHost.drain();
  assert(same(calls, [['mountFinished', 1], ['mountFinished', 2], ['exitFinished', 1, 60], ['writes', 1]]), `exit_finished follows mount_finished: ${JSON.stringify(calls)}`);
  assert(!hostRenderer.views.has(60), 'the remove write applies in the same turn');

  // -- VirtualList: FLIP item animations for dataset changes only ------------------
  const lists = {70: {keys: ['a', 'b', 'c'], extent: 40, revision: 1, patches: [{revision: 1}]}};
  host = fakeHost(lists);
  renderer = makeRenderer(overlay, host);
  const preset = (type) => ({type, duration: 200, delay: 0, easing: 'linear'});
  const row = (tag, key) => [create(tag, 'View', {_pn_list_key: key}), insert(70, tag, 0), frame(tag, 0, 0, 200, 40)];
  apply(renderer, [create(70, 'VirtualList', {dataset: {revision: 1}, item_entering: preset('fade_in'), item_exiting: preset('fade_out'), item_layout: preset('linear')}),
    ...row(71, 'a'), ...row(72, 'b'), ...row(73, 'c'), frame(70, 0, 0, 200, 300)]);
  const list = renderer.views.get(70); stage.append(list.el);
  apply(renderer, [frame(70, 0, 0, 200, 300)]);
  const rowEl = (tag) => renderer.views.get(tag).el;
  assert(rowEl(73).style.top === '80px' && !rowEl(73).getAnimations().length, 'rows sit at their offsets without animating on the first publish');
  const removed = rowEl(72);
  lists[70].keys = ['a', 'c', 'd'];
  lists[70].patches.push({revision: 2});
  apply(renderer, [{kind: 'delete', tag: 72}, {kind: 'update', tag: 70, props: {dataset: {revision: 2}}, removed: [], recreate: false}, ...row(74, 'd')]);
  assert(!renderer.views.has(72) && removed.isConnected && removed.style.top === '40px' && removed.getAnimations().length === 1 && removed.style.pointerEvents === 'none', 'a removed row stays in place to play item_exiting');
  const exitFrames = removed.getAnimations()[0].effect.getKeyframes();
  assert(String(exitFrames.at(-1).opacity) === '0', `item_exiting fades the row out: ${JSON.stringify(exitFrames)}`);
  const moved = rowEl(73).getAnimations();
  assert(rowEl(73).style.top === '40px' && moved.length === 1 && /^0(px)? 40px$/.test(moved[0].effect.getKeyframes()[0].translate), `a moved row flies from its old offset: ${JSON.stringify(moved.map(a => a.effect.getKeyframes()))}`);
  const entered = rowEl(74).getAnimations();
  assert(rowEl(74).style.top === '80px' && entered.length === 1 && String(entered[0].effect.getKeyframes()[0].opacity) === '0', 'an inserted row plays item_entering');
  assert(!rowEl(71).getAnimations().length, 'a row that stays put does not animate');
  await until(() => !removed.isConnected, 'the exiting row to leave', 1500);
  // Recycling (a row leaves the window without a dataset change) never animates.
  const recycled = rowEl(71);
  apply(renderer, [{kind: 'delete', tag: 71}]);
  assert(!recycled.isConnected, 'a recycled row leaves at once');
  apply(renderer, [{kind: 'delete', tag: 73}, {kind: 'delete', tag: 74}, {kind: 'delete', tag: 70}]);
  stage.remove();
}
