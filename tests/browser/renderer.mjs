// The browser preview's mounting path, end to end in Chrome: commits go to
// the WebAssembly renderer core in the page, which validates, lays out, and
// flattens them, and the DOM renderer applies the mount transactions it
// produces. The assertions read the DOM, the core's replies, and the
// messages the core emits for Python.
import {Renderer, transformToCSS, snapTarget, scrollPayload, keyPressName, screenTransition, stackHeaderHeight} from '../../src/pythonnative/devserver/static/renderer.js';
import {RendererCore, CoreHost, PROTOCOL_VERSION, decodeTransaction, decodeWrites} from '../../src/pythonnative/devserver/static/core/mount.js';
import {PreviewHost, Screen, localeRecord, scriptResult} from '../../src/pythonnative/devserver/static/host.js';
import {runDevToolsTests} from './devtools.mjs';
const assert = (condition, message) => { if (!condition) throw Error(message); };
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const until = async (condition, ms = 3000) => { for (const end = performance.now() + ms; !condition(); await sleep(10)) if (performance.now() > end) throw Error(`timed out waiting for ${condition}`); };
const frames = (n = 2) => new Promise(resolve => { const step = () => (n-- <= 0 ? resolve() : requestAnimationFrame(step)); step(); });
const same = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}
const FIXTURES = '../../src/pythonnative/native/ios/Tests/PythonNativeKitTests/Fixtures';

// ---------------------------------------------------------------------------
// The WebAssembly core against the shared fixtures.
// ---------------------------------------------------------------------------
const core = await RendererCore.load();
assert(core.protocolVersion() === PROTOCOL_VERSION, `the core speaks protocol ${core.protocolVersion()}`);
const fixtures = await (await fetch('../contracts/validation.json')).json();
for (const item of fixtures) assert(core.checkValue(item.schema, item.value) === item.valid, `contract fixture: ${item.name}`);
// The JavaScript decoder reads the transactions the host core recorded the way Python does.
const recorded = await (await fetch(`${FIXTURES}/mount.json`)).json();
for (const item of recorded) {
  const decoded = decodeTransaction(Uint8Array.from(atob(item.bytes), c => c.charCodeAt(0)));
  assert(decoded.surface === item.surface && decoded.revision === item.revision && decoded.id === item.id, `transaction header: ${item.name}`);
  assert(same(decoded.ops, item.ops), `decoded ops match Python's: ${item.name}: ${JSON.stringify(decoded.ops)}`);
}
const writes = new Uint8Array([2,0,0,0, 7,0,0,0,0,0,0,0, 7,0,0,0, ...new TextEncoder().encode('opacity'), 4, 0,0,0,0,0,0,224,63,
  7,0,0,0,0,0,0,0, 16,0,0,0, ...new TextEncoder().encode('background_color'), 5, 4,0,0,0, ...new TextEncoder().encode('#fff')]);
assert(same(decodeWrites(writes), [[7, 'opacity', 0.5], [7, 'background_color', '#fff']]), 'animated writes decode');
const contracts = await (await fetch(`${FIXTURES}/contracts.json`)).text();
assert(core.loadContracts(contracts) === null && core.fingerprint() !== '', 'the core compiles the contract document');

const messages = [], events = [], overlay = document.createElement('div'); document.body.append(overlay);
const renderer = new Renderer({scheme: () => 'light', overlays: () => overlay, bottomInset: () => 0, frameWidth: () => 390,
  pointInFrame: (event) => { const r = event.currentTarget.getBoundingClientRect(); return {x: event.clientX - r.left, y: event.clientY - r.top}; },
  pointInWindow: (event) => ({x: event.clientX, y: event.clientY}), statusBar() {}});
const mount = new CoreHost(core, renderer, {send: (kind, tag, name, payload) => {
  messages.push([kind, tag, name, payload]);
  if (kind === 'event') events.push([tag, name, JSON.parse(payload)]);
}});

// The list trace through the core: patches validate in the commit and publish to the mount side.
let traceRevision = 0, traceCreated = false;
const traceCommit = (op) => JSON.parse(core.commit(JSON.stringify({version:PROTOCOL_VERSION, application:'list-trace', surface:3, revision:traceRevision + 1, ops:[op]})));
for (const step of await (await fetch('../contracts/list-trace.json')).json()) {
  const ack = traceCommit(traceCreated ? ['u', 1, {dataset: step.packet}, []] : ['c', 1, 'VirtualList', {dataset: step.packet}]);
  assert(ack.ok === step.valid, `list trace ${step.name}: ${JSON.stringify(ack)}`);
  if (ack.ok) { traceRevision++; traceCreated = true; }
  mount.drain();
  const keys = Array.from({length: core.listCount(3, 1)}, (_, i) => core.listKey(3, 1, i));
  assert(same(keys, step.keys) && core.listRevision(3, 1) === step.revision, `atomic ${step.name}: ${JSON.stringify(keys)} r${core.listRevision(3, 1)}`);
}
traceCommit(['d', 1]); mount.drain();

let revision = 0;
const envelope = (ops, layout) => ({version:PROTOCOL_VERSION, application:'browser-test', surface:1, revision:revision+1, ops, ...(layout ? {layout} : {})});
const submit = (ops, layout) => { const ack = JSON.parse(core.commit(JSON.stringify(envelope(ops, layout)))); if (ack.ok) revision++; mount.drain(); return ack; };
const commit = (ops, layout) => { const ack = submit(ops, layout); assert(ack.ok, `${ack.error} in ${JSON.stringify(ops)}`); return ack; };
const layout = (roots, width, height, selective = false) => {
  const reply = JSON.parse(core.layout(JSON.stringify({surface:1, roots, width, height, selective})));
  assert(reply.ok, JSON.stringify(reply)); mount.drain(); return reply.value;
};
const command = (tag, name, args = {}) => {
  const callId = 1000 + messages.length;
  const reply = JSON.parse(core.command(1, tag, name, JSON.stringify(args), callId));
  assert(reply.ok, JSON.stringify(reply)); mount.drain();
  const result = messages.filter(([kind]) => kind === 'command').map(([, , , payload]) => JSON.parse(payload)).find(body => body.call_id === callId);
  assert(result, `command ${name} answered`); return result;
};
const emitted = (tag, name) => events.filter(([t, n]) => t === tag && n === name).map(([, , body]) => body.args);

commit([['c',1,'Column',{width:300}], ['c',2,'TextInput',{value:'hello', multiline:false, font_size:20,
  _pn_events:['on_change','on_selection_change']}], ['i',1,2,0], ['c',3,'Text',{text:'Label',color:'#ff0000'}], ['i',1,3,1]]);
document.body.append(renderer.views.get(1).el);
const first = layout([1], 300, 500);
assert(first.application==='browser-test' && first.revision===revision && first.frames.length===3, `layout identity: ${JSON.stringify(first)}`);
const textFrame = first.frames.find(frame => frame[0] === 3);
assert(textFrame[2] === 36 && textFrame[3] === 300 && textFrame[4] > 15 && textFrame[4] < 30, `the page measures text and inputs for the core: ${JSON.stringify(first.frames)}`);
assert(renderer.views.get(3).el.style.top === '36px' && renderer.views.get(3).el.style.width === '300px', 'mounted frames come from the core');
const original = renderer.views.get(2).el; original.focus(); original.setSelectionRange(1,3);
commit([['u',2,{multiline:true},[]]]);
let input = renderer.views.get(2).el;
assert(input !== original && input.tagName==='TEXTAREA','creation-only property replaces native control');
assert(input.value==='hello' && input.selectionStart===1 && input.selectionEnd===3,'replacement preserves text and selection');
assert(document.activeElement===input && input.parentElement===renderer.views.get(1).el,'replacement retains focus and parent');
assert(input.style.width !== '', 'replacement retains layout');
commit([['u',3,{},["color"]]]);
assert(renderer.views.get(3).props.color === undefined && renderer.views.get(3).el.style.color === '','removed color restores platform default');
const before = renderer.views.get(3).el;
const rejected = submit([['u',3,{text:'must not publish'},[]],['u',2,{typo:true},[]]]);
assert(!rejected.ok && rejected.failed === false && rejected.op === 1 && /typo/.test(rejected.error), `the core names the rejected op and prop: ${JSON.stringify(rejected)}`);
assert(renderer.views.get(3).el===before && renderer.views.get(3).props.text==='Label' && before.textContent === 'Label','invalid transaction is atomic');
const stale = JSON.parse(core.commit(JSON.stringify({...envelope([]), revision})));
assert(!stale.ok, 'a stale revision is rejected');
input.dispatchEvent(new CompositionEvent('compositionstart'));
commit([['u',2,{value:'controlled',_pn_edit_revision:0},[]]]);
assert(input.value==='hello','controlled update waits for composition');
input.dispatchEvent(new CompositionEvent('compositionend'));
assert(input.value==='controlled','controlled update publishes at composition end');
input.value='typed'; input.dispatchEvent(new Event('input', {bubbles:true}));
const change = events.find(([tag,name]) => tag===2 && name==='on_change')?.[2];
assert(change && change.edit_revision===1 && change.application==='browser-test' && change.revision===revision && change.sequence > 0 && change.args[0]==='typed',
  `the core stamps input with identity and a monotonic edit revision: ${JSON.stringify(change)}`);
