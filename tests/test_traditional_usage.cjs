const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const dictionary = JSON.parse(fs.readFileSync('easyread/web/i18n/zh-TW.json','utf8'));
const PR = {lang:'zh-TW', t:(key, vars)=> (dictionary[key]||key).replace(/\{(\w+)\}/g,(m,k)=>vars && k in vars ? vars[k] : m)};
vm.runInNewContext(fs.readFileSync('easyread/web/js/common/usage.js','utf8'),{window:{PR},Number,Date});
test('large token counts use Traditional Chinese',()=>{
  assert.equal(PR.fmtTokens(123000),'12.3 萬');
  const html=PR.usageBars({five_hour:{used:.2,resets_at:Date.now()/1000+3*86400}});
  assert.match(html,/週[日一二三四五六]/);
  assert.doesNotMatch(html,/万|周/);
});
