const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture() {
  let now = 0, sequence = 0;
  const timers = new Map(), events = new Map();
  const media = { matches: false, addEventListener(_name, fn) { this.change = fn; }, removeEventListener() {} };
  const document = { visibilityState: 'visible', addEventListener(name, fn) { events.set(name, fn); }, removeEventListener() {} };
  const element = (id, x, y, width, height) => ({
    id, style: { visibility: 'visible', opacity: '1' }, shown: true,
    getClientRects() { return this.shown ? [this.getBoundingClientRect()] : []; },
    getBoundingClientRect() { return { x, y, width, height, right: x + width, bottom: y + height }; },
  });
  const orb = element('orb', 300, 50, 280, 280);
  const root = { dataset: { coreState: 'READY' }, classList: { add() {}, remove() {} }, querySelector() { return orb; } };
  const context = vm.createContext({
    document, performance: { now: () => now }, module: { exports: {} },
    window: {
      innerWidth: 1440, innerHeight: 900, matchMedia: () => media,
      getComputedStyle: el => el.style,
      setTimeout(fn, ms) { const id = ++sequence; timers.set(id, { at: now + ms, fn }); return id; },
      clearTimeout(id) { timers.delete(id); },
    },
  });
  const source = fs.readFileSync(path.join(__dirname, '../static/core-state.js'), 'utf8').replaceAll('export function ', 'function ');
  vm.runInContext(source + '\nmodule.exports = { installCorePresence, attentionDirection };', context);
  const core = context.module.exports.installCorePresence(root, null);
  return { core, root, media, document, events, element, orb,
    reply: element('transcript', 300, 430, 600, 330),
    approval: element('approvalPanel', 1100, 120, 320, 700),
    advance(ms) {
      const end = now + ms;
      while (true) {
        const due = [...timers].filter(([, value]) => value.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) break;
        timers.delete(due[0]); now = due[1].at; due[1].fn();
      }
      now = end;
    },
  };
}

test('attention follows visible geometry and returns to neutral', () => {
  const f = fixture();
  assert.equal(f.core.lookAt(f.reply), true);
  assert.equal(f.root.dataset.gaze, 'down');
  assert.equal(f.root.dataset.attentionTarget, 'transcript');
  f.advance(1200);
  assert.equal(f.root.dataset.gaze, 'forward');
  assert.equal(f.root.dataset.attentionTarget, undefined);
});

test('urgent approval supersedes reply; repeated events cannot prolong gaze', () => {
  const f = fixture();
  f.core.lookAt(f.reply);
  f.advance(200);
  assert.equal(f.core.lookAt(f.approval, 2), true);
  assert.equal(f.root.dataset.gaze, 'right');
  assert.equal(f.core.lookAt(f.reply), false);
  f.advance(1000);
  assert.equal(f.core.lookAt(f.approval, 2), false);
  f.advance(800);
  assert.equal(f.root.dataset.gaze, 'forward');
});

test('hidden and offscreen targets never draw attention', () => {
  const f = fixture();
  f.reply.shown = false;
  assert.equal(f.core.lookAt(f.reply), false);
  assert.equal(f.core.lookAt(f.element('below', 300, 1000, 400, 200)), false);
  assert.equal(f.root.dataset.gaze, 'forward');
  f.orb.shown = false;
  assert.equal(f.core.lookAt(f.approval, 2), false);
});

test('mobile position changes attention direction instead of hardcoding right', () => {
  const f = fixture();
  assert.equal(f.core.lookAt(f.element('mobileDecision', 300, 430, 280, 300), 2), true);
  assert.equal(f.root.dataset.gaze, 'down');
});

test('offline, reduced motion, hidden page and destruction cancel attention', () => {
  for (const mode of ['offline', 'reduced', 'hidden', 'destroyed']) {
    const f = fixture();
    f.core.lookAt(f.approval, 2);
    if (mode === 'offline') f.core.update('OFFLINE');
    if (mode === 'reduced') { f.media.matches = true; f.media.change(); }
    if (mode === 'hidden') { f.document.visibilityState = 'hidden'; f.events.get('visibilitychange')(); }
    if (mode === 'destroyed') f.core.destroy();
    assert.equal(f.root.dataset.gaze, 'forward', mode);
    assert.equal(f.root.dataset.attentionTarget, undefined, mode);
    assert.equal(f.core.lookAt(f.reply), false, mode);
    f.advance(5000);
    assert.equal(f.root.dataset.gaze, 'forward', mode);
  }
});