commit([['u',2,{value:'stale',_pn_edit_revision:0},[]]]);
assert(input.value==='typed','stale controlled update rejected');
const container = renderer.views.get(1).el;
commit([['u',1,{background_color:'#eeeeee'},[]]]); commit([['u',1,{},["background_color"]]]);
assert(renderer.views.get(1).el===container && renderer.views.get(1).el.contains(input),'property reset retains container and children');
commit([['d',2],['d',3],['d',1]]);
assert(renderer.views.size===0,'teardown releases records');

// View flattening: a layout-only wrapper isn't mounted; its children move into
// the nearest mounted ancestor at the flattened offset, and a paint prop mounts it.
commit([['c',30,'Column',{width:200, padding:10}], ['c',31,'View',{padding:5}], ['i',30,31,0], ['c',32,'Text',{text:'Flat'}], ['i',31,32,0]]);
document.body.append(renderer.views.get(30).el);
layout([30], 200, 300);
assert(!renderer.views.has(31) && renderer.views.get(32).el.parentElement === renderer.views.get(30).el, 'a layout-only View is flattened');
assert(renderer.views.get(32).frame.x === 15 && renderer.views.get(32).frame.y === 15, `children of a flattened view carry its offset: ${JSON.stringify(renderer.views.get(32).frame)}`);
commit([['u',31,{background_color:'#00ff00'},[]]]);
assert(renderer.views.get(31) && renderer.views.get(32).el.parentElement === renderer.views.get(31).el && renderer.views.get(32).frame.x === 5, 'a paint prop mounts the view and adopts its children');
assert(JSON.parse(core.command(1, 999, 'focus', '{}', 1)).ok === false, 'commands to unknown views fail in the core');
commit([['d',32], ['d',31], ['d',30]]);

// ---------------------------------------------------------------------------
// RFC 0002: props, events, and modules the preview implements, driven
// through validated commits against the generated schema.
// ---------------------------------------------------------------------------
const stage = document.createElement('div');
stage.style.cssText = 'position:relative;width:390px;height:600px;overflow:hidden';
document.body.append(stage);
const place = (tag, x, y, w, h) => { const view = renderer.views.get(tag); view.frame = {x, y, w, h}; view.manager.frame(view, x, y, w, h); return view; };
const pointer = (el, type, x, y, extra = {}) => el.dispatchEvent(new PointerEvent(type, {bubbles:true, button:0, pointerId:1, clientX:x, clientY:y, ...extra}));
// Headless Chrome moves `document.activeElement` on `.focus()` but withholds
// the focus events while the page itself isn't focused; when the real event
// did not fire, dispatch the ones a focused page would have.
const focusEl = (el) => {
  let fired = false;
  const seen = () => { fired = true; };
  el.addEventListener('focus', seen);
  const previous = document.activeElement;
  el.focus();
  el.removeEventListener('focus', seen);
  if (fired || document.activeElement !== el) return;
  if (previous && previous !== document.body) { previous.dispatchEvent(new FocusEvent('blur')); previous.dispatchEvent(new FocusEvent('focusout', {bubbles:true})); }
  el.dispatchEvent(new FocusEvent('focus')); el.dispatchEvent(new FocusEvent('focusin', {bubbles:true}));
};
const key = (el, k, extra = {}) => el.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true, cancelable:true, key:k, ...extra}));

// Transforms and border style.
assert(transformToCSS([{perspective: 500}, {rotate_x: 30}, {rotate_y: '0.5rad'}, {rotate_z: 10}, {skew_x: 5}, {skew_y: '2deg'}]) ===
  'perspective(500px) rotateX(30deg) rotateY(0.5rad) rotateZ(10deg) skewX(5deg) skewY(2deg)', 'transform builder covers the 3D operations');
assert(transformToCSS([{rotate: 45}, {perspective: 100}]) === 'perspective(100px) rotate(45deg)', 'perspective is hoisted first');
commit([['c',10,'View',{width:100, height:40, border_width:2, border_color:'#000000'}]]);
stage.append(renderer.views.get(10).el); place(10, 0, 0, 100, 40);
commit([['u',10,{border_style:'dashed'},[]]]);
assert(renderer.views.get(10).el.style.borderTopStyle === 'dashed' && renderer.views.get(10).el.style.borderLeftStyle === 'dashed', 'border_style applies to every side');
commit([['u',10,{border_style:'dotted'},[]]]);
assert(renderer.views.get(10).el.style.borderTopStyle === 'dotted', 'border_style updates');

// Accessibility props.
commit([['u',10,{accessibility_live_region:'assertive', accessibility_value:{min:0, max:10, now:5}},[]]]); const a11y = renderer.views.get(10);
assert(a11y.el.getAttribute('aria-live') === 'assertive' && a11y.el.getAttribute('aria-atomic') === 'true', 'live region maps to aria-live');
assert(a11y.el.getAttribute('aria-valuemin') === '0' && a11y.el.getAttribute('aria-valuemax') === '10' && a11y.el.getAttribute('aria-valuenow') === '5', 'accessibility_value maps to aria-value*');
commit([['u',10,{accessibility_value:'half way'},[]]]);
assert(a11y.el.getAttribute('aria-valuetext') === 'half way' && !a11y.el.hasAttribute('aria-valuenow'), 'string accessibility_value is aria-valuetext');
commit([['u',10,{},['accessibility_live_region']]]);
assert(!a11y.el.hasAttribute('aria-live'), 'live region clears');
commit([['u',10,{accessibility_actions:[{name:'activate'}, {name:'increment', label:'More'}], _pn_events:['on_accessibility_action']},[]]]);
assert(a11y.el.dataset.pnActions === '["activate","increment"]' && a11y.el.tabIndex === 0, 'actions are exposed and make the view focusable');
a11y.el.focus(); key(a11y.el, 'Enter');
assert(JSON.stringify(emitted(10, 'on_accessibility_action')) === '[["activate"]]', 'Enter fires the activate action');
commit([['u',10,{important_for_accessibility:'no_hide_descendants'},[]]]);
assert(a11y.el.getAttribute('aria-hidden') === 'true', 'no_hide_descendants hides the subtree');
commit([['u',10,{important_for_accessibility:'no'},[]]]);
assert(!a11y.el.hasAttribute('aria-hidden') && a11y.el.getAttribute('role') === 'presentation' && a11y.el.tabIndex === -1, 'no drops the view from the tree');
commit([['u',10,{important_for_accessibility:'auto'},[]]]);
assert(!a11y.el.hasAttribute('role') && a11y.el.tabIndex === 0, 'auto restores the defaults');

// Pressable: disabled, delay_long_press.
commit([['c',11,'Pressable',{width:100, height:40, _pn_events:['on_press','on_long_press','on_press_in']}]]);
const pressable = renderer.views.get(11); stage.append(pressable.el); place(11, 0, 50, 100, 40);
const rect = () => pressable.el.getBoundingClientRect();
commit([['u',11,{disabled:true},[]]]);
assert(pressable.el.getAttribute('aria-disabled') === 'true' && pressable.el.tabIndex === -1, 'disabled exposes aria-disabled');
pointer(pressable.el, 'pointerdown', rect().left + 5, rect().top + 5); pointer(pressable.el, 'pointerup', rect().left + 5, rect().top + 5);
assert(emitted(11, 'on_press').length === 0 && emitted(11, 'on_press_in').length === 0 && pressable.el.style.opacity === '', 'disabled pressable ignores presses and pressed styling');
commit([['u',11,{disabled:false, delay_long_press:60},[]]]);
assert(!pressable.el.hasAttribute('aria-disabled'), 'enabling clears aria-disabled');
pointer(pressable.el, 'pointerdown', rect().left + 5, rect().top + 5);
assert(pressable.el.style.opacity === '0.6', 'pressed styling while held');
pointer(pressable.el, 'pointerup', rect().left + 5, rect().top + 5);
assert(emitted(11, 'on_press').length === 1 && pressable.el.style.opacity === '', 'a quick press fires on_press');
pointer(pressable.el, 'pointerdown', rect().left + 5, rect().top + 5);
await sleep(120);
pointer(pressable.el, 'pointerup', rect().left + 5, rect().top + 5);
assert(emitted(11, 'on_long_press').length === 1 && emitted(11, 'on_press').length === 1, 'delay_long_press fires on_long_press instead of on_press');

