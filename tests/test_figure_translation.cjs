const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

function settings(translateImages) {
  const controls = [];
  const PR = {settingsTabs: {}, esc: String, icon: () => '',
    $: () => ({addEventListener() {}}), $$: () => controls,
    t: key => key, opt: () => '', saveModelSettings() {this.saves = (this.saves || 0) + 1;}};
  const context = {window: {PR, addEventListener() {}}, document: {addEventListener() {}}};
  for (const file of ['settings.js', 'settings-chat.js']) {
    vm.runInNewContext(fs.readFileSync('easyread/web/js/common/' + file, 'utf8'), context);
  }
  PR.saveModelSettings = function () {this.saves = (this.saves || 0) + 1;};
  const state = {pinned: true, transChecked: true,
    cfg: {engine: 'codex', codex: {}, claude: {}, openai: {}, translate_images: translateImages}, chat: {models: []}};
  return {PR, state, controls};
}

test('figure translation checkbox defaults on and describes scope accessibly', () => {
  for (const value of [undefined, true, false]) {
    const {PR, state} = settings(value);
    const html = PR.settingsTabs.chat.render(state);
    const input = html.match(/<input[^>]+data-k="translate_images"[^>]*>/)[0];
    assert.equal(/ checked/.test(input), value !== false);
    assert.match(input, /aria-describedby="translateImagesHint"/);
    assert.match(html, /id="translateImagesHint"/);
    assert.match(html, /正文、表格與圖說仍會翻譯/);
  }
});

test('figure setting survives form collection and saves as boolean', () => {
  const {PR, state, controls} = settings(true);
  controls.push({dataset: {k: 'translate_images'}, type: 'checkbox', checked: false});
  PR.settingsTabs.chat.change({target: controls[0]}, state);
  assert.equal(PR.saves, 1);
  assert.equal(PR.settingsTabs.engine.collect(state).translate_images, false);
  controls[0].checked = true;
  PR.settingsTabs.chat.change({target: controls[0]}, state);
  assert.equal(PR.settingsTabs.engine.collect(state).translate_images, true);
});
