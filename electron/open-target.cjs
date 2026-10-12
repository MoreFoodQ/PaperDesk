function classify(target, backendUrl) {
  let url;
  try { url=new URL(target); } catch { return 'deny'; }
  if (!['http:','https:'].includes(url.protocol) || url.username || url.password) return 'deny';
  if (backendUrl && url.origin===backendUrl) {
    if (/^\/p\/[A-Za-z0-9_-]{4,64}\/source\.epub$/.test(url.pathname)) return 'download';
    return 'local';
  }
  return 'external';
}
function policy(target, backendUrl, contents, openExternal, background=false) {
  const kind=classify(target,backendUrl);
  if (kind==='local') return {action:'allow',overrideBrowserWindowOptions:{show:!background,
    webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true,preload:'',plugins:true}}};
  if (kind==='download') contents.downloadURL(target);
  if (kind==='external') openExternal(target);
  return {action:'deny'};
}
module.exports={classify,policy};