// ScrollView: payload, phases, throttling, snapping, keyboard behavior.
assert(JSON.stringify(Object.keys(scrollPayload(stage))) === '["x","y","content_width","content_height","viewport_width","viewport_height"]', 'ScrollEvent payload keys');
assert(snapTarget(140, 100, 'start', 300, 1000) === 100 && snapTarget(160, 100, 'start', 300, 1000) === 200, 'snap start aligns to the interval');
assert(snapTarget(130, 100, 'center', 300, 1000) === 100 && snapTarget(50, 100, 'end', 300, 1000) === 100, 'snap center/end shift by the viewport');
assert(snapTarget(950, 100, 'start', 300, 1000) === 700 && snapTarget(10, 0, 'start', 300, 1000) === null, 'snap clamps to the range and is off without an interval');
commit([['c',12,'ScrollView',{width:200, height:100, _pn_events:['on_scroll','on_scroll_begin_drag','on_scroll_end_drag','on_momentum_scroll_end']}],
  ['c',13,'View',{height:600}], ['i',12,13,0], ['c',14,'TextInput',{value:'', multiline:false}], ['i',13,14,0]]);
const scroller = renderer.views.get(12); stage.append(scroller.el); place(12, 0, 100, 200, 100);
layout([12], 390, 600);
assert(renderer.views.get(13).frame.h === 600 && scroller.content.style.height === '600px', `the content size follows the core's frames: ${scroller.content.style.height}`);
commit([['u',12,{horizontal:false, scroll_enabled:false},[]]]);
assert(scroller.el.style.overflowY === 'hidden', 'scroll_enabled=False hides overflow');
commit([['u',12,{scroll_enabled:true, keyboard_dismiss_mode:'on_drag', scroll_event_throttle:0},[]]]);
assert(scroller.el.style.overflowY === 'auto', 'scroll_enabled=True restores scrolling');
commit([['u',12,{content_inset:{top:10, bottom:20}},[]]]);
assert(scroller.content.style.paddingTop === '10px' && scroller.content.style.paddingBottom === '20px', 'content_inset pads the content');
const inner = renderer.views.get(14).el; inner.focus();
assert(document.activeElement === inner, 'input focused before drag');
scroller.el.scrollTop = 50; scroller.el.dispatchEvent(new Event('scroll'));
assert(document.activeElement !== inner, 'keyboard_dismiss_mode=on_drag blurs the input on the first scroll');
// Chrome also fires its own `scroll` (and `scrollend`) after a programmatic
// `scrollTop` write, so counts below are relative, not absolute.
let scrolls = emitted(12, 'on_scroll');
assert(scrolls.length === 1 && scrolls[0][0].y === 50 && scrolls[0][0].viewport_height === 100 && scrolls[0][0].content_height >= 600 && !('extent' in scrolls[0][0]), 'on_scroll carries the ScrollEvent payload');
assert(emitted(12, 'on_scroll_begin_drag').length === 1, 'first movement begins the drag');
await sleep(250);
assert(emitted(12, 'on_scroll_end_drag').length === 1 && emitted(12, 'on_momentum_scroll_end').length === 1, 'idle ends the drag and the momentum');
scrolls = emitted(12, 'on_scroll');
assert(scrolls.length >= 2 && scrolls.at(-1)[0].y === 50 && emitted(12, 'on_momentum_scroll_end')[0][0].y === 50, 'settling reports the final offset');
commit([['u',12,{scroll_event_throttle:1000},[]]]);
const beforeBurst = emitted(12, 'on_scroll').length;
for (let y = 60; y < 70; y++) { scroller.el.scrollTop = y; scroller.el.dispatchEvent(new Event('scroll')); }
const afterBurst = emitted(12, 'on_scroll').length;
assert(afterBurst - beforeBurst <= 1, 'scroll_event_throttle drops intermediate events');
await sleep(250);
assert(emitted(12, 'on_scroll').length === afterBurst + 1 && emitted(12, 'on_scroll').at(-1)[0].y === 69 && emitted(12, 'on_momentum_scroll_end').length === 2, 'the settle still reports the final offset after a throttled burst');
commit([['u',12,{snap_to_interval:100, snap_to_alignment:'start', scroll_event_throttle:0},[]]]);
const beforeSnap = emitted(12, 'on_momentum_scroll_end').length;
scroller.el.scrollTop = 140; scroller.el.dispatchEvent(new Event('scroll'));
await sleep(900);
assert(Math.abs(scroller.el.scrollTop - 100) < 1, 'snap_to_interval settles on the interval');
const momentumEnds = emitted(12, 'on_momentum_scroll_end');
assert(momentumEnds.length === beforeSnap + 1 && Math.abs(momentumEnds.at(-1)[0].y - 100) < 1 && Math.abs(emitted(12, 'on_scroll').at(-1)[0].y - 100) < 1, 'momentum ends once, at the snapped offset');
assert(Math.abs(command(12, 'get_scroll_offset').value.y - 100) < 1, 'a command result returns asynchronously through the core queue');
inner.focus();
commit([['u',12,{keyboard_should_persist_taps:'never'},['snap_to_interval']]]);
pointer(scroller.el, 'pointerdown', 10, 190);
assert(document.activeElement !== inner, 'keyboard_should_persist_taps=never blurs on a tap elsewhere');
inner.focus();
commit([['u',12,{keyboard_should_persist_taps:'always'},[]]]);
const mousedown = new MouseEvent('mousedown', {bubbles:true, cancelable:true, clientX:10, clientY:190});
scroller.el.dispatchEvent(mousedown);
assert(mousedown.defaultPrevented, 'keyboard_should_persist_taps=always keeps the focus');
pointer(scroller.el, 'pointerdown', 10, 190);
assert(document.activeElement === inner, 'always does not blur on tap');
inner.blur();

// Text: ellipsize_mode, on_press, pressable spans.
commit([['c',15,'Text',{text:'The quick brown fox jumps over the lazy dog again and again', max_lines:1, _pn_events:['on_press','on_span_press']}]]);
const text = renderer.views.get(15); stage.append(text.el); place(15, 0, 220, 120, 22);
assert(text.el.classList.contains('pn-clamp-1') && text.el.style.textOverflow === '', 'tail is the browser ellipsis');
commit([['u',15,{ellipsize_mode:'clip'},[]]]);
assert(text.el.style.textOverflow === 'clip', 'clip cuts without an ellipsis');
commit([['u',15,{ellipsize_mode:'head'},[]]]);
assert(text.el.textContent.startsWith('…') && text.el.textContent.endsWith('again') && text.el.scrollWidth <= text.el.clientWidth,
  `head truncation keeps the end: ${JSON.stringify(text.el.textContent)} scroll=${text.el.scrollWidth} client=${text.el.clientWidth}`);
commit([['u',15,{ellipsize_mode:'middle'},[]]]);
const middle = text.el.textContent;
assert(middle.startsWith('The') && middle.endsWith('again') && middle.includes('…') && middle.length < text.props.text.length, 'middle truncation keeps both ends');
const [measuredW] = renderer.measure({tag:15, component:'Text', mode:1, props:{...text.props}, width:0, widthMode:0, height:0, heightMode:0});
assert(measuredW > 200 && text.el.textContent === middle, 'measurement uses a prototype with the full text and leaves the truncation alone');
place(15, 0, 220, 900, 22); commit([['u',15,{ellipsize_mode:'head'},[]]]);
assert(text.el.textContent === text.props.text && text.truncated === null, 'no truncation when the text fits');
text.el.click();
assert(emitted(15, 'on_press').length === 1, 'label click fires on_press');
commit([['u',15,{spans:[{text:'Read the '}, {text:'terms', pressable:true, color:'#0066ff'}, {text:'.'}]},[]]]);
const span = text.el.children[1];
assert(span.getAttribute('role') === 'link' && span.tabIndex === 0 && text.el.children[0].getAttribute('role') == null, 'pressable spans render as links');
span.click();
assert(JSON.stringify(emitted(15, 'on_span_press')) === '[[1]]' && emitted(15, 'on_press').length === 1, 'span click fires on_span_press with its index and not on_press');
key(span, 'Enter');
assert(emitted(15, 'on_span_press').length === 2, 'Enter on a focused span presses it');

