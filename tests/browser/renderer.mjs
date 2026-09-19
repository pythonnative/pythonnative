import {Renderer, transformToCSS, easingFor, decayFinalValue, decayAt, snapTarget, scrollPayload, keyPressName, screenTransition} from '../../src/pythonnative/devserver/static/renderer.js';
import {PreviewHost, Screen, localeRecord, scriptResult} from '../../src/pythonnative/devserver/static/host.js';
import {matches} from '../../src/pythonnative/devserver/static/contracts.js';
const assert = (condition, message) => { if (!condition) throw Error(message); };
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const fixtures = await (await fetch('../contracts/validation.json')).json();
for (const item of fixtures) assert(matches(item.value, item.schema) === item.valid, item.name);
const events = [], gestures = [], overlay = document.createElement('div'); document.body.append(overlay);
const renderer = new Renderer({emit: (...args) => events.push(args), gesture: (...args) => gestures.push(args), request() {},
  animationFinished() {}, scheme: () => 'light', overlays: () => overlay, bottomInset: () => 0,
  frameWidth: () => 390, pointInFrame: () => ({x:0, y:0}), statusBar() {}});
let revision = 0;
const envelope = ops => ({version:3, application:'browser-test', surface:1, revision:revision+1, ops});
const commit = ops => { const result=renderer.apply(envelope(ops)); assert(result.ok, result.error); revision++; };
commit([['c',1,'Column',{width:300}], ['c',2,'TextInput',{value:'hello', multiline:false, font_size:20,
  _pn_events:['on_change','on_selection_change']}], ['i',1,2,0], ['c',3,'Text',{text:'Label',color:'#ff0000'}], ['i',1,3,1]]);
document.body.append(renderer.views.get(1).el);
const layout = renderer.computeLayout({roots:[1],width:300,height:500});
assert(layout.application==='browser-test' && layout.revision===revision && layout.frames.length===3,'layout identity');
const original = renderer.views.get(2).el; original.focus(); original.setSelectionRange(1,3);
commit([['u',2,{multiline:true},[]]]);
let input = renderer.views.get(2).el;
assert(input !== original && input.tagName==='TEXTAREA','creation-only property replaces native control');
assert(input.value==='hello' && input.selectionStart===1 && input.selectionEnd===3,'replacement preserves text and selection');
assert(document.activeElement===input && input.parentElement===renderer.views.get(1).el,'replacement retains focus and parent');
assert(input.style.width !== '', 'replacement retains layout');
commit([['u',3,{},["color"]]]);
assert(renderer.views.get(3).props.color === undefined,'removed color restores platform default');
const before = renderer.views.get(3).el;
const rejected = renderer.apply(envelope([['u',3,{text:'must not publish'},[]],['u',2,{typo:true},[]]]));
assert(!rejected.ok && renderer.views.get(3).el===before && renderer.views.get(3).props.text==='Label','invalid transaction is atomic');
assert(!renderer.apply({...envelope([]), surface:2}).ok,'foreign surface rejected');
input.dispatchEvent(new CompositionEvent('compositionstart'));
commit([['u',2,{value:'controlled',_pn_edit_revision:0},[]]]);
assert(input.value==='hello','controlled update waits for composition');
input.dispatchEvent(new CompositionEvent('compositionend'));
assert(input.value==='controlled','controlled update publishes at composition end');
input.value='typed'; input.dispatchEvent(new Event('input', {bubbles:true}));
assert(events.some(([tag,name,body]) => tag===2 && name==='on_change' && body.edit_revision===1),'input emits monotonic edit revision');
commit([['u',2,{value:'stale',_pn_edit_revision:0},[]]]);
assert(input.value==='typed','stale controlled update rejected');
const container = renderer.views.get(1).el;
commit([['u',1,{background_color:'#eeeeee'},[]]]); commit([['u',1,{},["background_color"]]]);
assert(renderer.views.get(1).el===container && renderer.views.get(1).el.contains(input),'property reset retains container and children');
commit([['d',2],['d',3],['d',1]]);
assert(renderer.views.size===0,'teardown releases records');

