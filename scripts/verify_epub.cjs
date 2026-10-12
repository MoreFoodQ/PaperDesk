// Optional browser integration using synthetic documents and no AI calls.
// Runtime overrides match scripts/verify_reader_drawer.cjs.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn,spawnSync}=require('node:child_process');
const {chromium}=require(process.env.PAPERDESK_PLAYWRIGHT||'playwright');
(async()=>{
 const root=path.resolve(__dirname,'..');
 const python=process.env.PAPERDESK_PYTHON||path.join(root,'.venv','Scripts','python.exe');
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'paperdesk-epub-browser-'));
 const env={...process.env,EASYREAD_HOME:home,PYTHONUTF8:'1',PAPERDESK_SESSION:'SYNTHETIC-EPUB-TEST'};delete env.EASYREAD_LIBRARY;
 fs.writeFileSync(path.join(home,'config.json'),JSON.stringify({engine:'none',auto_translate:false,metadata_lookup:false}));
 fs.writeFileSync(path.join(home,'prefs.json'),JSON.stringify({ui:{lang:'zh-TW'},reader:{theme:'dark',darkPalette:'graphite'}}));
 const seed=spawnSync(python,['-c','from pathlib import Path; from tests.test_epub import epub_bytes; from scripts.smoke_backend import probe_pdf; import os; p=Path(os.environ["EASYREAD_HOME"]); (p/"fixture.epub").write_bytes(epub_bytes()); (p/"fixture.pdf").write_bytes(probe_pdf())'],{cwd:root,env,windowsHide:true,encoding:'utf8'});
 if(seed.status!==0)throw Error(seed.stderr);
 const proc=spawn(python,['-m','easyread','serve','--port','0'],{cwd:root,env,windowsHide:true,stdio:'ignore'});
 let browser,base;const errors=[],external=[];
 try{
  for(let i=0;i<100&&!fs.existsSync(path.join(home,'.server.json'));i++)await new Promise(r=>setTimeout(r,100));
  base=JSON.parse(fs.readFileSync(path.join(home,'.server.json'),'utf8')).url;
  const headers={'X-Token':env.PAPERDESK_SESSION};
  const api=async(p,opts={})=>{const r=await fetch(base+p,{...opts,headers:{...headers,...opts.headers}});assert.ok(r.ok,'HTTP '+r.status+' '+p);return r.json()};
  browser=await chromium.launch({headless:true,...(process.env.PAPERDESK_CHROME?{executablePath:process.env.PAPERDESK_CHROME}:{})});
  const context=await browser.newContext({viewport:{width:1600,height:1000},acceptDownloads:true});
  await context.route('**/*',r=>{const u=r.request().url();if(u.startsWith(base)||u.startsWith('data:'))return r.continue();external.push(u);return r.abort()});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/auth?session='+env.PAPERDESK_SESSION);
  await page.locator('#importBtn').click();
  assert.ok((await page.locator('#fileInput').getAttribute('accept')).includes('.epub'));
  assert.ok((await page.locator('#pick').textContent()).includes('EPUB'));
  await page.locator('#fileInput').setInputFiles([path.join(home,'fixture.epub'),path.join(home,'fixture.pdf')]);
  let items=[];
  for(let i=0;i<100;i++){items=(await api('/api/library')).items;if(items.length===2&&items.every(x=>x.pages>0&&x.job?.state==='done'))break;await new Promise(r=>setTimeout(r,200))}
  assert.equal(items.length,2);assert.ok(items.every(x=>x.pages>0&&x.job.state==='done'));
  const book=items.find(x=>x.format==='epub'),pdf=items.find(x=>x.format==='pdf');assert.ok(book&&pdf);
  for(const item of [book,pdf]){
   await page.goto(base+'/read/'+item.id);await page.locator('#paper .blk, #paper .orig-page').first().waitFor();
   await page.evaluate(()=>window.PR.togglePages(true));await page.locator('.pv-page img').first().waitFor();
   await page.waitForFunction(()=>document.querySelector('.pv-page img')?.naturalWidth>0);
   assert.equal(await page.locator('[data-pv="pdf"]').textContent(),item.format==='epub'?'閱讀版 PDF':'PDF');
   await page.evaluate(()=>window.PR.commit({op:'paper_note',body:'Synthetic EPUB/PDF persistence note'}));
   let state;
   for(let i=0;i<60;i++){state=await api('/api/p/'+item.id+'/state');if(state.reader.paper_note.body==='Synthetic EPUB/PDF persistence note')break;await new Promise(r=>setTimeout(r,100))}
   assert.equal(state.reader.paper_note.body,'Synthetic EPUB/PDF persistence note');
   await page.reload();await page.locator('#paper .blk, #paper .orig-page').first().waitFor();
   assert.equal(await page.evaluate(()=>window.PR.state.reader.paper_note.body),'Synthetic EPUB/PDF persistence note');
   const exported=await fetch(base+'/api/p/'+item.id+'/export',{headers});assert.ok(exported.ok);const html=await exported.text();assert.ok(html.includes('Synthetic EPUB/PDF persistence note'));assert.ok(html.includes('data:image/webp;base64,'));
   const offline=await context.newPage();offline.on('pageerror',e=>errors.push(e.message));await offline.setContent(html);await offline.locator('#paper .blk, #paper .orig-page').first().waitFor();assert.equal(await offline.evaluate(()=>window.PR.store.mode),'static');if(item.format==='epub')assert.equal(await offline.locator('[data-act="pages"] span').textContent(),'原文頁面');await offline.close();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  }
  const original=await fetch(base+'/p/'+book.id+'/source.epub',{headers});assert.equal(original.headers.get('content-type'),'application/epub+zip');assert.ok(original.headers.get('content-disposition').includes('attachment'));assert.deepEqual(Buffer.from(await original.arrayBuffer()),fs.readFileSync(path.join(home,'fixture.epub')));
  assert.equal((await fetch(base+'/p/'+book.id+'/source.epub')).status,401);
  await page.goto(base+'/read/'+book.id);await page.locator('#paper .blk, #paper .orig-page').first().waitFor();await page.evaluate(()=>window.PR.togglePages(true));
  await page.waitForTimeout(350);await page.waitForFunction(()=>document.querySelector('.pv-page img')?.naturalWidth>0);
  await page.screenshot({path:path.join(home,'epub-reader.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log('PASS: mixed PDF/EPUB browser import, source pages, original download/auth, note save/reload, offline exports, no external requests or model calls.');
  console.log('Synthetic screenshot: '+path.join(home,'epub-reader.png'));
 }finally{
  if(browser)await browser.close();if(base)try{await fetch(base+'/api/shutdown',{method:'POST',headers:{'X-Token':env.PAPERDESK_SESSION},body:'{}'});}catch{}
  await new Promise(r=>{if(proc.exitCode!==null)return r();proc.once('exit',r);setTimeout(r,5000).unref()});if(proc.exitCode===null)proc.kill();
 }
})().catch(e=>{console.error(e);process.exit(1)});
