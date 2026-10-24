// Optional synthetic browser check; no model accounts or network inference used.
// Overrides: PAPERDESK_PLAYWRIGHT, PAPERDESK_CHROME and PAPERDESK_PYTHON.
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require(process.env.PAPERDESK_PLAYWRIGHT || 'playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'paperdesk-figure-browser-'));
  const env = {...process.env, EASYREAD_HOME: home, PYTHONUTF8: '1', PAPERDESK_SESSION: 'SYNTHETIC-FIGURE-TEST'};
  delete env.EASYREAD_LIBRARY;
  const python = process.env.PAPERDESK_PYTHON || path.join(root, '.venv', 'Scripts', 'python.exe');
  const seed = `import json, re
from easyread import config, engines, translate
from easyread.library import Library
from easyread.store import write_json_atomic
from scripts.smoke_backend import probe_pdf
from tests.test_epub import epub_bytes
from easyread.launch import serve
config.save({'engine':'openai','auto_translate':False,'metadata_lookup':False,'batch_pages':1,'concurrency':1,
 'openai':{'model':'synthetic','api_key':'','base_url':'http://127.0.0.1:9/v1','vision':True},
 'chat':{'models':[{'id':'synthetic','engine':'openai','model':'synthetic','preset':'custom','base_url':'http://127.0.0.1:9/v1','api':'chat'}],'default':'synthetic'}})
write_json_atomic(config.HOME/'prefs.json', {'ui':{'lang':'zh-TW'},'reader':{'theme':'dark','darkPalette':'graphite'}})
for suffix, data in [('pdf',probe_pdf()),('epub',epub_bytes())]:
 ws,_=Library(config.library_dir()).create_from_document(data,'synthetic.'+suffix)
 translate.prepare(ws)
 ws.apply_reader_ops([{'op':'paper_note','body':'Synthetic retained note'}])
def fake(cfg,prompt,cwd,images=None,cancel=None,meter=None):
 marker='要翻译的内容（键 → 英文）：'+chr(10)
 if marker in prompt:
  items=json.loads(prompt.split(marker,1)[1])
  return json.dumps({'zh':{**{k:({'image_zh':'時間（天）','image_en':'UNREQUESTED SOURCE CHANGE','src':'../../untrusted','box':[0,0,1,1]} if k.endswith('#image') else '時間（天）') for k in items},'p1':'UNREQUESTED BODY CHANGE'},'meta':{'title_zh':'UNREQUESTED TITLE CHANGE'}})
 pages=[int(n) for n in re.search(r'这次只处理第 ([0-9, ]+) 页',prompt)[1].split(',')]
 return json.dumps({'blocks':[b for n in pages for b in [
  {'id':f'p{n}','page':n,'type':'para','en':'Synthetic body text.','zh':'合成正文測試。'},
  {'id':f'f{n}','page':n,'type':'figure','box':[0.1,0.1,0.9,0.7],
   'caption_en':'Figure caption','caption_zh':'合成圖片說明','image_en':'Time (days)','image_zh':'MODEL SHOULD BE IGNORED'}]]})
engines.run=fake
translate.netcheck.problem=lambda cfg: None
serve(port=0)
`;
  const proc = spawn(python, ['-c', seed], {cwd: root, env, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe']});
  let stderr = ''; proc.stderr.on('data', d => {stderr += d.toString();});
  let browser, base;
  const errors = [], external = [];
  try {
    for (let i=0; i<200 && !fs.existsSync(path.join(home,'.server.json')); i++) {
      if (proc.exitCode !== null) throw Error(stderr);
      await new Promise(r=>setTimeout(r,100));
    }
    base=JSON.parse(fs.readFileSync(path.join(home,'.server.json'),'utf8')).url;
    const headers={'X-Token':env.PAPERDESK_SESSION,'Content-Type':'application/json'};
    const api=async (url, body) => {
      const r=await fetch(base+url,{headers,...(body===undefined?{}:{method:'POST',body:JSON.stringify(body)})});
      assert.ok(r.ok, 'HTTP '+r.status+' '+url);return r.json();
    };
    browser=await chromium.launch({headless:true,...(process.env.PAPERDESK_CHROME?{executablePath:process.env.PAPERDESK_CHROME}:{})});
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*', route => {
      const u=route.request().url();
      if(u.startsWith(base)||u.startsWith('data:')) return route.continue();
      external.push(u);return route.abort();
    });
    const page=await context.newPage(); page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/auth?session='+env.PAPERDESK_SESSION);
    await page.evaluate(()=>window.PR.openSettings());
    const checkbox=page.locator('[data-k="translate_images"]');
    await checkbox.waitFor(); assert.equal(await checkbox.isChecked(),true);
    await checkbox.uncheck();
    await page.waitForFunction(()=>window.PR.settingsState.cfg.translate_images===false);
    for(let i=0;i<50 && (await api('/api/config')).config.translate_images!==false;i++) await new Promise(r=>setTimeout(r,100));
    assert.equal((await api('/api/config')).config.translate_images,false);
    await page.keyboard.press('Escape'); await page.reload();
    await page.evaluate(()=>window.PR.openSettings());
    await checkbox.waitFor(); assert.equal(await checkbox.isChecked(),false);
    await page.screenshot({animations:'disabled',path:path.join(home,'figure-settings.png')});
    await page.keyboard.press('Escape');
    const items=(await api('/api/library')).items;
    assert.equal(items.length,2);
    const waitJob=async id=> {
      let data;
      for(let i=0;i<200;i++) {
        data=await api('/api/p/'+id+'/state');
        if(['done','partial','error','cancelled','confirm'].includes(data.job.state)) break;
        await new Promise(r=>setTimeout(r,100));
      }
      assert.equal(data.job.state,'done',JSON.stringify(data.job));return data;
    };
    for(const item of items) {
      await api('/api/p/'+item.id+'/translate',{});
      const skipped=await waitJob(item.id);
      const figures=skipped.paper.blocks.filter(b=>b.type==='figure');
      assert.ok(figures.length);
      assert.ok(figures.every(b=>b.image_translation_skipped===true&&!b.image_zh&&b.caption_zh));
      const originals=skipped.paper.blocks.filter(b=>b.type!=='figure');
      await page.goto(base+'/read/'+item.id);
      await page.locator('[data-t="translate-images"]').waitFor();
      await page.waitForFunction(()=>document.querySelector('.figure-media img')?.naturalWidth>0);
      assert.equal(await page.locator('.figure-translation').count(),0);
      const skippedExport = await (await fetch(base+'/api/p/'+item.id+'/export',{headers})).text();
      const offline = await context.newPage();
      offline.on('pageerror',e=>errors.push(e.message));
      await offline.setContent(skippedExport);
      await offline.locator('.figure-media img').first().waitFor();
      assert.equal(await offline.locator('.figure-translation').count(),0);
      assert.equal(await offline.locator('[data-t="translate-images"]').count(),0);
      await offline.close();
      await page.screenshot({animations:'disabled',path:path.join(home,'figure-skipped-'+item.format+'.png')});
      await Promise.all([page.waitForResponse(r=>r.url()===base+'/api/p/'+item.id+'/translate' && r.request().method()==='POST'), page.locator('[data-t="translate-images"]').click()]);
      const filled=await waitJob(item.id);
      assert.deepEqual(filled.paper.blocks.filter(b=>b.type!=='figure'),originals);
      assert.deepEqual(filled.reader,skipped.reader);
      for (const before of figures) {
        const after = filled.paper.blocks.find(b=>b.id===before.id);
        assert.equal(after.image_en,before.image_en);
        assert.equal(after.src,before.src);
        assert.deepEqual(after.box,before.box);
      }
      assert.ok(filled.paper.blocks.filter(b=>b.type==='figure').every(b=>b.image_zh==='時間（天）'&&!b.image_translation_skipped));
      await page.reload();await page.locator('#paper .blk').first().waitFor();
      assert.equal(await page.locator('[data-t="translate-images"]').count(),0);
      assert.equal(await page.locator('.figure-translation').count(),figures.length);
      await page.screenshot({animations:'disabled',path:path.join(home,'figure-filled-'+item.format+'.png')});
      const html=await (await fetch(base+'/api/p/'+item.id+'/export',{headers})).text();
      assert.ok(html.includes('Synthetic retained note')&&html.includes('data:image/webp;base64,'));
      const filledOffline = await context.newPage();
      filledOffline.on('pageerror',e=>errors.push(e.message));
      await filledOffline.setContent(html);
      await filledOffline.locator('.figure-translation').first().waitFor();
      assert.equal(await filledOffline.locator('.figure-translation').count(),figures.length);
      await filledOffline.close();
      for(const width of [390,900,1440]) {
        await page.setViewportSize({width,height:1000});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      }
    }
    assert.equal((await api('/api/config')).config.translate_images,false);
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log('PASS: default-on setting, save/reload, PDF/EPUB skip and image-only fill, reader persistence, exports and responsive layouts. No live model calls.');
    console.log('Synthetic evidence: '+home);
  } finally {
    if(browser) await browser.close();
    if(base) try {await fetch(base+'/api/shutdown',{method:'POST',headers:{'X-Token':env.PAPERDESK_SESSION},body:'{}'});}catch{}
    await new Promise(r=>{if(proc.exitCode!==null)return r();proc.once('exit',r);setTimeout(r,5000).unref();});
    if(proc.exitCode===null)proc.kill();
  }
})().catch(error=>{console.error(error);process.exit(1);});
