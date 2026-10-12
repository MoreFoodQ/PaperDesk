const {test}=require('node:test');
const assert=require('node:assert/strict');
const {classify,policy}=require('../electron/open-target.cjs');
const base='http://127.0.0.1:12345';
test('local PDF opens in a sandboxed session-sharing window without external auth transfer',()=>{
 const seen=[];const result=policy(base+'/p/abcdef/source.pdf#page=2',base,{},url=>seen.push(url));
 assert.equal(result.action,'allow');assert.equal(result.overrideBrowserWindowOptions.webPreferences.sandbox,true);assert.equal(result.overrideBrowserWindowOptions.webPreferences.nodeIntegration,false);assert.equal(result.overrideBrowserWindowOptions.webPreferences.preload,'');assert.deepEqual(seen,[]);
});
test('original EPUB downloads with the desktop web contents session',()=>{
 const downloads=[],external=[];const url=base+'/p/abcdef/source.epub';
 assert.equal(policy(url,base,{downloadURL:u=>downloads.push(u)},u=>external.push(u)).action,'deny');assert.deepEqual(downloads,[url]);assert.deepEqual(external,[]);
});
test('external links cannot receive session headers or become local app windows',()=>{
 const external=[];assert.equal(policy('https://example.org/paper',base,{},u=>external.push(u)).action,'deny');assert.deepEqual(external,['https://example.org/paper']);assert.equal(classify('http://127.0.0.1:54321/',base),'external');
});
test('file, script and credential-bearing popup URLs are rejected',()=>{
 for(const url of ['file:///C:/private','javascript:alert(1)','data:text/html,x','https://user:password@example.org','invalid'])assert.equal(classify(url,base),'deny');
});
