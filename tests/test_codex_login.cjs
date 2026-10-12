const {test}=require('node:test');
const assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const {registerCodexLogin}=require('../electron/codex-login.cjs');
function fixture(){
 const app=new EventEmitter();app.isPackaged=true;const calls=[];let handler;
 const ipcMain={handle(_name,fn){handler=fn}};
 registerCodexLogin({app,ipcMain,resourcesPath:'C:/Synthetic/Resources',trustedWindow(e){if(e!=='trusted')throw Error('Untrusted')},exists:()=>true,
 run(command,args,options){const child=new EventEmitter();child.kill=()=>child.emit('exit',1);calls.push({command,args,options,child});return child}});
 return {app,calls,login:e=>handler(e||'trusted')};
}
test('foreign IPC cannot start CLI login',()=>{const f=fixture();assert.throws(()=>f.login('foreign'),/Untrusted/);assert.equal(f.calls.length,0)});
test('explicit login starts only one official process without a shell or session secret',{skip:process.platform!=='win32'},async()=>{
 const f=fixture();const first=f.login(),second=f.login();assert.equal(first,second);assert.equal(f.calls.length,1);
 const c=f.calls[0];assert.ok(c.command.replaceAll('\\','/').endsWith('/codex/bin/codex.exe'));assert.equal(c.args[0],'login');assert.equal(c.options.windowsHide,true);assert.equal(c.options.stdio,'ignore');assert.equal(c.options.env.PAPERDESK_SESSION,undefined);assert.equal(c.options.shell,undefined);
 c.child.emit('exit',0);assert.deepEqual(await first,{ok:true});assert.deepEqual(await second,{ok:true});
});
test('failed login and app quit clear the active process',{skip:process.platform!=='win32'},async()=>{
 const f=fixture();const first=f.login();f.calls[0].child.emit('exit',1);await assert.rejects(first,/did not complete/);
 const second=f.login();assert.equal(f.calls.length,2);f.app.emit('before-quit');await assert.rejects(second,/did not complete/);
});
