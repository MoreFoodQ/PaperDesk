// Build-time smoke test of a real packaged app. No live model calls by default.
// Set PAPERDESK_PLAYWRIGHT and PAPERDESK_PYTHON to your test runtimes.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const {_electron}=require(process.env.PAPERDESK_PLAYWRIGHT||'playwright');

(async()=>{
 const root=path.resolve(__dirname,'..');
 const flag=process.argv.indexOf('--app');
 const executable=flag>=0?path.resolve(process.argv[flag+1]):path.join(root,'dist/electron/win-unpacked/PaperDesk.exe');
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'paperdesk-packaged-test-'));
 const python=process.env.PAPERDESK_PYTHON||path.join(root,'.venv/Scripts/python.exe');
 const env={...process.env,EASYREAD_HOME:path.join(home,'data'),PAPERDESK_DESKTOP_PROFILE:path.join(home,'profile'),
   PAPERDESK_BACKGROUND:'1',USERPROFILE:home,HOME:home,CODEX_HOME:path.join(home,'codex-home'),
   PATH:path.join(process.env.SYSTEMROOT||'C:/Windows','System32'),PYTHONUTF8:'1'};
 for(const key of ['EASYREAD_LIBRARY','COREAD_LIBRARY','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','OPENAI_API_KEY','CODEX_API_KEY','NODE_PATH','ELECTRON_RUN_AS_NODE'])delete env[key];
 for(const dir of [env.EASYREAD_HOME,env.PAPERDESK_DESKTOP_PROFILE,env.CODEX_HOME])fs.mkdirSync(dir,{recursive:true});
 fs.writeFileSync(path.join(env.EASYREAD_HOME,'config.json'),JSON.stringify({engine:'none',auto_translate:false,metadata_lookup:false}));
 fs.writeFileSync(path.join(env.EASYREAD_HOME,'prefs.json'),JSON.stringify({ui:{lang:'zh-TW'},reader:{theme:'dark',darkPalette:'graphite'}}));
 fs.writeFileSync(path.join(env.PAPERDESK_DESKTOP_PROFILE,'window-state.json'),JSON.stringify({bounds:{x:0,y:0,width:1600,height:1000},maximized:false}));
 const seed=spawnSync(python,['-c','from pathlib import Path; from tests.test_epub import epub_bytes; from scripts.smoke_backend import probe_pdf; import os; p=Path(os.environ["EASYREAD_HOME"]); (p/"fixture.epub").write_bytes(epub_bytes()); (p/"fixture.pdf").write_bytes(probe_pdf())'],{cwd:root,env,windowsHide:true,encoding:'utf8'});
 if(seed.status!==0)throw Error(seed.stderr);
 let app,base;const errors=[],external=[];
 try{
  app=await _electron.launch({executablePath:executable,env,cwd:home,timeout:60000});
  const page=await app.firstWindow();page.on('pageerror',e=>errors.push(e.message));
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:\d+\/$/,{timeout:60000});
  await page.waitForFunction(()=>window.PR?.lib&&window.PR.token);
  base=new URL(page.url()).origin;
  const token=await page.evaluate(()=>window.PR.token);
  const headers={'X-Token':token};
  const api=async(p,opts={})=>{const r=await fetch(base+p,{...opts,headers:{...headers,...opts.headers}});assert.ok(r.ok,'HTTP '+r.status+' '+p);return r.json()};
  const state=await app.evaluate(({app})=>({packaged:app.isPackaged,profile:app.getPath('userData'),version:app.getVersion(),electron:process.versions.electron}));
  assert.equal(state.packaged,true);assert.equal(path.resolve(state.profile),path.resolve(env.PAPERDESK_DESKTOP_PROFILE));
  const expected=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
  assert.equal(state.version,expected.version);assert.equal(state.electron,expected.devDependencies.electron);
  assert.equal(await page.evaluate(()=>window.PR.t('分类名，回车')), '輸入分類名稱，按 Enter');
  assert.equal(await page.evaluate(()=>window.PR.t('回收站')), '回收區');
  assert.equal(await page.evaluate(()=>window.PR.t('快捷键')), '快捷鍵');
  assert.equal(await page.evaluate(()=>typeof window.easyreadDesktop.loginCodex),'function');
  await page.evaluate(()=>window.PR.openSettings());
  await page.locator('[data-codex-login]').waitFor();assert.ok((await page.locator('[data-codex-login]').textContent()).includes('登入'));
  await page.evaluate(()=>document.querySelector('#settingsDlg').classList.remove('open'));
  const engines=await api('/api/engines');assert.equal(engines.found.codex.found,true);assert.ok(engines.found.codex.version.includes('0.162.1'));
  assert.equal((await fetch(base+'/api/library')).status,401);
  const context=page.context();await context.route('**/*',r=>{const u=r.request().url();if(u.startsWith(base)||u.startsWith('data:')||u.startsWith('chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/'))return r.continue();external.push(u);return r.abort()});
  await page.locator('#importBtn').click();
  await page.locator('#fileInput').setInputFiles([path.join(env.EASYREAD_HOME,'fixture.pdf'),path.join(env.EASYREAD_HOME,'fixture.epub')]);
  let items=[];
  for(let i=0;i<150;i++){items=(await api('/api/library')).items;if(items.length===2&&items.every(x=>x.pages>0&&x.job?.state==='done'))break;await new Promise(r=>setTimeout(r,200))}
  assert.equal(items.length,2);assert.ok(items.every(x=>x.pages>0&&x.job.state==='done'));
  const book=items.find(x=>x.format==='epub');assert.ok(book);
  const pdf=items.find(x=>x.format==='pdf');assert.ok(pdf);
  for(const item of [pdf,book]){
   await page.goto(base+'/read/'+item.id);await page.locator('#paper .orig-page').first().waitFor();
   await page.evaluate(()=>{window.PR.toggleDrawer(false);window.PR.togglePages(true)});
   await page.waitForFunction(()=>document.querySelector('.pv-page img')?.naturalWidth>0);
   assert.equal(await page.locator('[data-pv="pdf"]').textContent(),item.format==='epub'?'閱讀版 PDF':'PDF');
   await page.evaluate(()=>window.PR.commit({op:'paper_note',body:'Packaged persistence note'}));
   let saved;
   for(let i=0;i<60;i++){saved=await api('/api/p/'+item.id+'/state');if(saved.reader.paper_note.body==='Packaged persistence note')break;await new Promise(r=>setTimeout(r,100))}
   assert.equal(saved.reader.paper_note.body,'Packaged persistence note');
   await page.reload();await page.locator('#paper .orig-page').first().waitFor();
   assert.equal(await page.evaluate(()=>window.PR.state.reader.paper_note.body),'Packaged persistence note');
   const button=page.locator('#bar [data-act="drawer"]');
   await button.click();await page.waitForTimeout(300);await button.click();await page.waitForTimeout(300);
   assert.ok(await page.evaluate(()=>document.querySelector('#drawer').getBoundingClientRect().right<=1));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
   await page.evaluate(()=>window.PR.togglePages(true));
   const popupPromise=app.waitForEvent('window');
   await page.locator('[data-pv="pdf"]').click();
   const popup=await popupPromise;
   await popup.waitForURL(u=>u.origin===base&&u.pathname.endsWith('/source.pdf'));
   await popup.close();
   const output=await fetch(base+'/api/p/'+item.id+'/export',{headers});assert.ok(output.ok);const html=await output.text();assert.ok(html.includes('Packaged persistence note'));assert.ok(html.includes('data:image/webp;base64,'));
   fs.writeFileSync(path.join(home,item.format+'-offline.html'),html);
  }
  // 以合成資料驗證實際安裝包的略過／已翻譯呈現，不呼叫模型。
  for (const item of [pdf,book]) {
    const paperPath=path.join(env.EASYREAD_HOME,'library',item.id,'paper.json');
    const paper=JSON.parse(fs.readFileSync(paperPath,'utf8'));
    paper.blocks=[{id:'qa-body',type:'para',page:1,en:'Synthetic body',zh:'合成正文'},
      {id:'qa-figure',type:'figure',page:1,src:paper.meta.pages[0].img,image_en:'Score',caption_en:'Synthetic caption',caption_zh:'合成圖說',image_translation_skipped:true}];
    paper.translation={...(paper.translation||{}),done_pages:[1],en_pages:[]};
    fs.writeFileSync(paperPath,JSON.stringify(paper));
    await page.goto(base+'/read/'+item.id);await page.locator('#b-qa-figure').waitFor();
    assert.equal(await page.locator('.figure-translation').count(),0);
    assert.equal(await page.locator('[data-t="translate-images"]').count(),0); // No model is configured in this isolated package test.
    assert.equal(await page.evaluate(()=>window.PR.state.reader.paper_note.body),'Packaged persistence note');
    paper.blocks[1].image_zh='分數';delete paper.blocks[1].image_translation_skipped;
    fs.writeFileSync(paperPath,JSON.stringify(paper));
    await page.reload();await page.locator('.figure-translation').waitFor();
    assert.ok((await page.locator('.figure-translation').textContent()).includes('分數'));
    assert.equal(await page.locator('[data-t="translate-images"]').count(),0);
    assert.equal(await page.evaluate(()=>window.PR.state.reader.paper_note.body),'Packaged persistence note');
  }
  const original=await fetch(base+'/p/'+book.id+'/source.epub',{headers});assert.deepEqual(Buffer.from(await original.arrayBuffer()),fs.readFileSync(path.join(env.EASYREAD_HOME,'fixture.epub')));
  assert.equal((await fetch(base+'/p/'+book.id+'/source.epub')).status,401);
  const captured=await app.evaluate(async({BrowserWindow})=>(await BrowserWindow.getAllWindows()[0].webContents.capturePage(undefined,{stayHidden:true,stayAwake:true})).toPNG().toString('base64'));
  fs.writeFileSync(path.join(home,'packaged-reader.png'),Buffer.from(captured,'base64'));
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  assert.ok(!fs.existsSync(path.join(env.CODEX_HOME,'auth.json')));
  fs.writeFileSync(path.join(home,'RESULT.json'),JSON.stringify({packaged:true,version:state.version,electron:state.electron,figure_visibility:true,external_python_node_path:false,pdf_epub:true,notes_reload:true,offline_exports:true,auth:true,bundled_codex:true,live_model_calls:0},null,2));
  console.log('PASS: actual packaged app without Python/Node on PATH; bundled CLI, login UI, PDF/EPUB, notes, offline exports and authentication. No live model calls.');
  console.log('Synthetic evidence: '+home);
 }finally{
  if(app)await app.close();
  if(base){let closed=false;for(let i=0;i<30;i++){try{await fetch(base+'/api/library')}catch{closed=true;break}await new Promise(r=>setTimeout(r,100))}assert.ok(closed,'Backend remained after desktop quit')}
 }
})().catch(e=>{console.error(e);process.exit(1)});