// TextInput: key press, selection, select on focus, blur on submit, keyboard types, content size.
commit([['c',16,'TextInput',{value:'hello world', multiline:false, _pn_events:['on_key_press','on_submit','on_selection_change']}]]);
const field = renderer.views.get(16); stage.append(field.el); place(16, 0, 260, 200, 36);
key(field.el, 'a'); key(field.el, 'Backspace'); key(field.el, 'Shift'); key(field.el, 'ArrowLeft');
assert(JSON.stringify(emitted(16, 'on_key_press')) === '[[{"key":"a"}],[{"key":"Backspace"}]]', 'on_key_press reports characters, Backspace, and Enter only');
assert(keyPressName('Enter') === 'Enter' && keyPressName('é') === 'é' && keyPressName('Tab') === null, 'key names');
commit([['u',16,{selection:{start:1, end:4}},[]]]);
assert(field.el.selectionStart === 1 && field.el.selectionEnd === 4, 'controlled selection applies');
field.lastSelection = {start:2, end:2};
commit([['u',16,{selection:{start:2, end:2}},[]]]);
assert(field.el.selectionStart === 1 && field.el.selectionEnd === 4, 'an echoed selection does not move the caret');
commit([['u',16,{selection:{start:100, end:200}},[]]]);
assert(field.el.selectionStart === 11 && field.el.selectionEnd === 11, 'selection clamps to the value');
commit([['u',16,{select_text_on_focus:true},[]]]);
field.el.blur(); focusEl(field.el);
assert(field.el.selectionStart === 0 && field.el.selectionEnd === 11 && emitted(16, 'on_focus').length === 1,
  `select_text_on_focus selects everything: ${field.el.selectionStart}-${field.el.selectionEnd}`);
const mouseup = new MouseEvent('mouseup', {bubbles:true, cancelable:true});
field.el.dispatchEvent(mouseup);
assert(mouseup.defaultPrevented && !new MouseEvent('mouseup', {cancelable:true}).defaultPrevented, 'the focusing click does not collapse the selection');
const mouseup2 = new MouseEvent('mouseup', {bubbles:true, cancelable:true}); field.el.dispatchEvent(mouseup2);
assert(!mouseup2.defaultPrevented, 'later clicks place the caret normally');
key(field.el, 'Enter');
assert(JSON.stringify(emitted(16, 'on_submit')) === '[["hello world"]]' && document.activeElement !== field.el, 'Enter submits and blurs a single-line input by default');
commit([['u',16,{blur_on_submit:false},[]]]); field.el.focus(); key(field.el, 'Enter');
assert(emitted(16, 'on_submit').length === 2 && document.activeElement === field.el, 'blur_on_submit=False keeps the focus');
field.el.blur();
commit([['u',16,{keyboard_type:'web_search'},[]]]);
assert(field.el.type === 'search' && field.el.inputMode === 'search', 'web_search keyboard');
commit([['u',16,{keyboard_type:'numbers_and_punctuation'},[]]]);
assert(field.el.type === 'text' && field.el.inputMode === 'decimal', 'numbers_and_punctuation keyboard');
commit([['u',16,{keyboard_type:'visible_password'},[]]]);
assert(field.el.type === 'text' && field.el.autocomplete === 'off', 'visible_password shows the text');
commit([['u',16,{keyboard_type:'ascii'},[]]]);
assert(field.el.type === 'text' && field.el.inputMode === 'text', 'ascii keyboard');
commit([['u',16,{secure:true},[]]]);
assert(field.el.type === 'password', 'secure wins over keyboard_type');
// clear() is an edit: it reports the empty string so a controlled value follows.
commit([['c',67,'TextInput',{value:'draft', multiline:false, _pn_events:['on_change']}]]);
const cleared = command(67, 'clear');
assert(cleared.ok && renderer.views.get(67).el.value === '' && JSON.stringify(emitted(67, 'on_change')) === '[[""]]', 'clear() empties the field and reports on_change');
renderer.views.get(67).el.value = 'typed';
assert(command(67, 'get_value').value === 'typed', 'get_value answers with what the field holds');
commit([['d',67]]);
commit([['c',17,'TextInput',{value:'one\ntwo\nthree\nfour', multiline:true, _pn_events:['on_content_size_change','on_submit']}]]);
const area = renderer.views.get(17); stage.append(area.el); place(17, 0, 300, 200, 40);
const sizes = emitted(17, 'on_content_size_change');
assert(sizes.length === 1 && sizes[0][0].width > 180 && sizes[0][0].width <= 200 && sizes[0][0].height > 40, 'multiline reports its content size once laid out');
area.el.value += '\nfive\nsix'; area.el.dispatchEvent(new Event('input', {bubbles:true}));
assert(emitted(17, 'on_content_size_change').length === 2 && emitted(17, 'on_content_size_change')[1][0].height > sizes[0][0].height, 'content size follows the text');
area.el.focus(); const enter = new KeyboardEvent('keydown', {bubbles:true, cancelable:true, key:'Enter'}); area.el.dispatchEvent(enter);
assert(!enter.defaultPrevented && emitted(17, 'on_submit').length === 0, 'multiline Enter inserts a newline by default');
commit([['u',17,{blur_on_submit:true},[]]]); const enter2 = new KeyboardEvent('keydown', {bubbles:true, cancelable:true, key:'Enter'}); area.el.dispatchEvent(enter2);
assert(enter2.defaultPrevented && emitted(17, 'on_submit').length === 1 && document.activeElement !== area.el, 'multiline blur_on_submit submits and blurs on Enter');
// A multiline input grows with its text: input invalidates its measurement in the core.
commit([['c',40,'Column',{width:200}], ['c',41,'TextInput',{multiline:true}], ['i',40,41,0]]);
document.body.append(renderer.views.get(40).el);
layout([40], 200, 800);
const grow = renderer.views.get(41), short = grow.frame.h;
grow.el.value = 'one\ntwo\nthree\nfour\nfive\nsix\nseven'; grow.el.dispatchEvent(new Event('input', {bubbles:true}));
mount.flush();
assert(grow.frame.h > short, `an uncontrolled multiline input relayouts as it grows: ${short} -> ${grow.frame.h}`);
assert(messages.some(([kind]) => kind === 'layout'), 'a native-initiated relayout reports observed frames to Python');
commit([['d',41], ['d',40]]);

// Image: load lifecycle, fade, and the loaded size the core lays out with.
const PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
// A view emitting while its create applies is born in that revision: the
// event must carry it, or Python drops it as older than the view.
commit([['c',19,'Image',{width:10, height:10, source:'data:image/gif;base64,R0lGODlhAQABAAAAACw=', _pn_events:['on_load_start']}]]);
const startEnvelope = events.filter(([t, n]) => t === 19 && n === 'on_load_start').map(([, , body]) => body)[0];
assert(startEnvelope && startEnvelope.revision === revision && startEnvelope.application === 'browser-test', 'events emitted during a mount carry its revision');
commit([['d',19]]);
commit([['c',18,'Image',{width:10, height:10, _pn_events:['on_load_start','on_load_end','on_load']}]]);
const image = renderer.views.get(18); stage.append(image.el);
commit([['u',18,{fade_duration:200, source:PIXEL},[]]]);
assert(emitted(18, 'on_load_start').length === 1 && image.img.style.opacity === '0', 'on_load_start fires when the source is set and fade starts transparent');
await new Promise(resolve => image.img.complete && image.img.naturalWidth ? resolve() : image.img.addEventListener('load', resolve, {once:true}));
await frames(2);
assert(emitted(18, 'on_load').length === 1 && emitted(18, 'on_load_end').length === 1 && image.img.style.opacity === '1' && image.img.style.transition.includes('200ms'), 'on_load_end follows on_load and the image fades in');
commit([['u',18,{source:'data:image/png;base64,broken'},[]]]);
await new Promise(resolve => image.img.addEventListener('error', resolve, {once:true}));
await sleep(0);
assert(emitted(18, 'on_load_start').length === 2 && emitted(18, 'on_load_end').length === 2, 'a failed load still ends the load');
commit([['c',42,'Column',{width:300}], ['c',43,'Image',{source:PIXEL}], ['i',42,43,0]]);
layout([42], 300, 400);
const loaded = renderer.views.get(43);
await until(() => emitted(43, 'on_load').length);
mount.flush();
assert(loaded.frame && loaded.frame.w === 300 && loaded.frame.h === 1, `an image without a height lays out at its loaded size: ${JSON.stringify(loaded.frame)}`);
commit([['d',43], ['d',42]]);

// Modal: Escape asks Python to close, only when wired.
commit([['c',19,'Modal',{visible:true}]]);
document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true, cancelable:true}));
assert(emitted(19, 'on_request_close').length === 0 && emitted(19, 'on_show').length === 1, 'Escape does nothing without on_request_close');
commit([['u',19,{_pn_events:['on_request_close']},[]]]);
document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true, cancelable:true}));
assert(emitted(19, 'on_request_close').length === 1, 'Escape fires on_request_close');
renderer.views.get(19).backdrop.click();
assert(emitted(19, 'on_request_close').length === 2, 'backdrop tap fires on_request_close');
commit([['u',19,{visible:false},[]]]);
document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true, cancelable:true}));
assert(emitted(19, 'on_request_close').length === 2 && emitted(19, 'on_dismiss').length === 1, 'a hidden modal ignores Escape');

