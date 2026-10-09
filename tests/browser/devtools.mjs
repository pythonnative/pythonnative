// RFC 0006 in the browser: the preview's DevSupport module, the structured
// development error overlay, and the DevTools page's pure helpers.
// `renderer.mjs` calls `runDevToolsTests` with its renderer and host.

import {flattenTree, revealTarget, visibleForest} from '../../src/pythonnative/devserver/static/devtools/tree.js';
import {groupFrames, phaseLabel, renderReport} from '../../src/pythonnative/devserver/static/devtools/report.js';
import {mergeRecord, prettyBody, splitUrl} from '../../src/pythonnative/devserver/static/devtools/panels/network.js';
import {sampleMetrics, sparkPath} from '../../src/pythonnative/devserver/static/devtools/panels/performance.js';
import {problemKey} from '../../src/pythonnative/devserver/static/devtools/panels/problems.js';
import {launchConfig} from '../../src/pythonnative/devserver/static/devtools/panels/connect.js';
import {FrameMeter} from '../../src/pythonnative/devserver/static/devsupport.js';

const assert = (condition, message) => { if (!condition) throw Error(message); };
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const frame = () => new Promise(resolve => requestAnimationFrame(() => resolve()));

export const SAMPLE_REPORT = {
  level: 'error', phase: 'render', type: 'ZeroDivisionError', message: 'division by zero',
  title: 'ZeroDivisionError in render: division by zero',
  component_stack: [{name: 'Counter', file: 'app/main.py', line: 14}, {name: 'StackNavigator', file: null, line: null}, {name: 'App', file: 'app/main.py', line: 52}],
  frames: [
    {file: '/venv/pythonnative/reconciler/core.py', line: 900, function: '_render', code: 'rendered = component.render(element)', title: '/venv/pythonnative/reconciler/core.py:900 in _render', excerpt: '', framework: true},
    {file: '/venv/pythonnative/component.py', line: 296, function: 'render', code: 'return self.fn()', title: '/venv/pythonnative/component.py:296 in render', excerpt: '', framework: true},
    {file: 'app/main.py', line: 15, function: 'Counter', code: 'value = 1 / 0', title: 'app/main.py:15 in Counter',
      excerpt: '  14 | def Counter():\n> 15 |     value = 1 / 0\n  16 |     return pn.Text(value)', framework: false},
  ],
  text: 'Traceback (most recent call last):\n  ...\nZeroDivisionError: division by zero',
  timestamp: 0,
};

