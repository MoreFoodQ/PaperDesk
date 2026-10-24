// easyread://open?sha256=…&block=… 打開指定論文和段落（給 Zotero 插件等外部工具用，約定見 docs/api.md）。
// 桌面版只做轉發：交給後端的 /open，由後端按指紋找論文。
const { URL } = require("url");

const SCHEME = "paperdesk";

// 只放行 open 和已知參數，別的連結一律忽略，不把任意內容帶進後端位址
function openPath(link) {
  let url;
  try { url = new URL(link); } catch { return null; }
  if (url.protocol !== `${SCHEME}:` || (url.hostname || url.pathname.replace(/^\/+/, "")) !== "open") return null;
  const query = new URLSearchParams();
  for (const key of ["sha256", "id", "block"]) {
    const value = url.searchParams.get(key);
    if (value && /^[A-Za-z0-9_-]{1,64}$/.test(value)) query.set(key, value);
  }
  return query.has("sha256") || query.has("id") ? `/open?${query}` : null;
}

// Windows / Linux 把連結放在命令列參數裡（首次啟動和 second-instance 都是）
function fromArgv(argv) {
  const link = (argv || []).find(arg => typeof arg === "string" && arg.toLowerCase().startsWith(`${SCHEME}:`));
  return link ? openPath(link) : null;
}

function register(app, proc) {
  if (!app.setAsDefaultProtocolClient) return;
  // 開發時（electron .）要把入口指令碼一起登記，否則系統會啟動一個空的 Electron
  if (proc.defaultApp && proc.argv && proc.argv.length >= 2) {
    app.setAsDefaultProtocolClient(SCHEME, proc.execPath, [require("path").resolve(proc.argv[1])]);
  } else {
    app.setAsDefaultProtocolClient(SCHEME);
  }
}

module.exports = { SCHEME, openPath, fromArgv, register };