// Modal: children survive closing, lay out against the sheet, and an overlay's empty area is its backdrop.
overlay.style.cssText = 'position:relative;width:390px;height:800px';
commit([['c',21,'Modal',{visible:false, presentation_style:'overlay', _pn_events:['on_request_close']}], ['c',22,'Text',{text:'Modal body'}], ['i',21,22,0]]);
const reopened = renderer.views.get(21);
commit([['u',21,{visible:true},[]]]);
commit([['u',21,{visible:false},[]]]);
commit([['u',21,{visible:true},[]]]);
assert(reopened.backdrop.isConnected && reopened.sheet.contains(renderer.views.get(22).el), 'a reopened modal still shows its children');
layout([21], 390, 600); mount.flush();
assert(renderer.views.get(22).frame?.w === reopened.sheet.clientWidth, `modal content lays out against the sheet: ${JSON.stringify(renderer.views.get(22).frame)} ${reopened.sheet.clientWidth}`);
renderer.views.get(22).el.click();
assert(emitted(21, 'on_request_close').length === 0, 'a tap on overlay content is not a backdrop tap');
reopened.sheet.click();
assert(emitted(21, 'on_request_close').length === 1, 'a tap on an overlay outside its children asks to close');
commit([['u',21,{dismiss_on_backdrop:false},[]]]);
reopened.sheet.click();
assert(emitted(21, 'on_request_close').length === 1, 'dismiss_on_backdrop=False ignores backdrop taps');
commit([['d',22], ['d',21]]);
overlay.style.cssText = '';

// VirtualList: on_scroll only when wired.
commit([['c',20,'VirtualList',{width:200, height:100, dataset:{base:0,revision:1,changes:[['reset',[['a',1,44,false],['b',1,44,false],['c',1,44,true],['d',1,44,false]]]]}, _pn_events:['on_bind_row']}]]);
const list = renderer.views.get(20); stage.append(list.el); place(20, 0, 0, 200, 100);
list.el.dispatchEvent(new Event('scroll'));
assert(emitted(20, 'on_scroll').length === 0, 'unwired VirtualList on_scroll stays quiet');
commit([['u',20,{_pn_events:['on_bind_row','on_scroll']},[]]]);
list.el.dispatchEvent(new Event('scroll'));
assert(emitted(20, 'on_scroll').length === 1 && 'viewport_height' in emitted(20, 'on_scroll')[0][0], 'wired VirtualList on_scroll carries typed geometry');
const windows = emitted(20, 'on_window');
assert(windows.length && windows.at(-1)[0].revision === 1 && windows.at(-1)[0].range === 176 && windows.at(-1)[0].first === 0, `the list reports its window from the core's dataset: ${JSON.stringify(windows.at(-1))}`);

// One-row patches publish through the core; rows stack at measured extents.
commit([['u',20,{dataset:{base:1,revision:2,changes:[['u',['a',2,55,false]]]}},[]]]);
assert(list.rows.revision === 2 && list.rows.keys.join() === 'a,b,c,d' && core.listExtent(1, 20, 0) === 55 && list.rows.offsets[1] === 55, 'one-row update keeps the order and takes the new extent');
const patch = {base:2,revision:3,changes:[['u',['a',3,60,false]]]};
assert(!submit([['u',20,{dataset:patch},[]],['u',20,{dataset:patch},[]]]).ok, 'duplicate patch rejects atomically');
assert(list.rows.revision === 2 && core.listRevision(1, 20) === 2, 'rejected patch does not publish');
commit([['c',50,'View',{_pn_list_key:'a', height:30}], ['i',20,50,0], ['c',51,'View',{_pn_list_key:'b', height:20, background_color:'#ff0000'}], ['i',20,51,1]]);
layout([20], 200, 100);
assert(renderer.views.get(50).frame.w === 200 && renderer.views.get(50).frame.h === 30, `rows lay out as detached roots at the list's width: ${JSON.stringify(renderer.views.get(50).frame)}`);
assert(renderer.views.get(51).el.style.top === '30px' && list.spacer.style.height === `${30 + 20 + 44 + 44}px`, `rows stack at their measured extents: ${renderer.views.get(51).el.style.top} ${list.spacer.style.height}`);
commit([['u',20,{dataset:{base:2,revision:3,changes:[['m','b',0]]}},[]]]);
assert(list.rows.keys.join() === 'b,a,c,d' && renderer.views.get(50).el.style.top === '20px', 'a move reorders the rows');
assert(list.el.querySelector('[data-pn-tag="51"]').style.zIndex === '', 'only the sticky row floats');
commit([['d',50], ['d',51], ['u',20,{horizontal:false},[]]]);
// A recreated list (a creation-only prop) starts from the dataset the core already holds.
const recreatedBefore = list.el;
commit([['u',20,{horizontal:true},[]]]);
assert(list.el !== recreatedBefore || list.rows.revision === 3, 'the list keeps its published dataset');
assert(list.rows.keys.join() === 'b,a,c,d' && list.rows.revision === 3, `a recreated list reads the core's dataset: ${list.rows.keys} r${list.rows.revision}`);

// Selective geometry and removal of an override retain the shorthand.
commit([['c',980,'Column',{width:300,padding:20,padding_left:30}], ['c',981,'Text',{text:'Observed',_pn_layout:true}], ['i',980,981,0]]);
let selective = layout([980], 300, 400, true);
assert(selective.frames.length === 1 && selective.frames[0][0] === 981 && selective.frames[0][1] === 30, `only observed geometry crosses: ${JSON.stringify(selective.frames)}`);
commit([['u',980,{},['padding_left']]]);
selective = layout([980], 300, 400, true);
assert(selective.frames.length === 0 && renderer.views.get(981).frame.x === 20, 'shorthand survives removal of edge override (the commit laid it out)');
commit([['u',981,{color:'#ff0000'},[]]]);
assert(layout([980], 300, 400, true).frames.length === 0, 'paint has no layout work');
const observing = commit([['u',980,{_pn_layout:true},[]]], {roots:[980], width:300, height:400, selective:true});
assert(observing.layout.frames.length === 1 && observing.layout.frames[0][0] === 980, `a new observer receives the cached frame: ${JSON.stringify(observing.layout)}`);
const ack = commit([['u',981,{text:'Observed\non two lines'},[]]], {roots:[980], width:300, height:400, selective:true});
assert(ack.layout && ack.layout.frames.some(frame => frame[0] === 981) && ack.metrics.validate_ns >= 0, `a commit acknowledges with observed frames: ${JSON.stringify(ack.layout)}`);
const measured = JSON.parse(core.measure(1, 981));
assert(measured.frame[0] === 20 && measured.window.length === 4, `the core answers measure_in_window from the shadow tree: ${JSON.stringify(measured)}`);
commit([['d',981],['d',980]]);

// ScreenStack: presentation and animation.
assert(screenTransition({}) === 'pn-screen-right' && screenTransition({presentation:'modal'}) === 'pn-screen-bottom', 'default transitions by presentation');
assert(screenTransition({presentation:'form_sheet'}) === 'pn-screen-bottom' && screenTransition({presentation:'transparent_modal'}) === 'pn-screen-bottom', 'sheets slide from the bottom');
assert(screenTransition({animation:'fade'}) === 'pn-screen-fade' && screenTransition({animation:'none'}) === null, 'explicit animations');
assert(screenTransition({presentation:'modal', animation:'slide_from_right'}) === 'pn-screen-right' && screenTransition({animation:'slide_from_bottom'}) === 'pn-screen-bottom', 'animation wins over presentation');
assert(stackHeaderHeight({}) === 44 && stackHeaderHeight({header_large_title:true}) === 96 && stackHeaderHeight({header_shown:false}) === 0, 'stack header heights');
commit([['c',21,'ScreenStack',{}], ['c',22,'Screen',{presentation:'card', active:false}], ['i',21,22,0],
  ['c',23,'Screen',{presentation:'transparent_modal', active:true}], ['i',21,23,1]]);
stage.append(renderer.views.get(21).el); place(21, 0, 0, 390, 600);
const [card, sheet] = renderer.views.get(21).children;
assert(card.el.style.display === '' && sheet.el.style.display === '' && sheet.el.classList.contains('pn-screen-transparent'), 'a transparent modal keeps the screen beneath visible');
commit([['u',22,{active:false},[]], ['c',24,'Screen',{presentation:'card', active:true, animation:'fade'}], ['i',21,24,2]]);
const third = renderer.views.get(24);
assert(card.el.style.display === 'none' && sheet.el.style.display === '' && third.el.style.display === '' && third.el.classList.contains('pn-screen-fade'), 'a pushed card enters with its animation over the screen it covers');
await frames(3);
assert(!third.el.classList.contains('pn-screen-fade') && !sheet.el.classList.contains('pn-under'), 'the enter class is released after a frame; a fade leaves the covered screen in place');
await sleep(350);
assert(sheet.el.style.display === 'none' && card.el.style.display === 'none', 'the covered screens leave the stage once the push lands');
commit([['d',24]]);
const ghost = renderer.views.get(21).el.querySelector('.pn-screen-ghost');
assert(ghost && card.el.style.display === '' && sheet.el.style.display === '' && renderer.views.get(21).children.length === 2, 'a pop leaves a snapshot to animate out and reveals the stack beneath');
await sleep(350);
assert(!renderer.views.get(21).el.querySelector('.pn-screen-ghost'), 'the snapshot is removed after the transition');
commit([['d',23], ['d',22], ['d',21]]);

