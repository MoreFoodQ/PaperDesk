const assert=require('node:assert/strict');
const {test}=require('node:test');
const fs=require('node:fs');
const vm=require('node:vm');
const PR={t:s=>s,settingsState:{},$$:()=>[], $:()=>null};
vm.runInNewContext(fs.readFileSync('easyread/web/js/common/settings-api.js','utf8'),{window:{PR}});
test('manual model blur keeps the pending Add click target in the DOM',()=>{
  const state={presets:[]},form={model:'research-model',preset:''};
  assert.equal(PR.apiForm.change({target:{dataset:{af:'model'},tagName:'INPUT',value:'research-model'}},state,form,'key',{}),false);
});
test('model select still redraws dependent fields',()=>{
  const state={presets:[]},form={model:'research-model',preset:''};
  assert.equal(PR.apiForm.change({target:{dataset:{af:'model'},tagName:'SELECT',value:'research-model'}},state,form,'key',{}),true);
});
