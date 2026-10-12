const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

const PR = {settingsTabs: {}, t: (s,v) => v ? s.replace(/\{(\w+)\}/g,(_,k)=>v[k]) : s,
  esc: s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;')};
vm.runInNewContext(fs.readFileSync('easyread/web/js/common/settings-tabs.js','utf8'),{window:{PR},Number,Date});
test('unavailable quota is never zero remaining',()=> {
  const html=PR.accountUsageHtml({status:'unavailable'});
  assert.match(html,/不代表剩餘為零/);
  assert.doesNotMatch(html,/剩餘 0%/);
});
test('official bucket name is escaped and remaining is shown',()=> {
  const html=PR.accountUsageHtml({status:'available',at:Date.now()/1000,buckets:[{name:'<img onerror="evil">',windows:[{remaining_percent:85,window_minutes:300,resets_at:Date.now()/1000+1000}]}]});
  assert.match(html,/剩餘 85%/);
  assert.match(html,/5 小時視窗/);
  assert.doesNotMatch(html,/<img/);
});
test('budget values survive quota refresh', async()=> {
  const s={tab:'usage',cfg:{budget:{daily_calls:0,daily_tokens:0}}};
  PR.$=()=>({querySelectorAll:()=>[{dataset:{budget:'daily_calls'},value:'3'}]});
  PR.settingsRender=()=>{};PR.api=async()=>({status:'unavailable'});
  await PR.settingsTabs.usage.click({target:{closest:()=>true}},s);
  assert.equal(s.cfg.budget.daily_calls,3);
  assert.equal(s.accountPending,false);
});
test('null remaining is not shown as zero, weekly window is readable',()=> {
  const html=PR.accountUsageHtml({status:'available',at:Date.now()/1000,buckets:[{name:'codex',windows:[{remaining_percent:null,window_minutes:10080}]}]});
  assert.doesNotMatch(html,/剩餘 0%/);
  assert.match(html,/7 天視窗/);
});