// ScreenStack: the navigation bar follows the top screen's options.
commit([['c',60,'ScreenStack',{_pn_events:['on_native_back']}],
  ['c',61,'Screen',{title:'Inbox', header_style:{background_color:'#112233'}}], ['i',60,61,0]]);
const navStack = renderer.views.get(60); stage.append(navStack.el); place(60, 0, 0, 390, 600);
assert(navStack.titleEl.textContent === 'Inbox' && navStack.back.style.display === 'none' && navStack.body.style.top === '44px', 'the root screen shows its title and no back button');
assert(navStack.header.style.background.includes('rgb(17, 34, 51)'), 'header_style.background_color paints the bar');
commit([['c',62,'Screen',{title:'Detail', header_tint_color:'#ff0000', header_title_style:{color:'#00ff00'}}], ['i',60,62,1],
  ['c',63,'View',{_pn_header_slot:'right', height:44}], ['i',62,63,0], ['c',64,'Text',{text:'Edit'}], ['i',63,64,0]]);
assert(navStack.titleEl.textContent === 'Detail' && navStack.back.style.display === '' && navStack.back.textContent === 'Inbox', 'a pushed screen gets a back button labeled with the previous title');
assert(navStack.back.style.color === 'rgb(255, 0, 0)' && navStack.titleEl.style.color === 'rgb(0, 255, 0)', 'header tint and title colors apply');
assert(renderer.views.get(63).el.parentNode === navStack.right, 'a header_right slot moves into the bar');
navStack.back.click();
assert(JSON.stringify(emitted(60, 'on_native_back')) === '[[1]]', 'the back button asks Python to pop one screen');
commit([['u',61,{title:'A much longer inbox title'},[]]]);
assert(navStack.back.textContent === 'Back', 'a long previous title falls back to "Back", as in UIKit');
commit([['u',61,{header_back_title:'Every message in the inbox'},[]], ['u',62,{title:'A detail title that fills the bar'},[]]]);
assert(navStack.back.textContent === 'Back' && navStack.back.getAttribute('aria-label') === 'Every message in the inbox', 'a back title that would hit the title shortens to "Back" and keeps its accessible name');
navStack.el.style.width = '200px';
commit([['u',62,{title:'A detail title that fills the narrow bar'},[]]]);
assert(navStack.back.textContent === '' && navStack.back.classList.contains('pn-stack-back-chevron'), `with no room for "Back" the chevron stands alone: ${JSON.stringify([navStack.back.textContent, navStack.titleEl.offsetWidth, navStack.right.offsetWidth])}`);
navStack.el.style.width = '390px';
commit([['u',61,{},['header_back_title']]]);
commit([['u',62,{title:'Detail'},[]]]);
commit([['u',62,{header_shown:false},[]]]);
assert(navStack.header.style.display === 'none' && navStack.body.style.top === '0px', 'header_shown false hides the bar');
commit([['u',62,{header_shown:true, header_large_title:true},[]]]);
assert(navStack.header.classList.contains('pn-stack-large') && navStack.body.style.top === '96px', 'a large title grows the bar');
layout([60], 390, 600); mount.flush();
assert(renderer.views.get(62).frame.h === 600 - 96 && renderer.views.get(61).frame.h === 600 - 44, `each screen lays out in the container it reports, below its bar: ${renderer.views.get(62).frame.h} ${renderer.views.get(61).frame.h}`);
assert(renderer.views.get(63).frame.h === 44 && renderer.views.get(63).frame.w < 60, `header slots are laid out at the bar height and their content's width: ${JSON.stringify(renderer.views.get(63).frame)}`);
commit([['d',64], ['d',63], ['d',62], ['d',61], ['d',60]]);
navStack.el.remove();

// ScreenStack: a card push slides over the covered screen, which parallaxes aside; a pop reveals it the same way.
commit([['c',710,'ScreenStack',{}], ['c',711,'Screen',{title:'List'}], ['i',710,711,0]]);
const cardStack = renderer.views.get(710); stage.append(cardStack.el); place(710, 0, 0, 390, 600);
const listScreen = renderer.views.get(711);
commit([['c',712,'Screen',{title:'Item'}], ['i',710,712,1]]);
const itemScreen = renderer.views.get(712);
assert(itemScreen.el.classList.contains('pn-screen-right') && listScreen.el.style.display === '', 'a push starts the new card off stage and keeps the covered screen up');
await frames(3);
assert(!itemScreen.el.classList.contains('pn-screen-right') && listScreen.el.classList.contains('pn-under'), 'the card slides in while the covered screen moves aside');
await sleep(350);
assert(listScreen.el.style.display === 'none' && !listScreen.el.classList.contains('pn-under'), 'the covered screen leaves the stage once the push lands');
commit([['d',712]]);
assert(listScreen.el.style.display === '' && listScreen.el.classList.contains('pn-under') && !listScreen.el.classList.contains('pn-screen-right'), 'a pop reveals the screen beneath from its parallax position, not as a push');
await frames(2);
assert(!listScreen.el.classList.contains('pn-under'), 'the revealed screen slides back into place');
commit([['d',711], ['d',710]]);
cardStack.el.remove();

// Leaf views paint background_color and honor display and z_index.
commit([['c',700,'Image',{width:40, height:40, background_color:'#ff0000', placeholder_color:'#00ff00'}],
  ['c',701,'ActivityIndicator',{background_color:'#0000ff', z_index:3}], ['c',702,'Button',{title:'Hidden', display:'none'}]]);
assert(renderer.views.get(700).el.style.backgroundColor === 'rgb(255, 0, 0)', 'Image background_color wins over placeholder_color');
commit([['u',700,{},['background_color']]]);
assert(renderer.views.get(700).el.style.backgroundColor === 'rgb(0, 255, 0)', 'without background_color the placeholder fill shows');
assert(renderer.views.get(701).el.style.backgroundColor === 'rgb(0, 0, 255)' && renderer.views.get(701).el.style.zIndex === '3', 'leaf views paint background_color and z_index');
assert(renderer.views.get(702).el.style.display === 'none', 'display none hides a leaf view');
commit([['d',700], ['d',701], ['d',702]]);

// Intrinsic leaves measure on a prototype built from their props.
commit([['c',720,'Row',{width:390, flex_direction:'row', align_items:'flex_start'}], ['c',721,'Switch',{value:true}], ['i',720,721,0],
  ['c',722,'Button',{title:'A wide button title'}], ['i',720,722,1], ['c',723,'ActivityIndicator',{size:'large'}], ['i',720,723,2]]);
layout([720], 390, 200);
assert(renderer.views.get(721).frame.w === 51 && renderer.views.get(721).frame.h === 31, `a Switch measures at the platform size: ${JSON.stringify(renderer.views.get(721).frame)}`);
assert(renderer.views.get(722).frame.w > 100 && renderer.views.get(722).frame.x === 51, `a Button measures its title: ${JSON.stringify(renderer.views.get(722).frame)}`);
assert(renderer.views.get(723).frame.w === 37, 'an ActivityIndicator measures by its size');
commit([['d',721], ['d',722], ['d',723], ['d',720]]);

// Switch keeps its intrinsic size; Slider paints its minimum track.
commit([['c',703,'Switch',{value:true}], ['c',704,'Slider',{value:0.25, min_value:0, max_value:1, _pn_events:['on_change']}]]);
const switchView = renderer.views.get(703); stage.append(switchView.el); place(703, 0, 0, 300, 40);
assert(switchView.el.style.width === '51px' && switchView.el.style.height === '31px', 'a stretched Switch keeps the platform switch size');
const sliderView = renderer.views.get(704);
assert(sliderView.el.style.getPropertyValue('--pn-fill') === '25%', 'the minimum track fills up to the value');
sliderView.el.value = '0.75'; sliderView.el.dispatchEvent(new Event('input'));
assert(sliderView.el.style.getPropertyValue('--pn-fill') === '75%' && emitted(704, 'on_change').length === 1, 'dragging moves the fill and reports the value');
switchView.el.remove();
commit([['d',703], ['d',704]]);