// ---------------------------------------------------------------------------
// RFC 0002: props, events, and modules the preview implements, driven
// through validated commits against the generated schema.
// ---------------------------------------------------------------------------
const stage = document.createElement('div');
stage.style.cssText = 'position:relative;width:390px;height:600px;overflow:hidden';
document.body.append(stage);
const place = (tag, x, y, w, h) => { const view = renderer.views.get(tag); view.frame = {x, y, w, h}; view.manager.frame(view, x, y, w, h); return view; };
const emitted = (tag, name) => events.filter(([t, n]) => t === tag && n === name).map(([, , body]) => body.args);
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
const scroller = renderer.views.get(12); stage.append(scroller.el); place(12, 0, 100, 200, 100); place(13, 0, 0, 200, 600); place(14, 0, 0, 100, 36);
scroller.manager.childrenChanged(scroller);
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
const [measuredW] = text.manager.measure(text, 1e6, 1e6);
assert(measuredW > 200 && text.el.textContent === middle, 'measure uses the full text and restores the truncation');
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
renderer.command(67, 'clear', '{}');
assert(renderer.views.get(67).el.value === '' && JSON.stringify(emitted(67, 'on_change')) === '[[""]]', 'clear() empties the field and reports on_change');
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

// Image: load lifecycle and fade.
const PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
// A view emitting while its create applies is born in that revision: the
// event must carry it, or Python drops it as older than the view.
commit([['c',19,'Image',{width:10, height:10, source:'data:image/gif;base64,R0lGODlhAQABAAAAACw=', _pn_events:['on_load_start']}]]);
const startEnvelope = events.filter(([t, n]) => t === 19 && n === 'on_load_start').map(([, , body]) => body)[0];
assert(startEnvelope && startEnvelope.revision === revision && startEnvelope.application === 'browser-test', 'events emitted during a commit carry its revision');
commit([['d',19]]);
commit([['c',18,'Image',{width:10, height:10, _pn_events:['on_load_start','on_load_end','on_load']}]]);
const image = renderer.views.get(18); stage.append(image.el);
commit([['u',18,{fade_duration:200, source:PIXEL},[]]]);
assert(emitted(18, 'on_load_start').length === 1 && image.img.style.opacity === '0', 'on_load_start fires when the source is set and fade starts transparent');
await new Promise(resolve => image.img.complete && image.img.naturalWidth ? resolve() : image.img.addEventListener('load', resolve, {once:true}));
await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
assert(emitted(18, 'on_load').length === 1 && emitted(18, 'on_load_end').length === 1 && image.img.style.opacity === '1' && image.img.style.transition.includes('200ms'), 'on_load_end follows on_load and the image fades in');
commit([['u',18,{source:'data:image/png;base64,broken'},[]]]);
await new Promise(resolve => image.img.addEventListener('error', resolve, {once:true}));
await sleep(0);
assert(emitted(18, 'on_load_start').length === 2 && emitted(18, 'on_load_end').length === 2, 'a failed load still ends the load');

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

// Modal: children survive closing, and an overlay's empty area is its backdrop.
commit([['c',21,'Modal',{visible:false, presentation_style:'overlay', _pn_events:['on_request_close']}], ['c',22,'Text',{text:'Modal body'}], ['i',21,22,0]]);
const reopened = renderer.views.get(21);
commit([['u',21,{visible:true},[]]]);
commit([['u',21,{visible:false},[]]]);
commit([['u',21,{visible:true},[]]]);
assert(reopened.backdrop.isConnected && reopened.sheet.contains(renderer.views.get(22).el), 'a reopened modal still shows its children');
renderer.views.get(22).el.click();
assert(emitted(21, 'on_request_close').length === 0, 'a tap on overlay content is not a backdrop tap');
reopened.sheet.click();
assert(emitted(21, 'on_request_close').length === 1, 'a tap on an overlay outside its children asks to close');
commit([['u',21,{dismiss_on_backdrop:false},[]]]);
reopened.sheet.click();
assert(emitted(21, 'on_request_close').length === 1, 'dismiss_on_backdrop=False ignores backdrop taps');
commit([['d',22], ['d',21]]);

// VirtualList: on_scroll only when wired.
commit([['c',20,'VirtualList',{width:200, height:100, keys:['a','b'], count:2, revision:1, _pn_events:['on_bind_row']}]]);
const list = renderer.views.get(20); stage.append(list.el);
list.el.dispatchEvent(new Event('scroll'));
assert(emitted(20, 'on_scroll').length === 0, 'unwired VirtualList on_scroll stays quiet');
commit([['u',20,{_pn_events:['on_bind_row','on_scroll']},[]]]);
list.el.dispatchEvent(new Event('scroll'));
assert(emitted(20, 'on_scroll').length === 1 && 'first' in emitted(20, 'on_scroll')[0][0] && 'viewport_height' in emitted(20, 'on_scroll')[0][0], 'wired VirtualList on_scroll carries the window');

