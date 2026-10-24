/* 設定的另外兩頁：閱讀（功能開關、主題）、快捷鍵（總開關、改鍵）。 */
(function (PR) {
  "use strict";
  const T = PR.settingsTabs;

  PR.accountUsageHtml = function (data) {
    if (!data || data.status !== 'available') return '<p class="hint">' + PR.t('目前無法取得官方額度；不代表剩餘為零。API 與其他服務請以供應商帳單為準。') + '</p>';
    const rows = (data.buckets || []).map(bucket => '<h4 class="set-h">' + PR.esc(bucket.name) + '</h4>' + (bucket.windows || []).map(w => {
      const remaining = w.remaining_percent == null ? NaN : Number(w.remaining_percent);
      const stale = w.resets_at && w.resets_at * 1000 <= Date.now();
      const valid = Number.isFinite(remaining) && remaining >= 0 && remaining <= 100;
      const window = Number(w.window_minutes);
      const label = window > 0 ? (window % 1440 === 0 ? PR.t('{n} 天視窗', {n: window / 1440}) : window % 60 === 0 ? PR.t('{n} 小時視窗', {n: window / 60}) : PR.t('{n} 分鐘視窗', {n: window})) : PR.t('額度視窗');
      const resets = w.resets_at ? new Date(w.resets_at * 1000).toLocaleString() : PR.t('重置時間未知');
      return '<div class="us-limit"><div class="us-row"><span>' + PR.esc(label) + '</span><strong>' + (valid && !stale ? PR.t('剩餘 {n}%', {n: remaining}) : PR.t('快照已過期')) + '</strong></div>' +
        '<div class="us-bar"><i style="width:' + (valid && !stale ? remaining : 0) + '%"></i></div><p class="hint">' + PR.esc(resets) + '</p></div>';
    }).join('')).join('');
    return rows + '<p class="hint">' + PR.t('帳號共用，包含其他 Codex 工作；不是各模型的獨立餘額。查詢時間：{time}', {time: new Date(data.at * 1000).toLocaleString()}) + '</p>';
  };
  T.usage = {
    render(s) {
      const budget = s.cfg.budget || {daily_calls: 0, daily_tokens: 0};
      const local = s.accountUsage && s.accountUsage.local_usage;
      const explanation = '<p class="set-lead">' + PR.t('透過 ChatGPT 登入 Codex CLI 時，翻譯與問答使用訂閱提供的 Codex 用量；不是一般 ChatGPT 聊天訊息額度。改用 API 金鑰則依 API 帳戶計費。') + '</p>';
      return '<h3>' + PR.t('Codex 官方帳號額度') + '</h3>' + explanation + '<p class="hint">' + PR.t('只讀取額度，不呼叫模型或消耗重置券；最多每分鐘更新一次。') + '</p>' +
        '<button class="btn" data-account-refresh' + (s.accountPending ? ' disabled' : '') + '>' + (s.accountPending ? PR.t('正在查詢額度') : PR.t('讀取官方額度')) + '</button>' +
        (s.accountUsage ? PR.accountUsageHtml(s.accountUsage) : '<p class="hint">' + PR.t('尚未查詢。已有對話與翻譯的 token 用量仍會分別保留。') + '</p>') +
        '<h3>' + PR.t('本機每日限制') + '</h3>' + (local ? '<p class="hint">' + PR.t('今日呼叫嘗試 {calls} 次；服務回報累計 {tokens} token。', {calls: Number(local.calls), tokens: Number(local.reported_tokens)}) + '</p>' : '') +
        '<div class="settings-sec grid3"><label class="field"><span>' + PR.t('每日呼叫次數上限') + '</span><input class="input" type="number" min="0" max="1000000000" step="1" data-budget="daily_calls" value="' + Number(budget.daily_calls || 0) + '"></label>' +
        '<label class="field"><span>' + PR.t('每日回報 token 上限') + '</span><input class="input" type="number" min="0" max="1000000000" step="1" data-budget="daily_tokens" value="' + Number(budget.daily_tokens || 0) + '"></label></div>' +
        '<p class="hint">' + PR.t('0 表示未啟用。翻譯與問答共用，台北時間每日歸零。達上限後停止新呼叫；已開始的回覆可能超過 token 門檻。未回報 token 的服務無法靠此限制費用。') + '</p>';
    },
    sync(s, root) {
      s.cfg.budget = s.cfg.budget || {daily_calls: 0, daily_tokens: 0};
      root.querySelectorAll('[data-budget]').forEach(input => {s.cfg.budget[input.dataset.budget] = Number(input.value);});
    },
    async click(e, s) {
      if (!e.target.closest('[data-account-refresh]') || s.accountPending) return false;
      this.sync(s, PR.$('#settingsDlg'));
      s.accountPending = true; PR.settingsRender();
      try { s.accountUsage = await PR.api('/api/usage/account'); }
      catch (_) { s.accountUsage = {status: 'unavailable'}; }
      finally { s.accountPending = false; if (s.tab === 'usage') PR.settingsRender(); }
      return true;
    },
  };

  /* ---------- 閱讀 ---------- */
  /* 排版：和閱讀頁 Aa 面板是同一份設定，這裡多一個“恢復預設” */
  function typeHtml(s) {
    if (!s.type) s.type = Object.assign({}, PR.TYPE_DEFAULTS, PR.ls.get("paperdesk-prefs", {}));
    const t = Object.assign({ view: s.type.mode === "bi" ? "both" : s.type.lead === "original" ? "original" : "translation" }, s.type), range = (a, b, step) => { const out = []; for (let v = a; v <= b + 1e-9; v += step) out.push([+v.toFixed(2), +v.toFixed(2)]); return out; };
    const sel = (key, label, list) => '<label class="field"><span>' + label + '</span><select class="input" data-type="' + key + '">' + PR.opt(list, t[key]) + "</select></label>";
    return '<h4 class="set-h">' + PR.t("排版") + '</h4><div class="settings-sec grid3">' +
      sel("fs", PR.t("字号"), range(13, 28, 1).map(([v]) => [v, PR.t("{n} px", { n: v })])) + sel("measure", PR.t("版心（每行字数）"), range(26, 50, 1).map(([v]) => [v, PR.t("{n} 字", { n: v })])) +
      sel("lh", PR.t("行距"), range(1.5, 2.4, 0.05)) + sel("font", PR.t("字体"), [["serif", PR.t("宋体")], ["sans", PR.t("黑体")]]) +
      sel("view", PR.t("打开时显示"), [["translation", PR.t("译文")], ["original", PR.t("原文")], ["both", PR.t("双语")]]) + sel("margin", PR.t("边注"), [["true", PR.t("显示")], ["false", PR.t("收起")]]) +
      '</div><div class="keys-foot" style="margin-top:4px"><span class="hint">' + PR.t("阅读时也能在右上角 Aa 里随手调。") + '</span><button class="btn sm" data-type-reset>' + PR.t("恢复默认排版") + "</button></div>";
  }
  T.reading = {
    render(s) {
      return typeHtml(s) + '<h4 class="set-h">' + PR.t("功能") + '</h4><p class="set-lead">' + PR.t("阅读页上显示哪些功能。关掉的功能，按钮和快捷键都会一起消失。") + '</p><div class="switch-list">' +
        PR.FEATURES.map(([id, name, , desc]) => '<label class="switch-row"><span><b>' + name + "</b><small>" + desc + '</small></span><input type="checkbox" class="switch" data-feat="' + id + '"' + (s.ui.features[id] !== false ? " checked" : "") + "></label>").join("") +
        "</div>" + '<label class="switch-row"><span><b>' + PR.t('線上補齊文獻資料') + '</b><small>' + PR.t('開啟後，本機 PDF 的 arXiv 編號或 DOI 會送至 arXiv／Semantic Scholar 查詢作者與年份。預設關閉；貼上網址匯入仍會連線。') + '</small></span><input type="checkbox" class="switch" id="metadataLookup"' + (s.cfg.metadata_lookup === true ? ' checked' : '') + '></label>' + '<div class="settings-sec grid2"><label class="field"><span>' + PR.t("界面主题") + '</span><select class="input" id="themeSel">' +
        PR.opt([["auto", PR.t("跟随系统")], ["light", PR.t("浅色")], ["dark", PR.t("深色")]], s.theme) + "</select></label>" +
        '<label class="field"><span>' + PR.t("深色配色") + '</span><select class="input" id="darkPaletteSel">' + PR.opt(PR.DARK_PALETTES, s.darkPalette) + "</select></label>" +
        '<p class="hint">' + PR.t("配色僅套用於深色模式；選擇後可預覽，按儲存保留，取消則還原。") + "</p>" +
        (location.protocol === "file:" ? "" : '<label class="field"><span>' + PR.t("界面语言") + '</span><select class="input" id="langSel">' +
          PR.opt([["auto", PR.t("跟随系统")], ["zh-TW", "繁體中文"], ["en", PR.t("英文")]], s.lang || PR.langChoice) + "</select></label>") + // i18n-ok
        (location.protocol === "file:" ? "" : '<label class="field"><span>' + PR.t("论文译成") + '</span><select class="input" id="targetSel">' +
          PR.opt(PR.TARGETS, s.target || PR.target) + "</select></label>") + "</div>" +
        (location.protocol === "file:" ? "" : '<p class="set-lead">' + PR.t("新翻译的论文用这个语言；已经译过的论文保持原来的语言。不需要译文的话，导入时选“读英文原文”。") + "</p>") +
        (PR.updateSection ? PR.updateSection() : "");  // 版本和檢查更新，只有文獻庫頁有（update.js）
    },
    click(e, s) {
      if (!e.target.closest("[data-type-reset]")) return false;
      s.type = Object.assign({}, s.type, PR.TYPE_DEFAULTS);  // 只重設排版，顯示方式保留
      return true;
    },
    change(e, s) {
      const t = e.target.dataset.type;
      if (t === "view") { s.type.mode = e.target.value === "both" ? "bi" : "zh"; if (e.target.value !== "both") s.type.lead = e.target.value; }  // 和閱讀頁頂欄一樣：mode + lead
      else if (t) s.type[t] = t === "margin" ? e.target.value === "true" : ["fs", "measure", "lh"].includes(t) ? +e.target.value : e.target.value;
      if (e.target.dataset.feat) s.ui.features[e.target.dataset.feat] = e.target.checked;
      if (e.target.id === "themeSel") { s.theme = e.target.value; PR.applyTheme(s.theme, s.darkPalette); }
      if (e.target.id === "darkPaletteSel") { s.darkPalette = PR.darkPalette(e.target.value); PR.applyTheme(s.theme, s.darkPalette); }
      if (e.target.id === "langSel") s.lang = e.target.value;
      if (e.target.id === "targetSel") s.target = e.target.value;
      if (e.target.id === 'metadataLookup') s.cfg.metadata_lookup = e.target.checked;
      return false;
    },
  };

  /* ---------- 快捷鍵 ---------- */
  T.keys = {
    render(s) {
      let h = '<label class="switch-row big"><span><b>' + PR.t("启用快捷键") + "</b><small>" + PR.t("关掉后只剩 Esc。单个字母的快捷键打字时不会触发，但点着页面时按到会触发。") + '</small></span><input type="checkbox" class="switch" id="keysOn"' + (s.ui.keys_on ? " checked" : "") + "></label>";
      h += '<div class="keys-list' + (s.ui.keys_on ? "" : " dim") + '">';
      let grp = "";
      for (const [id, label, , group, need] of PR.KEY_ACTIONS) {
        if (group !== grp) { h += '<div class="grp">' + group + "</div>"; grp = group; }
        const off = need && s.ui.features[need] === false;
        const k = s.ui.keys[id];
        h += "<span>" + label + (off ? ' <small class="hint">' + PR.t("（功能已关）") + "</small>" : "") + '</span><button class="kcap' + (s.recording === id ? " rec" : k ? "" : " off") + '" data-krec="' + id + '">' +
          (s.recording === id ? PR.t("按一个键…") : k ? PR.esc(PR.keyName(k)) : PR.t("未设置")) + '</button><button class="kx" data-koff="' + id + '" title="' + PR.t("不用这个快捷键") + '">' + PR.t("清除") + "</button>";
      }
      return h + '</div><div class="keys-foot"><span class="hint">' + PR.t("选中文字后 1–4 四色划线、N 笔记、Q 提问，跟着总开关。") + '</span><button class="btn sm" data-kreset>' + PR.t("恢复默认键位") + "</button></div>";
    },
    click(e, s) {
      const r = e.target.closest("[data-krec]"), off = e.target.closest("[data-koff]");
      if (r) { s.recording = s.recording === r.dataset.krec ? null : r.dataset.krec; return true; }
      if (off) { s.ui.keys[off.dataset.koff] = ""; s.recording = null; return true; }
      if (e.target.closest("[data-kreset]")) { s.ui.keys = PR.defaultKeys(); s.recording = null; return true; }
      return false;
    },
    change(e, s) { if (e.target.id === "keysOn") { s.ui.keys_on = e.target.checked; return true; } return false; },
    key(e, s) {
      if (e.key === "Escape") { s.recording = null; return true; }
      if (["Shift", "Control", "Alt", "Meta"].includes(e.key)) return false;
      const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (/^[1-4]$/.test(k)) { PR.toast(PR.t("1–4 留给选中文字后的划线")); return false; }
      const taken = Object.keys(s.ui.keys).find((id) => s.ui.keys[id] === k && id !== s.recording);
      if (taken) { s.ui.keys[taken] = ""; PR.toast(PR.t("「{name}」原来的键让给了这个操作", { name: PR.KEY_ACTIONS.find((a) => a[0] === taken)[1] })); }
      s.ui.keys[s.recording] = k;
      s.recording = null;
      return true;
    },
  };
})(window.PR);
