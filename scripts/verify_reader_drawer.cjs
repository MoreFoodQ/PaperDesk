// Optional browser regression: set PAPERDESK_PLAYWRIGHT, PAPERDESK_CHROME,
// and PAPERDESK_PYTHON when using runtimes outside the project environment.
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn,spawnSync}=require('node:child_process');
const {chromium}=require(process.env.PAPERDESK_PLAYWRIGHT||'playwright');

(async()=>{
 const root=path.resolve(__dirname,'..');
 const python=process.env.PAPERDESK_PYTHON||path.join(root,'.venv','Scripts','python.exe');
 const home=fs.mkdtempSync(path.join(os.tmpdir(),'paperdesk-drawer-test-'));
 const env={...process.env,EASYREAD_HOME:home,PYTHONUTF8:'1',PAPERDESK_SESSION:'SYNTHETIC-DRAWER-TEST'};delete env.EASYREAD_LIBRARY;
 fs.writeFileSync(path.join(home,'config.json'),JSON.stringify({engine:'none',auto_translate:false,metadata_lookup:false}));
 fs.writeFileSync(path.join(home,'prefs.json'),JSON.stringify({ui:{lang:'zh-TW'},reader:{theme:'dark',darkPalette:'graphite'}}));
 const seed='from scripts.smoke_backend import probe_pdf; from easyread import config; from easyread.library import Library; from easyread.store import write_json_atomic; ws,_=Library(config.library_dir()).create_from_pdf(probe_pdf(),"drawer-test.pdf"); p=ws.load("paper"); p["blocks"]=[{"id":"heading","type":"heading","zh":"測試目錄","en":"Test outline","level":1},{"id":"text","type":"para","zh":"合成段落，用於驗證抽屜收合。","en":"Synthetic text for drawer regression."}]; write_json_atomic(ws.paper_path,p); print(ws.id)';
 const fixture=spawnSync(python,['-c',seed],{cwd:root,env,windowsHide:true,encoding:'utf8'});
 if(fixture.status!==0)throw Error(fixture.stderr);
 const id=fixture.stdout.trim();
 const proc=spawn(python,['-m','easyread','serve','--port','0'],{cwd:root,env,windowsHide:true,stdio:'ignore'});
 let browser,base;const errors=[];
 try{
  for(let i=0;i<100&&!fs.existsSync(path.join(home,'.server.json'));i++)await new Promise(r=>setTimeout(r,100));
  base=JSON.parse(fs.readFileSync(path.join(home,'.server.json'),'utf8')).url;
  browser=await chromium.launch({headless:true,...(process.env.PAPERDESK_CHROME?{executablePath:process.env.PAPERDESK_CHROME}:{})});
  const page=await browser.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/auth?session='+env.PAPERDESK_SESSION);
  async function closed(){await page.waitForTimeout(260);const s=await page.evaluate(()=>{const d=document.querySelector('#drawer');return{right:d.getBoundingClientRect().right,visibility:getComputedStyle(d).visibility,pointer:getComputedStyle(d).pointerEvents,inert:d.inert,hidden:d.getAttribute('aria-hidden')}});assert.ok(s.right<=1,JSON.stringify(s));assert.equal(s.visibility,'hidden');assert.equal(s.pointer,'none');assert.equal(s.inert,true);assert.equal(s.hidden,'true');}
  async function opened(){await page.waitForTimeout(260);const s=await page.evaluate(()=>{const d=document.querySelector('#drawer'),r=d.getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,inert:d.inert,expanded:document.querySelector('#bar [data-act="drawer"]').getAttribute('aria-expanded')}});assert.ok(s.left>=0&&s.right<=page.viewportSize().width+1,JSON.stringify(s));assert.ok(s.top>=60);assert.equal(s.inert,false);assert.equal(s.expanded,'true');}
  for(const width of [1600,1360,1359,1180,980,900,899,600,390]){
   await page.setViewportSize({width,height:900});await page.goto(base+'/read/'+id);await page.locator('#paper .blk').first().waitFor();
   await page.evaluate(()=>{window.PR.openSide(null);window.PR.toggleDrawer(false)});await closed();
   const top=page.locator('#bar [data-act="drawer"]');
   for(let i=0;i<2;i++){await top.click();await opened();await top.click();await closed();}
   if(width>=900){const dock=page.locator('#workspaceDock [data-pd-act="drawer"]');await dock.click();await opened();await dock.click();await closed();}
   if(width<1360){await top.click();await opened();await page.mouse.click(width-12,450);await closed();}
   await page.evaluate(()=>document.activeElement.blur());await page.keyboard.press('t');await opened();await page.keyboard.press('t');await closed();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'overflow at '+width);
   console.log('PASS: drawer fully closes and reopens at '+width+'px');
  }
  assert.deepEqual(errors,[]);
 }finally{
  if(browser)await browser.close();if(base)try{await fetch(base+'/api/shutdown',{method:'POST',headers:{'X-Token':env.PAPERDESK_SESSION},body:'{}'});}catch{}
  await new Promise(r=>{if(proc.exitCode!==null)return r();proc.once('exit',r);setTimeout(r,5000).unref()});if(proc.exitCode===null)proc.kill();
 }
})().catch(e=>{console.error(e);process.exit(1)});
