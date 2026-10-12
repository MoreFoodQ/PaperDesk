// Login is an explicit user action. Native CLI opens the official browser flow.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawn } = require('node:child_process');

function registerCodexLogin({app, ipcMain, trustedWindow, resourcesPath, run=spawn, exists=fs.existsSync}) {
  let active = null;
  ipcMain.handle('paperdesk:codex-login', event => {
    trustedWindow(event);
    if (!app.isPackaged || process.platform !== 'win32') throw Error('Bundled Windows login is unavailable.');
    if (active) return active.promise;
    const executable = path.join(resourcesPath, 'codex', 'bin', 'codex.exe');
    if (!exists(executable)) throw Error('Bundled Codex CLI is missing. Reinstall PaperDesk.');
    const allowed = new Set(['SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP','USERPROFILE','HOME',
      'APPDATA','LOCALAPPDATA','CODEX_HOME','HTTPS_PROXY','HTTP_PROXY','ALL_PROXY','NO_PROXY']);
    const env = Object.fromEntries(Object.entries(process.env).filter(([key])=>allowed.has(key.toUpperCase())));
    const child = run(executable, ['login', '-c', 'features.hooks=false', '-c', 'notify=[]'],
      {cwd:os.homedir(), env, windowsHide:true, stdio:'ignore'});
    const state = {child};
    active = state;
    state.promise = new Promise((resolve, reject) => {
      const timer = setTimeout(()=>{child.kill();finish(reject,Error('Login timed out. Try again.'));}, 15*60*1000);
      let finished = false;
      function finish(done, result){if(finished)return;finished=true;clearTimeout(timer);if(active===state)active=null;done(result)}
      child.once('error',()=>finish(reject,Error('Could not start bundled Codex login.')));
      child.once('exit',code=>code===0?finish(resolve,{ok:true}):finish(reject,Error('Codex login did not complete. Try again.')));
    });
    return state.promise;
  });
  app.on('before-quit',()=>{if(active)active.child.kill()});
}
module.exports = {registerCodexLogin};