export async function runDevToolsTests({renderer, host, commit, callbacks, call, stage, screensEl, overlaysEl}) {
  // ------------------------------------------------------------------
  // DevSupport: the module table, highlight, inspector, monitor, stats.
  // ------------------------------------------------------------------
  stage.scrollIntoView();
  const saved = [screensEl.style.cssText, overlaysEl.style.cssText];
  // Earlier tests leave views in the stage; lift the screens above them.
  screensEl.style.cssText = 'position:absolute;left:0;top:0;width:390px;height:600px;z-index:1000';
  overlaysEl.style.cssText = 'position:absolute;left:0;top:0;width:390px;height:600px;z-index:1001';
  overlaysEl.className = 'pn-overlays';
  const moduleEvents = (name) => callbacks
    .filter(([kind, , module]) => kind === 'module' && module === 'DevSupport')
    .map(([, , , payload]) => JSON.parse(payload)).filter((message) => message.event === name).map((message) => message.payload);

  assert((await call('DevSupport', 'enable')).ok !== false, 'DevSupport.enable');
  assert((await call('DevSupport', 'reattach')).code === 'unknown_method', 'only the contract methods are callable');

  commit([['c', 90, 'View', {width: 120, height: 40, background_color: '#ff0000'}]]);
  const view = renderer.views.get(90);
  assert(view.el.dataset.pnTag === '90', 'views carry their tag for the inspector');
  screensEl.append(view.el);
  view.frame = {x: 10, y: 30, w: 120, h: 40}; view.manager.frame(view, 10, 30, 120, 40);

  await call('DevSupport', 'highlight', {tag: 90, label: 'App › Counter'});
  const outline = overlaysEl.querySelector('.pn-dev-highlight');
  assert(outline && outline.style.display !== 'none', 'highlight draws an outline');
  assert(Math.round(parseFloat(outline.style.left)) === 10 && Math.round(parseFloat(outline.style.top)) === 30 &&
    Math.round(parseFloat(outline.style.width)) === 120 && Math.round(parseFloat(outline.style.height)) === 40,
    `outline matches the view's frame: ${outline.style.cssText}`);
  assert(outline.textContent === 'App › Counter', 'the outline carries its label');
  assert(getComputedStyle(outline).pointerEvents === 'none', 'the outline never takes clicks');
  await call('DevSupport', 'highlight', {tag: null, label: ''});
  assert(!overlaysEl.querySelector('.pn-dev-highlight'), 'highlight(null) clears the outline');

  await call('DevSupport', 'set_inspecting', {enabled: true});
  const catcher = overlaysEl.querySelector('.pn-dev-inspect-catcher');
  const banner = overlaysEl.querySelector('.pn-dev-inspect-banner');
  assert(catcher && banner && banner.textContent.includes('Done'), 'inspecting shows the click catcher and banner');
  const box = view.el.getBoundingClientRect();
  const at = {bubbles: true, cancelable: true, clientX: box.left + 20, clientY: box.top + 10};
  catcher.dispatchEvent(new PointerEvent('pointermove', at));
  await frame();
  const hover = overlaysEl.querySelector('.pn-dev-hover');
  assert(hover && hover.style.display !== 'none' && hover.textContent === 'View', 'hovering outlines the view under the pointer');
  catcher.dispatchEvent(new MouseEvent('click', at));
  const inspected = moduleEvents('inspect');
  assert(inspected.length === 1 && inspected[0].tag === 90 && Math.round(inspected[0].x) === 30 && Math.round(inspected[0].y) === 40,
    `a click reports the view's tag and frame point: ${JSON.stringify(inspected)}`);
  // Clicks outside every view report nothing.
  catcher.dispatchEvent(new MouseEvent('click', {...at, clientX: box.left + 300, clientY: box.top + 400}));
  assert(moduleEvents('inspect').length === 1, 'clicks on empty space are ignored');
  // A remount empties the overlay layer; the inspector survives it.
  await host.clear();
  assert(overlaysEl.querySelector('.pn-dev-inspect-catcher'), 'the inspector survives a remount');
  banner.querySelector('button').click();
  assert(moduleEvents('inspect_done').length === 1, 'Done sends inspect_done');
  assert(!overlaysEl.querySelector('.pn-dev-inspect-catcher') && !overlaysEl.querySelector('.pn-dev-inspect-banner'), 'Done removes the inspector');

  await call('DevSupport', 'set_perf_monitor', {visible: true, lines: ['PY lag 1 ms', 'renders 2/s']});
  const monitor = overlaysEl.querySelector('.pn-dev-monitor');
  const lines = [...monitor.children].map((row) => row.textContent);
  assert(lines.length === 3 && /^UI .* fps$/.test(lines[0]) && lines[1] === 'PY lag 1 ms' && lines[2] === 'renders 2/s', `monitor lines: ${lines}`);
  await call('DevSupport', 'set_perf_monitor', {visible: true, lines: ['PY lag 3 ms']});
  assert(overlaysEl.querySelectorAll('.pn-dev-monitor').length === 1 && monitor.children[1].textContent === 'PY lag 3 ms', 'monitor updates in place');
  await call('DevSupport', 'set_perf_monitor', {visible: false, lines: []});
  assert(!overlaysEl.querySelector('.pn-dev-monitor'), 'monitor hides');

  const first = (await call('DevSupport', 'frame_stats')).value;
  await sleep(120);
  const second = (await call('DevSupport', 'frame_stats')).value;
  assert(typeof first.fps === 'number' && typeof second.fps === 'number' && typeof second.dropped === 'number', `frame_stats: ${JSON.stringify(second)}`);
  const meter = new FrameMeter();
  meter.reset(0); meter.frames = 1; meter.last = 0; meter.tick(50); cancelAnimationFrame(meter.handle);
  assert(meter.dropped === 2, `a 50 ms gap drops two frames at 60 Hz: ${meter.dropped}`);
  assert(meter.take(1000).fps === 2, 'fps counts frames over the window');

  commit([['d', 90]]); view.el.remove();
  screensEl.style.cssText = saved[0]; overlaysEl.style.cssText = saved[1]; overlaysEl.className = '';

  // ------------------------------------------------------------------
  // Host.show_error: the structured report.
  // ------------------------------------------------------------------
  callbacks.length = 0;
  await call('Host', 'show_error', {screen: 99, ...SAMPLE_REPORT});
  const overlay = document.getElementById('pn-error-overlay');
  assert(overlay && overlay.getAttribute('role') === 'alertdialog', 'host shows the error screen');
  assert(overlay.querySelector('.pn-error-title').textContent === 'ZeroDivisionError' && overlay.querySelector('.pn-error-message').textContent === 'division by zero', 'type and message');
  assert(overlay.querySelector('.pn-error-phase').textContent === 'Render error', 'phase label');
  const components = [...overlay.querySelectorAll('.pn-report-component')].map((li) => li.textContent);
  assert(components.length === 3 && components[0] === '<Counter>app/main.py:14' && components[1] === '<StackNavigator>', `component stack: ${components}`);
  const appFrames = overlay.querySelectorAll('.pn-report-frames > .pn-report-frame');
  assert(appFrames.length === 1 && appFrames[0].querySelector('.pn-report-frame-title').textContent === 'app/main.py:15 in Counter', 'the app frame stands alone, innermost first');
  const current = overlay.querySelector('.pn-report-line-current');
  assert(current && current.textContent.startsWith('> 15'), 'the failing line is marked');
  const framework = overlay.querySelector('.pn-report-framework');
  assert(framework && !framework.open && framework.querySelector('summary').textContent === '2 framework frames', 'framework frames collapse into one row');
  assert(overlay.textContent.includes('Dismiss') && overlay.textContent.includes('Copy') && overlay.textContent.includes('Reload'), 'actions');
  appFrames[0].querySelector('button.pn-report-frame-title').click();
  const opened = callbacks.find(([kind, screen, name]) => kind === 'host' && screen === 99 && name === 'open_in_editor');
  assert(opened && JSON.parse(opened[3]).file === 'app/main.py' && JSON.parse(opened[3]).line === 15, `frame titles open the editor: ${JSON.stringify(callbacks)}`);
  overlay.querySelector('.pn-report-component button').click();
  assert(callbacks.filter(([, , name]) => name === 'open_in_editor').length === 2, 'component locations open the editor');
  renderer.reset();
  assert(document.getElementById('pn-error-overlay'), 'renderer reset preserves host diagnostics');
  [...overlay.querySelectorAll('button')].find((b) => b.textContent === 'Reload').click();
  assert(callbacks.some(([kind, tag, name]) => kind === 'host' && tag === 99 && name === 'reload'), 'host reload bypasses renderer events');
  overlay.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  assert(!document.getElementById('pn-error-overlay'), 'Escape dismisses the error screen');
  await call('Host', 'show_error', {screen: 99, level: 'warning', phase: 'warning', type: 'warning', message: 'slow', title: 'Warning: slow', text: 'slow'});
  assert(document.getElementById('pn-error-overlay').classList.contains('pn-error-overlay-warning'), 'warnings get their own styling');
  await call('Host', 'show_error', {screen: 99, type: 'RuntimeError', message: 'boom', text: 'Traceback: sample'});
  assert(document.querySelectorAll('#pn-error-overlay').length === 1 && document.querySelector('.pn-error-text').textContent === 'Traceback: sample', 'a report without frames falls back to its text');
  await call('Host', 'dismiss_error');
  assert(!document.getElementById('pn-error-overlay'), 'host dismiss releases the overlay');

  // ------------------------------------------------------------------
  // DevTools page helpers.
  // ------------------------------------------------------------------
  assert(phaseLabel({level: 'warning'}) === 'Warning' && phaseLabel({phase: 'effect'}) === 'Effect error', 'phase labels');
  const groups = groupFrames(SAMPLE_REPORT.frames);
  assert(groups.length === 2 && !groups[0].framework && groups[1].framework && groups[1].frames.length === 2, 'frame grouping');
  const rendered = renderReport(SAMPLE_REPORT, {});
  assert(!rendered.querySelector('button') && rendered.querySelector('.pn-report-message').textContent === 'division by zero', 'reports render without editor links');

  const tree = [{screen: 'app.main', root: {id: 1, name: 'App', kind: 'component', source: {file: 'app/main.py', line: 3}, children: [
    {id: 2, name: 'StackNavigator', kind: 'component', framework: true, children: [
      {id: 3, name: 'Fragment', kind: 'fragment', children: [
        {id: 4, name: 'Counter', kind: 'component', key: "'a'", children: [{id: 5, name: 'Text', kind: 'native', tag: 7, text: 'Count 1', children: []}]},
        {id: 6, name: 'Button', kind: 'native', tag: 8, children: []},
      ]},
    ]},
  ]}}];
  const names = (rows) => rows.filter((r) => r.type === 'node').map((r) => `${r.depth}:${r.node.name}`).join(' ');
  assert(names(flattenTree(tree).rows) === '0:App 1:Counter 2:Text 1:Button', `framework nodes hoist their children: ${names(flattenTree(tree).rows)}`);
  assert(names(flattenTree(tree, {showFramework: true}).rows) === '0:App 1:StackNavigator 2:Fragment 3:Counter 4:Text 3:Button', 'framework nodes show on request');
  assert(flattenTree(tree).rows[0].type === 'screen' && flattenTree(tree).parents.get(4) === 1, 'screen rows and visible parents');
  assert(names(flattenTree(tree, {collapsed: new Set([4])}).rows) === '0:App 1:Counter 1:Button', 'collapsed nodes hide their children');
  const search = flattenTree(tree, {query: 'count', collapsed: new Set([1, 4])});
  assert(names(search.rows) === '0:App 1:Counter 2:Text' && search.matches === 2, `search keeps matches and ancestors: ${names(search.rows)}`);
  assert(visibleForest([tree[0].root], false)[0].children.length === 2, 'visible forest');
  const reveal = revealTarget(tree, 5);
  assert(reveal.id === 5 && reveal.ancestors.join() === '1,4', 'reveal expands visible ancestors');
  assert(revealTarget(tree, 2, {fallbackId: 6}).id === 6, 'a hidden node falls back to the tapped view');
  assert(revealTarget(tree, 2).id === 1, 'a hidden node without a fallback selects its visible ancestor');
  assert(revealTarget(tree, 99) === null, 'unmounted nodes are not found');

  const records = new Map();
  mergeRecord(records, 'preview', {id: 1, phase: 'start', method: 'GET', url: 'https://api.example.com/items?page=2', started: 10});
  const done = mergeRecord(records, 'preview', {id: 1, phase: 'end', status: 200, response_size: 2048, duration_ms: 12.5, response_body: '{"a":1}'});
  assert(records.size === 1 && done.state === 'done' && done.method === 'GET' && done.status === 200, 'start and end merge into one request');
  assert(mergeRecord(records, 'client-1', {id: 1, phase: 'error', error: 'boom'}).state === 'error' && records.size === 2, 'ids are per app');
  assert(splitUrl('https://api.example.com/items?page=2').name === 'items?page=2' && splitUrl('https://api.example.com/items').host === 'api.example.com', 'URL names');
  assert(prettyBody('{"a":1}') === '{\n  "a": 1\n}' && prettyBody('plain') === 'plain', 'JSON bodies pretty-print');

  const metrics = sampleMetrics({interval_s: 2, phases: {render: {count: 4}, commit: {count: 2, max_ms: 3.5}}, commits: [{ms: 1}, {ms: 2}], loop_lag_ms: 1.5, components_rendered: 10});
  assert(metrics.renders === 2 && metrics.commits === 1 && metrics.commitMax === 3.5 && metrics.commitLast === 2 && metrics.components === 5 && metrics.fps === null, `sample metrics: ${JSON.stringify(metrics)}`);
  const spark = sparkPath([0, 30, 60], 160, 32, 60);
  assert(spark.line.startsWith('M') && spark.line.split('L').length === 3 && spark.area.endsWith('Z'), 'sparkline paths');
  assert(sparkPath([null, null], 160, 32).line === '', 'empty sparkline');
  assert(problemKey('preview', SAMPLE_REPORT) === problemKey('preview', {...SAMPLE_REPORT}) && problemKey('a', SAMPLE_REPORT) !== problemKey('b', SAMPLE_REPORT), 'problem identity');
  assert(JSON.parse(launchConfig(5699)).connect.port === 5699 && JSON.parse(launchConfig()).connect.port === 5678, 'launch.json snippet');
}