// ScreenStack: presentation and animation.
assert(screenTransition({}) === 'pn-screen-right' && screenTransition({presentation:'modal'}) === 'pn-screen-bottom', 'default transitions by presentation');
assert(screenTransition({presentation:'form_sheet'}) === 'pn-screen-bottom' && screenTransition({presentation:'transparent_modal'}) === 'pn-screen-bottom', 'sheets slide from the bottom');
assert(screenTransition({animation:'fade'}) === 'pn-screen-fade' && screenTransition({animation:'none'}) === null, 'explicit animations');
assert(screenTransition({presentation:'modal', animation:'slide_from_right'}) === 'pn-screen-right' && screenTransition({animation:'slide_from_bottom'}) === 'pn-screen-bottom', 'animation wins over presentation');
commit([['c',21,'ScreenStack',{}], ['c',22,'Screen',{presentation:'card', active:false}], ['i',21,22,0],
  ['c',23,'Screen',{presentation:'transparent_modal', active:true}], ['i',21,23,1]]);
stage.append(renderer.views.get(21).el); place(21, 0, 0, 390, 600);
const [card, sheet] = renderer.views.get(21).children;
assert(card.el.style.display === '' && sheet.el.style.display === '' && sheet.el.classList.contains('pn-screen-transparent'), 'a transparent modal keeps the screen beneath visible');
commit([['u',22,{active:false},[]], ['c',24,'Screen',{presentation:'card', active:true, animation:'fade'}], ['i',21,24,2]]);
const third = renderer.views.get(24);
assert(card.el.style.display === 'none' && sheet.el.style.display === 'none' && third.el.style.display === '' && third.el.classList.contains('pn-screen-fade'), 'a pushed card covers the stack and enters with its animation');
await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve))));
assert(!third.el.classList.contains('pn-screen-fade'), 'the enter class is released after a frame');
commit([['d',24]]);
const ghost = renderer.views.get(21).el.querySelector('.pn-screen-ghost');
assert(ghost && card.el.style.display === '' && sheet.el.style.display === '' && renderer.views.get(21).children.length === 2, 'a pop leaves a snapshot to animate out and reveals the stack beneath');
await sleep(350);
assert(!renderer.views.get(21).el.querySelector('.pn-screen-ghost'), 'the snapshot is removed after the transition');

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
commit([['u',62,{header_shown:false},[]]]);
assert(navStack.header.style.display === 'none' && navStack.body.style.top === '0px', 'header_shown false hides the bar');
commit([['u',62,{header_shown:true, header_large_title:true},[]]]);
assert(navStack.header.classList.contains('pn-stack-large') && navStack.body.style.top === '96px', 'a large title grows the bar');
renderer.computeLayout({roots:[60], width:390, height:600});
assert(renderer.views.get(62).frame.h === 600 - 96 && renderer.views.get(61).frame.h === 600 - 44, 'each screen is laid out below its bar');
assert(renderer.views.get(63).frame.h === 44, 'header slots are laid out at the bar height');
commit([['d',64], ['d',63], ['d',62], ['d',61], ['d',60]]);
navStack.el.remove();

// Animation: easing descriptors and the decay model.
assert(easingFor({easing:'linear'})(0.3) === 0.3 && easingFor({easing:'quad'})(0.5) === 0.25 && easingFor({easing:'cubic'})(0.5) === 0.125, 'named easings');
assert(Math.abs(easingFor({easing:[0, 0, 1, 1]})(0.25) - 0.25) < 1e-3 && easingFor({easing:{bezier:[0, 0, 1, 1]}}) === null && easingFor({easing:[0, 0, 1]}) === null, 'bezier easing is a bare four-number array');
const ease = easingFor({easing:'ease'}), easeOut = easingFor({easing:'ease_out'}), easeInOut = easingFor({easing:'ease_in_out'});
assert(ease(0.5) < 0.5 && ease(0.5) > 0.25 && Math.abs(ease(0.5) - easingFor({easing:'ease_in'})(0.5)) < 1e-9 && easeOut(0.5) > 0.5 && Math.abs(easeInOut(0.5) - 0.5) < 1e-3 && Math.abs(ease(1) - 1) < 1e-6,
  'ease/ease_in are bezier(0.42, 0, 1, 1), ease_out and ease_in_out the CSS keywords');