// RefreshControl: pulling down at the top fires on_refresh; the spinner holds while refreshing.
commit([['c',705,'ScrollView',{width:200, height:100, refresh_control:{refreshing:false}, _pn_events:['on_refresh']}], ['c',706,'View',{height:300}], ['i',705,706,0]]);
const refresher = renderer.views.get(705); stage.append(refresher.el); place(705, 0, 0, 200, 100);
assert(refresher.refresh && refresher.refresh.style.opacity !== '1' && !refresher.el.querySelector('button'), 'the refresh indicator stays hidden at rest');
const wheel = (deltaY) => refresher.el.dispatchEvent(new WheelEvent('wheel', {deltaY, bubbles:true, cancelable:true}));
wheel(-20);
assert(refresher.pull > 0 && refresher.content.style.transform.startsWith('translateY(') && emitted(705, 'on_refresh').length === 0, 'a short pull moves the content without refreshing');
for (let i = 0; i < 8; i++) wheel(-30);
assert(emitted(705, 'on_refresh').length === 1, 'pulling past the threshold fires on_refresh once');
commit([['u',705,{refresh_control:{refreshing:true}},[]]]);
await sleep(200);
assert(refresher.content.style.transform === 'translateY(56px)' && refresher.refreshSpinner.classList.contains('pn-refresh-spinning'), 'the spinner holds in view while refreshing');
commit([['u',705,{refresh_control:{refreshing:false}},[]]]);
assert(refresher.content.style.transform === '' && !refresher.refreshSpinner.classList.contains('pn-refresh-spinning'), 'the content springs back when the refresh ends');
refresher.el.scrollTop = 50; wheel(-30);
assert(refresher.pull === 0, 'scrolling up through content is plain scrolling');
commit([['d',706], ['d',705]]);
refresher.el.remove();

// Portal content lays out against the whole overlay, so absolute insets pin it to the screen edges.
overlay.style.cssText = 'position:relative;flex:none;width:390px;height:800px';
commit([['c',707,'Portal',{}], ['c',708,'View',{position:'absolute', left:24, right:24, bottom:40, height:50, background_color:'#000000'}], ['i',707,708,0]]);
mount.flush();
layout([707], 390, 600);
const banner = renderer.views.get(708).frame;
assert(banner.x === 24 && banner.w === 342 && banner.y === 710 && banner.h === 50, `portal insets resolve against the overlay: ${JSON.stringify(banner)}`);
commit([['d',708], ['d',707]]);
overlay.style.cssText = '';

// Modal: presenting and dismissing animate (animation_type), and "none" is instant.
commit([['c',709,'Modal',{visible:true}]]);
const sliding = renderer.views.get(709);
assert(sliding.backdrop.dataset.animation === 'slide', 'a modal slides by default');
commit([['u',709,{visible:false},[]]]);
assert(sliding.backdrop.isConnected && sliding.backdrop.classList.contains('pn-modal-out'), 'a dismissed modal animates out before it leaves the stage');
await sleep(400);
assert(!sliding.backdrop.isConnected, 'the dismissed modal leaves the stage after its transition');
commit([['u',709,{animation_type:'none', visible:true},[]]]);
commit([['u',709,{visible:false},[]]]);
assert(!sliding.backdrop.isConnected, 'animation_type none dismisses at once');
commit([['d',709]]);

// Animation: the core's drivers run on the page's frame clock and write to the views.
const animation = (id) => messages.filter(([kind]) => kind === 'animation').map(([, , , payload]) => JSON.parse(payload)).filter(body => body.id === id);
const declined = JSON.parse(core.animate(1, 10, JSON.stringify({op:'start', id:901, prop:'opacity', spec:{kind:'timing', to:0, duration_ms:100, easing:'nope'}})));
assert(declined.ok === false && /easing/.test(declined.error), `a timing animation with an unknown easing is declined: ${JSON.stringify(declined)}`);
assert(JSON.parse(core.animate(1, 10, JSON.stringify({op:'start', id:902, prop:'opacity', spec:{kind:'timing', from:1, to:0.25, duration_ms:80, easing:'linear'}}))).ok, 'the core queues an animation');
mount.drain();
await sleep(250); await frames(2);
assert(renderer.views.get(10).el.style.opacity === '0.25' && animation(902).some(body => body.finished === true), `a timing animation finishes at its target: ${renderer.views.get(10).el.style.opacity} ${JSON.stringify(animation(902))}`);
assert(JSON.parse(core.animate(1, 10, JSON.stringify({op:'start', id:903, prop:'translate_x', spec:{kind:'spring', to:40, stiffness:400, damping:30}}))).ok, 'a spring starts');
mount.drain();
await sleep(600); await frames(2);
const springX = parseFloat(/translateX\(([-\d.]+)px\)/.exec(renderer.views.get(10).el.style.transform)?.[1]);
assert(Math.abs(springX - 40) < 0.5, `a spring settles on its target: ${renderer.views.get(10).el.style.transform}`);
JSON.parse(core.animate(1, 10, JSON.stringify({op:'set', prop:'background_color', value:'#00ff00'}))); mount.drain();
assert(renderer.views.get(10).el.style.backgroundColor === 'rgb(0, 255, 0)', 'a set writes the value directly');
JSON.parse(core.animate(1, 10, JSON.stringify({op:'start', id:904, prop:'opacity', spec:{kind:'timing', to:1, duration_ms:5000}}))); mount.drain();
await frames(3);
JSON.parse(core.animate(1, 10, JSON.stringify({op:'cancel', id:904}))); mount.drain();
await frames(2);
assert(animation(904).some(body => body.finished === false), 'a cancelled animation reports that it did not finish');

// TabBar: the contract's styling props.
commit([['c',26,'TabBar',{items:[{name:'home', title:'Home'}, {name:'inbox', title:'Inbox', badge:'3'}], active_tab:'inbox', tint_color:'#ff0000', inactive_tint_color:'#00ff00', translucent:false, shows_labels:false}]]);
const tabbar = renderer.views.get(26); stage.append(tabbar.el);
assert(tabbar.el.style.getPropertyValue('--pn-tab-active').includes('255, 0, 0') && tabbar.el.classList.contains('pn-opaque') && tabbar.el.classList.contains('pn-no-labels'), 'tint_color, translucent, shows_labels');
const [homeTab, inboxTab] = tabbar.el.querySelectorAll('button');
assert(inboxTab.classList.contains('pn-active') && !homeTab.classList.contains('pn-active') && homeTab.style.color.includes('0, 255, 0') && inboxTab.querySelector('.pn-badge').textContent === '3', 'active_tab and inactive_tint_color');
homeTab.click();
assert(JSON.stringify(emitted(26, 'on_tab_select')) === '[["home"]]', 'tab presses report the tab name');

// Gestures: pointer events go to the core's gesture engine in the page.
commit([['c',25,'View',{width:100, height:100, gestures:[{kind:'tap'}]}]]);
const target = renderer.views.get(25); stage.append(target.el); place(25, 50, 400, 100, 100);
const box = target.el.getBoundingClientRect();
assert(core.hasGestures(1, 25), 'the core holds the view gestures');
pointer(target.el, 'pointerdown', box.left + 20, box.top + 30);
pointer(target.el, 'pointerup', box.left + 20, box.top + 30);
const taps = emitted(25, 'gesture:0').map(args => args[0]);
const tap = taps.find(body => body.state === 'ended');
assert(tap && tap.kind === 'tap' && Math.abs(tap.x - 20) < 0.01 && Math.abs(tap.y - 30) < 0.01 && Math.abs(tap.absolute_x - (box.left + 20)) < 0.01 && Math.abs(tap.absolute_y - (box.top + 30)) < 0.01,
  `a tap is recognized with view and window coordinates: ${JSON.stringify(taps)}`);
commit([['u',25,{gestures:[{kind:'long_press', min_duration_ms:60}]},[]]]);
pointer(target.el, 'pointerdown', box.left + 10, box.top + 10);
await sleep(150);
const held = emitted(25, 'gesture:0').map(args => args[0]).filter(body => body.kind === 'long_press');
assert(held.length > 0, `a long press fires from the gesture deadline timer: ${JSON.stringify(held)}`);
pointer(target.el, 'pointerup', box.left + 10, box.top + 10);
commit([['u',25,{gestures:[{kind:'pan'}]},[]]]);
pointer(target.el, 'pointerdown', box.left + 10, box.top + 10);
for (let step = 1; step <= 5; step++) pointer(target.el, 'pointermove', box.left + 10 + step * 8, box.top + 10);
pointer(target.el, 'pointerup', box.left + 50, box.top + 10);
const pans = emitted(25, 'gesture:0').map(args => args[0]).filter(body => body.kind === 'pan');
assert(pans.some(body => body.state === 'changed' && body.translation_x > 0) && pans.at(-1).state === 'ended', `a pan reports its translation: ${JSON.stringify(pans.map(body => body.state))}`);
commit([['d',25]]);

