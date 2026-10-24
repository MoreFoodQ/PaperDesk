const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');

function setup(cached = {}, systemDark = true) {
  const source = fs.readFileSync('easyread/web/js/common/util.js', 'utf8');
  const start = source.indexOf('  PR.DARK_PALETTES');
  const end = source.indexOf('  const subs = {};', start);
  assert.ok(start >= 0 && end > start, 'Theme source boundaries must exist');
  const theme = source.slice(start, end);
  const dataset = {}, PR = {t: s => s, ls: {get: () => cached}};
  vm.runInNewContext(theme, {PR, document: {documentElement: {dataset}}, matchMedia: () => ({matches: systemDark})});
  return {PR, dataset};
}

test('missing or invalid palette safely uses graphite without changing appearance mode', () => {
  const {PR, dataset} = setup();
  PR.applyTheme('dark');
  assert.deepEqual(dataset, {theme: 'dark', palette: 'graphite'});
  PR.applyTheme('light', 'unknown');
  assert.deepEqual(dataset, {theme: 'light', palette: 'graphite'});
});

test('preview is explicit and theme toggles preserve the saved palette', () => {
  const {PR, dataset} = setup({darkPalette: 'mocha'});
  PR.applyTheme('dark', 'nord');
  assert.equal(dataset.palette, 'nord');
  PR.applyTheme('light');
  assert.equal(dataset.palette, 'mocha');
  assert.equal(dataset.theme, 'light');
  PR.applyTheme('auto');
  assert.equal(dataset.theme, 'dark');
  assert.equal(dataset.palette, 'mocha');
});

test('all dark palettes keep body, supporting text and primary button contrast above 4.5', () => {
  const css = fs.readFileSync('easyread/web/css/workspace.css', 'utf8');
  const lum = hex => hex.slice(1).match(/../g).map(x => parseInt(x,16)/255)
    .map(x => x <= .04045 ? x/12.92 : ((x+.055)/1.055)**2.4)
    .reduce((a,x,i) => a+x*[.2126,.7152,.0722][i],0);
  const contrast = (a,b) => (Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
  const blocks = [...css.matchAll(/:root\[data-theme="dark"\](?:\[data-palette="\w+"\])? \{([^}]+)\}/g)];
  assert.equal(blocks.length, 5);
  for (const [,block] of blocks) {
    const values = Object.fromEntries([...block.matchAll(/--([\w-]+): (#[\da-f]{6})/g)].map(m => [m[1],m[2]]));
    for (const [text,bg] of [['ink','bg'],['ink','surface'],['ink-2','surface'],['ink-3','surface-2'],['bg','accent']]) {
      assert.ok(contrast(values[text],values[bg]) >= 4.5, `${text}/${bg}: ${block}`);
    }
  }
});