assert(Math.abs(easingFor({easing:'bounce'})(1) - 1) < 1e-9 && easingFor({}) === easingFor({easing:undefined}) && easingFor({})(0.5) > 0.49 && easingFor({easing:'nope'}) === null, 'bounce ends at 1, missing easing is ease_in_out, unknown names are declined');
const declined = renderer.animate(10, JSON.stringify({op:'start', id:901, prop:'opacity', spec:{kind:'timing', to:0, duration_ms:100, easing:'nope'}}));
assert(declined && declined.ok === false, 'a timing animation with an unknown easing is declined so Python ticks it');
assert(Math.abs(decayFinalValue(10, 2, 0.998) - 1010) < 1e-6 && Math.abs(decayFinalValue(0, -1) - (-500)) < 1e-6, 'decay travels v0 / (1 - deceleration)');
const [far, slow] = decayAt(0, 2, 0.998, 60000);
assert(Math.abs(far - 1000) < 1e-6 && slow < 1e-9 && Math.abs(decayAt(0, 2, 0.998, 1)[0] - 2) < 1e-9, 'decay position and velocity follow v0 * d^t');

// TabBar: the contract's styling props.
commit([['c',26,'TabBar',{items:[{name:'home', title:'Home'}, {name:'inbox', title:'Inbox', badge:'3'}], active_tab:'inbox', tint_color:'#ff0000', inactive_tint_color:'#00ff00', translucent:false, shows_labels:false}]]);
const tabbar = renderer.views.get(26); stage.append(tabbar.el);
assert(tabbar.el.style.getPropertyValue('--pn-tab-active').includes('255, 0, 0') && tabbar.el.classList.contains('pn-opaque') && tabbar.el.classList.contains('pn-no-labels'), 'tint_color, translucent, shows_labels');
const [homeTab, inboxTab] = tabbar.el.querySelectorAll('button');
assert(inboxTab.classList.contains('pn-active') && !homeTab.classList.contains('pn-active') && homeTab.style.color.includes('0, 255, 0') && inboxTab.querySelector('.pn-badge').textContent === '3', 'active_tab and inactive_tint_color');
homeTab.click();
assert(JSON.stringify(emitted(26, 'on_tab_select')) === '[["home"]]', 'tab presses report the tab name');

// Gestures: the pointer stream carries window coordinates.
commit([['c',25,'View',{width:100, height:100, gestures:[{kind:'tap'}]}]]);
const target = renderer.views.get(25); stage.append(target.el); place(25, 50, 400, 100, 100);
const stream = () => gestures.filter(([tag, phase]) => tag === 25 && phase !== 'clear');
pointer(target.el, 'pointerdown', 70, 430);
assert(stream().length === 1 && stream()[0][1] === 'down' && stream()[0][2].absolute_x === 70 && stream()[0][2].absolute_y === 430 && 'x' in stream()[0][2] && Array.isArray(stream()[0][2].specs),
  `pointer payload includes absolute_x / absolute_y: ${JSON.stringify(stream())}`);
pointer(target.el, 'pointerup', 70, 430);
assert(stream().length === 2 && stream()[1][1] === 'up', 'pointer up follows');

// Host modules: Device, Keyboard, AccessibilityInfo, Localization, header options, viewport payload.
const callbacks = [];
const screensEl = document.createElement('div'), overlaysEl = document.createElement('div'); stage.append(screensEl, overlaysEl);
const host = new PreviewHost({bridge:{request: async () => null, callback: (...args) => callbacks.push(args), send() {}}, renderer, screensEl, overlaysEl,
  frameMetrics: () => ({width:744, height:1133, bottomInset:20}), deviceName: () => 'iPad mini', projectName: () => 'demo',
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
assert(viewport.screen_width === 744 && viewport.screen_height === 1133 && viewport.font_scale === 1 && viewport.scale === (window.devicePixelRatio || 1) && viewport.width === 744 && viewport.height === 1133 - 47 - 44, 'viewport payload carries scale, font_scale, and the screen size');
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

const result=document.getElementById('result'); result.dataset.status='passed';
result.textContent=`${fixtures.length} shared fixtures and renderer acceptance assertions passed`;