// Host modules: Device, Keyboard, AccessibilityInfo, Localization, header options, viewport payload.
const callbacks = [];
const screensEl = document.createElement('div'), overlaysEl = document.createElement('div'); stage.append(screensEl, overlaysEl);
const host = new PreviewHost({bridge:{request: async () => null, callback: (...args) => callbacks.push(args), send() {}}, renderer, screensEl, overlaysEl,
  frameMetrics: () => ({width:744, height:1133, top:24, bottomInset:20, leftInset:0, rightInset:0}), deviceName: () => 'iPad mini', projectName: () => 'demo',
  scheme: () => 'light', color: (value) => value == null ? null : String(value), statusBar() {}, log() {}, toast() {}});
const call = async (module, method, args = {}) => JSON.parse(await host.call(module, method, JSON.stringify({args})));
const info = (await call('Device', 'info')).value;
assert(JSON.stringify(Object.keys(info).sort()) === JSON.stringify(['app_name','app_version','build_number','bundle_id','font_scale','is_simulator','is_tablet','locale','manufacturer','model','os_version','platform','scale']), 'Device.info returns exactly the DeviceInfo keys');
assert(info.platform === 'web' && info.model === 'iPad mini' && info.manufacturer === 'Browser' && info.is_simulator === true && info.is_tablet === true && info.bundle_id === 'demo' && info.app_name === 'demo' && info.font_scale === 1 && info.build_number === '0' && info.app_version === '0.0.0', 'Device.info values');
assert((await call('Clipboard', 'has_string')).code === 'unknown_method' && (await call('Linking', 'get_initial_url')).code === 'unknown_method', 'dead browser methods are gone');
const locales = (await call('Localization', 'get_locales')).value;
assert(Array.isArray(locales) && locales.length && typeof locales[0].language_tag === 'string' && 'is_rtl' in locales[0] && 'region_code' in locales[0] && 'language_code' in locales[0], 'Localization.get_locales');
assert(typeof (await call('Localization', 'get_timezone')).value === 'string', 'Localization.get_timezone');
const arabic = localeRecord('ar-EG'), english = localeRecord('en_US');
assert(arabic.is_rtl === true && arabic.region_code === 'EG' && arabic.language_code === 'ar' && english.is_rtl === false && english.language_code === 'en', 'locale records');
assert((await call('AccessibilityInfo', 'is_screen_reader_enabled')).value === false && typeof (await call('AccessibilityInfo', 'is_reduce_motion_enabled')).value === 'boolean', 'AccessibilityInfo readers');
await call('AccessibilityInfo', 'announce', {message:'Saved'}); await sleep(0);
assert(document.querySelector('.pn-live-region').textContent === 'Saved' && document.querySelector('.pn-live-region').getAttribute('aria-live') === 'polite', 'announce writes into the live region');
// Module methods run synchronously inside `host.call`; read focus state
// right away, before the unfocused headless page resets it.
const focusing = call('AccessibilityInfo', 'set_accessibility_focus', {tag:10});
const focusedByModule = document.activeElement;
await focusing;
assert(focusedByModule === renderer.views.get(10).el, 'set_accessibility_focus focuses the view');
const hostInput = document.createElement('input'); screensEl.append(hostInput);
document.activeElement?.blur?.();
assert((await call('Keyboard', 'is_visible')).value === false, 'keyboard hidden while nothing is focused');
focusEl(hostInput);
const visibleWhileFocused = call('Keyboard', 'is_visible');
assert((await visibleWhileFocused).value === true, 'a focused input shows the keyboard');
const keyboardEvents = callbacks.filter(([kind, , module]) => kind === 'module' && module === 'Keyboard').map(([, , , payload]) => JSON.parse(payload));
assert(keyboardEvents.length === 1 && keyboardEvents[0].event === 'change' && JSON.stringify(keyboardEvents[0].payload) === '{"height":0,"visible":true,"duration_ms":0}', 'Keyboard.change payload');
focusEl(hostInput);
await call('Keyboard', 'dismiss');
assert(document.activeElement !== hostInput && (await call('Keyboard', 'is_visible')).value === false, 'Keyboard.dismiss blurs the input');
// WebViews.eval_js answers with the script's result, stringified like the natives.
assert(scriptResult(undefined) === '' && scriptResult(null) === '' && scriptResult('hi') === 'hi' && scriptResult(42) === '42' && scriptResult(true) === 'true' && scriptResult([1, 2]) === '[1,2]', 'script results stringify like the native modules');
commit([['c',68,'WebView',{html:'<p>page</p>', width:100, height:80}]]);
const webView = renderer.views.get(68); stage.append(webView.el); place(68, 0, 0, 100, 80);
await new Promise(resolve => webView.iframe.contentDocument?.readyState === 'complete' ? resolve() : webView.iframe.addEventListener('load', resolve, {once:true}));
const evaluated = await call('WebViews', 'eval_js', {tag:68, script:'1 + 41'});
assert(evaluated.ok !== false && evaluated.value === '42', `eval_js answers from the page: ${JSON.stringify(evaluated)}`);
commit([['d',68]]); webView.el.remove();
const screen = new Screen(host, 99, null, null, {});
const viewport = screen.viewport();
assert(viewport.screen_width === 744 && viewport.screen_height === 1133 && viewport.font_scale === 1 && viewport.scale === (window.devicePixelRatio || 1) && viewport.width === 744 && viewport.height === 1133 - 24 - 44 && JSON.stringify(viewport.insets) === '{"top":0,"left":0,"bottom":20,"right":0}', 'viewport payload carries scale, font_scale, the screen size, and the device status bar and insets');
screen.applyOptions({title:'Inbox', header_style:{background_color:'rgb(255, 0, 0)'}, header_back_visible:false, header_tint_color:'rgb(0, 128, 0)', header_title_style:{color:'rgb(1, 2, 3)'}});
assert(screen.header.style.background.includes('rgb(255, 0, 0)') && screen.back.style.visibility === 'hidden' && screen.back.style.color === 'rgb(0, 128, 0)' && screen.title.style.color === 'rgb(1, 2, 3)' && screen.title.textContent === 'Inbox', 'header reads header_style.background_color and header_back_visible');
assert(screen.transition() === 'pn-screen-right' && new Screen(host, 98, null, null, {presentation:'modal'}).transition() === 'pn-screen-bottom', 'host screens use the same transitions');
// A root-level native stack draws its own bar, so the host header yields (as on iOS).
commit([['c',65,'ScreenStack',{}], ['c',66,'Screen',{title:'Root'}], ['i',65,66,0]]);
const topBefore = screen.contentTop();
screen.attachRoot(renderer.views.get(65));
assert(screen.stackOwnsHeader && screen.header.style.display === 'none' && screen.contentTop() === topBefore - 44, 'a root native stack hides the host header');
screen.detachRoot(renderer.views.get(65));
assert(!screen.stackOwnsHeader && screen.header.style.display === '' && screen.contentTop() === topBefore, 'the host header returns with the stack gone');
commit([['d',66], ['d',65]]);
// A module call mounts what Python committed first: attach_root sees a view whose commit hasn't drained.
host.stack.push(screen);
core.commit(JSON.stringify(envelope([['c',69,'View',{}]]))); revision++;
assert(!renderer.views.has(69), 'mounting waits for the UI turn');
assert((await call('Host', 'attach_root', {screen:99, tag:69})).ok !== false && screen.root === renderer.views.get(69), 'Host.attach_root drains pending mounts');
screen.detachRoot(renderer.views.get(69)); host.stack.pop();
commit([['d',69]]);
// A plugin component without a browser widget mounts as a labeled placeholder.
assert(renderer.measure({tag:5000, component:'InboxBadge', mode:3, props:{}, width:300, widthMode:2, height:0, heightMode:0})[1] === 44, 'a native measurement without a browser widget measures the placeholder');

// RFC 0006: DevSupport, the structured error screen, and DevTools helpers.
await runDevToolsTests({renderer, host, commit, callbacks, call, stage, screensEl, overlaysEl});
// A mount failure fails the surface and tells Python, which remounts.
const failures = messages.length;
renderer.applyOp = () => { throw new Error('boom'); };
commit([['c',70,'View',{}]]);
const failed = messages.slice(failures).find(([kind, , name]) => kind === 'host' && name === 'surface_failed');
assert(failed && JSON.parse(failed[3]).error.includes('boom'), `a failed mount reports surface_failed: ${JSON.stringify(messages.slice(failures))}`);
delete renderer.applyOp;
mount.reset();
assert(renderer.views.size === 0 && core.fingerprint() === '', 'a reset forgets the views, the surfaces, and the contracts');
const result=document.getElementById('result'); result.dataset.status='passed';
result.textContent=`${fixtures.length} contract fixtures, ${recorded.length} recorded transactions, and the renderer acceptance assertions passed`;
