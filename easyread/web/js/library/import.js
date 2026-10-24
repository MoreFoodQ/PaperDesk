/* 匯入：對話框（選檔案 / 連結）+ 把 PDF 拖進窗口任何地方 + 在頁面上直接貼上連結。 */
(function (PR) {
  "use strict";
  const L = PR.lib;
  const dlg = PR.$("#importDlg");
  const SCOPES = [["all", PR.t("全文")], ["body", PR.t("正文（到参考文献为止）")], ["range", PR.t("指定页")]];
  // 匯入後做什麼：翻譯成中文 / 只閱讀原文（模型把版面排好，不翻譯）/ 只放原頁圖
  const AFTER = [["translate", PR.t("翻译成"), PR.t("后台逐页翻译，随时对照原文；译成哪种语言在右边选")],
    ["read", PR.t("閱讀原文"), PR.t("不翻譯：模型整理原文段落、公式與表格；需要譯文時可選「翻譯成{lang}」。", { lang: PR.targetName(PR.target) })],
    ["none", PR.t("先不处理"), PR.t("不用模型，阅读页先放原页图片")]];

  const pref = () => {
    const saved = PR.ls.get("paperdesk-import", null);
    // 英文介面第一次匯入預設讀原文：母語是英文的人多半不需要譯文，要翻譯時再選
    const p = Object.assign({ auto: true, scope: "all", from: 1, to: 10 }, saved || (PR.lang === "en" ? { after: "read" } : {}));
    if (p.scope === "first") Object.assign(p, { scope: "range", from: 1, to: p.first || 10 });  // 舊的“前幾頁”
    if (!p.after) p.after = p.auto ? "translate" : "none";  // 舊的“匯入後翻譯”勾選框
    return p;
  };
  const savePref = (p) => PR.ls.set("paperdesk-import", Object.assign(pref(), p));

  PR.openImport = function (ref) {
    const p = pref();
    const off = L.engine === "none";
    const after = off ? "none" : p.after;
    dlg.querySelector(".dialog").innerHTML =
      "<h2>" + PR.t("导入论文") + "</h2>" +
      '<div class="dropzone" id="pick">' + PR.icon("upload") + '<div class="big">' + PR.t("選擇 PDF 或 EPUB，或拖曳到這裡") + '</div><div class="hint">' + PR.t("可以一次選取多個；相同檔案不會重複匯入。EPUB 會重新分頁，頁碼與原書可能不同。") + "</div></div>" +
      '<div class="or">' + PR.t("或者") + "</div>" +
      '<label class="field"><span>' + PR.t("链接、arXiv 编号、DOI 或论文标题") + '</span><div class="inline"><input class="input" id="arxivRef" placeholder="' + PR.t("2411.00640 · 10.18653/v1/N19-1423 · 论文网页链接 · 论文标题") + '">' +
      '<button class="btn accent" id="arxivGo">' + PR.t("导入") + "</button></div></label>" +
      '<div class="imp-opts"><span class="imp-lbl">' + PR.t("导入后") + '</span><div class="seg" id="afterSeg">' + AFTER.map(([k, l, tip]) => '<button data-after="' + k + '" title="' + PR.esc(tip) + '" class="' + (after === k ? "on" : "") + '"' + (off && k !== "none" ? " disabled" : "") + ">" + l + "</button>").join("") + "</div>" +
        '<select class="input imp-target" id="impTarget" title="' + PR.t("译成哪种语言") + '"' + (after === "translate" ? "" : " hidden") + ">" + PR.opt(PR.TARGETS, PR.target) + "</select></div>" +
      '<p class="hint" id="originalModelHint"' + (after === "read" ? "" : " hidden") + '>' + PR.t("閱讀原文仍需模型整理內容，會消耗額度；只看文件請選「先不處理」。") + "</p>" +
      '<div class="imp-opts' + (after === "none" ? " dim" : "") + '" id="scopeRow"><span class="imp-lbl">' + PR.t("范围") + '</span><div class="seg" id="scopeSeg">' + SCOPES.map(([k, l]) => '<button data-scope="' + k + '" class="' + (p.scope === k ? "on" : "") + '">' + l + "</button>").join("") + "</div>" +
      '<span class="first-n"' + (p.scope === "range" ? "" : " hidden") + '>' + PR.t("第 {from} 到 {to} 页", { from: '<input class="input" id="pgFrom" type="number" min="1" value="' + p.from + '">', to: '<input class="input" id="pgTo" type="number" min="1" value="' + p.to + '">' }) + "</span></div>" +
      '<div class="imp-opts' + (after === "none" ? " dim" : "") + '" id="modelRow"><span class="imp-lbl">' + PR.t("模型") + '</span><select class="input" id="impModel">' +
      '<option value="">' + PR.esc(L.engineLabel || PR.t("未设置")) + "</option></select>" +
      '<button class="linkish" id="impEngine" title="' + PR.t("增删模型在设置 → 模型") + '">' + PR.t("管理模型") + "</button></div>" +
      '<div class="actions"><button class="btn" id="impClose">' + PR.t("关闭") + "</button></div>";
    dlg.classList.add("open");
    setTimeout(() => { const i = PR.$("#arxivRef"); if (ref) i.value = ref; i.focus(); }, 50);
    fillModels(p.model);
  };

  /* 模型：預設是設定裡的翻譯引擎，也可以直接選“問 AI”名單裡配好的模型 */
  async function fillModels(want) {
    let r;
    try { r = await PR.api("/api/chat/models"); } catch (e) { return; }
    const sel = PR.$("#impModel");
    if (!sel) return;
    // 標著“翻譯”的那張卡片就是空值（用設定裡的翻譯設定，包括“能看圖”）；對不上時才留第一項翻譯引擎
    if (r.translate) sel.innerHTML = "";
    sel.insertAdjacentHTML("beforeend", (r.models || []).map((m) =>
      '<option value="' + (m.id === r.translate ? "" : PR.esc(m.id)) + '"' + (m.ready ? "" : " disabled") + ">" + PR.esc(m.label + " · " + m.source) + "</option>").join(""));
    const ok = (r.models || []).some((m) => m.id === want && m.id !== r.translate && m.ready);
    sel.value = ok ? want : "";
  }
  const close = () => dlg.classList.remove("open");
  function opts() {
    const p = pref();
    const after = L.engine === "none" ? "none" : p.after;
    const from = Math.max(1, +p.from || 1), to = Math.max(1, +p.to || from);
    const scope = p.scope === "range" ? "range:" + Math.min(from, to) + "-" + Math.max(from, to) : p.scope;
    const sel = PR.$("#impModel"), tgt = PR.$("#impTarget");  // 拖進來匯入時對話框沒開，用設定裡的譯文語言
    return { translate: after !== "none", read: after === "read", scope, model: after === "none" ? "" : sel ? sel.value : "",
      target: after === "translate" ? (tgt ? tgt.value : PR.target) : "" };
  }

  dlg.addEventListener("click", (e) => {
    if (e.target === dlg || e.target.closest("#impClose")) close();
    if (e.target.closest("#pick")) PR.$("#fileInput").click();
    if (e.target.closest("#arxivGo")) importRef(PR.$("#arxivRef").value);
    if (e.target.closest("#impEngine")) { close(); PR.openSettings(); }
    const a = e.target.closest("[data-after]");
    if (a && !a.disabled) {
      savePref({ after: a.dataset.after });
      PR.$$("[data-after]", dlg).forEach((b) => b.classList.toggle("on", b === a));
      PR.$("#scopeRow").classList.toggle("dim", a.dataset.after === "none");
      PR.$("#modelRow").classList.toggle("dim", a.dataset.after === "none");
      PR.$("#impTarget").hidden = a.dataset.after !== "translate";
      PR.$("#originalModelHint").hidden = a.dataset.after !== "read";
    }
    const s = e.target.closest("[data-scope]");
    if (s) {
      savePref({ scope: s.dataset.scope });
      PR.$$("[data-scope]", dlg).forEach((b) => b.classList.toggle("on", b === s));
      PR.$(".first-n", dlg).hidden = s.dataset.scope !== "range";
    }
  });
  dlg.addEventListener("change", (e) => { if (e.target.id === "impModel") savePref({ model: e.target.value }); });
  dlg.addEventListener("input", (e) => {  // 邊輸邊存：輸完直接點“匯入”也用新的頁碼
    if (e.target.id === "pgFrom") savePref({ from: +e.target.value || 1 });
    if (e.target.id === "pgTo") savePref({ to: +e.target.value || 1 });
  });
  dlg.addEventListener("keydown", (e) => { if (e.target.id === "arxivRef" && e.key === "Enter") importRef(e.target.value); if (e.key === "Escape") close(); });
  PR.$("#importBtn").onclick = () => PR.openImport();
  PR.$("#fileInput").addEventListener("change", (e) => { importFiles(Array.from(e.target.files)); e.target.value = ""; });

  async function importFiles(files) {
    const pdfs = files.filter((f) => /\.(pdf|epub)$/i.test(f.name) || ["application/pdf", "application/epub+zip"].includes(f.type));
    if (!pdfs.length) return PR.toast(PR.t("支援 PDF 與 EPUB 檔案"));
    close();
    const o = opts();
    let last = null;
    for (const [k, f] of pdfs.entries()) {
      PR.toast(PR.t("正在导入 {i}/{n}：{name}", { i: k + 1, n: pdfs.length, name: PR.esc(f.name) }), null, 60000);
      try {
        const r = await PR.api("/api/import?translate=" + (o.translate ? 1 : 0) + "&read=" + (o.read ? 1 : 0) + "&model=" + encodeURIComponent(o.model) + "&target=" + encodeURIComponent(o.target) + "&scope=" + encodeURIComponent(o.scope) + "&name=" + encodeURIComponent(f.name), { method: "POST", body: f });
        last = r.id;
        if (!r.new) PR.toast(r.queued ? PR.t("《{name}》已重新加入准备队列", { name: PR.esc(f.name) }) : PR.t("《{name}》已经在库里了", { name: PR.esc(f.name) }));
      } catch (e) { PR.toast(PR.t("导入失败：{msg}", { msg: PR.esc(e.message) })); }
    }
    await L.load();
    if (last) { L.select(last); PR.toast((o.read ? PR.t("已导入 {n} 篇，后台开始整理原文", { n: pdfs.length }) : o.translate ? PR.t("已导入 {n} 篇，后台开始翻译", { n: pdfs.length }) : PR.t("已导入 {n} 篇", { n: pdfs.length })), { label: PR.t("打开"), fn: () => L.openReader(last) }, 6000); }
  }

  async function importRef(ref) {
    ref = (ref || "").trim();
    if (!ref) return;
    const btn = PR.$("#arxivGo");
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spin"></span> ' + PR.t("查找中"); }
    else PR.toast('<span class="spin"></span> ' + PR.t("正在查找并下载 {ref}", { ref: PR.esc(ref) }), null, 60000);
    const o = opts();
    try {
      const r = await PR.api("/api/import-url", { method: "POST", body: { ref, translate: o.translate, read: o.read, model: o.model, scope: o.scope, target: o.target } });
      close();
      await L.load();
      L.select(r.id);
      PR.toast(r.new ? (o.read ? PR.t("已导入，后台开始整理原文") : o.translate ? PR.t("已导入，后台开始翻译") : PR.t("已导入")) : r.queued ? PR.t("已重新加入准备队列") : PR.t("这篇已经在库里了"), { label: PR.t("打开"), fn: () => L.openReader(r.id) }, 6000);
    } catch (e) {
      PR.toast(PR.t("导入失败：{msg}", { msg: PR.esc(e.message) }), null, 8000);
      if (btn) { btn.disabled = false; btn.textContent = PR.t("导入"); }
    }
  }
  PR.importRef = importRef;

  /* 在文獻庫頁面直接 Ctrl+V 一個連結或 arXiv 編號 */
  document.addEventListener("paste", (e) => {
    if (e.target.closest("input, textarea, [contenteditable]") || PR.$(".dialog-backdrop.open")) return;
    const files = Array.from(e.clipboardData.files || []);
    if (files.length) { e.preventDefault(); return importFiles(files); }
    const t = (e.clipboardData.getData("text") || "").trim();
    if (/^(https?:\/\/\S+|(arxiv:)?\d{4}\.\d{4,5}(v\d+)?|(doi:\s*)?10\.\d{4,9}\/\S+)$/i.test(t)) { e.preventDefault(); PR.openImport(t); }
  });

  /* 拖進窗口任何地方都能匯入 */
  let depth = 0;
  const overlay = PR.$("#dropOverlay");
  const hasFiles = (e) => Array.from(e.dataTransfer && e.dataTransfer.types || []).includes("Files");
  window.addEventListener("dragenter", (e) => { if (!hasFiles(e)) return; depth++; overlay.classList.add("on"); });
  window.addEventListener("dragleave", () => { depth = Math.max(0, depth - 1); if (!depth) overlay.classList.remove("on"); });
  window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault(); depth = 0; overlay.classList.remove("on");
    importFiles(Array.from(e.dataTransfer.files));
  });
})(window.PR);
