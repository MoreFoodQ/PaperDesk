/* 閱讀頁的資料與儲存。
   - paper / discussion / layout / job 來自翻譯方，唯讀；
   - reader（我的修改、筆記、論文筆記、進度）只透過“操作”改：先進瀏覽器裡的待存佇列，再發給本機服務，
     服務確認寫進 reader.json 後才從佇列刪。斷網、服務沒開、頁面崩了，佇列都還在，下次自動補發。
   - 離線版（匯出的單檔案）沒有服務，佇列本身就是儲存，可匯出後並回。 */
(function (PR) {
  "use strict";
  const S = (PR.state = { paper: null, discussion: { entries: [] }, reader: {}, layout: {}, item: {}, job: {}, images: {}, versions: {}, engine: "none" });
  let mode = "server";
  let serverReader = null;
  let outbox = [];
  let outboxKey = "";
  let flushing = false, retryMs = 1500, retryT = null, flushT = null;
  const client = PR.uid("c");
  PR.pid = decodeURIComponent((location.pathname.match(/\/read\/([^/]+)/) || [])[1] || "");
  const base = () => "/api/p/" + PR.pid;

  PR.store = { get mode() { return mode; }, get pending() { return outbox.length; } };

  /* ---------- 和 Python store.apply_ops 同一套規則 ---------- */
  function applyOps(reader, ops) {
    reader.edits = reader.edits || {};
    reader.notes = reader.notes || {};
    reader.progress = reader.progress || {};
    for (const op of ops) {
      const at = op.at || PR.nowIso();
      if (op.op === "edit") {
        const cur = reader.edits[op.block];
        if (cur && (cur.at || "") > at) continue;
        if (op.zh == null) { if (cur) reader.edits[op.block] = { reverted: true, prev: cur.zh, at }; }
        else {
          const e = { zh: op.zh, base: op.base || "", at };
          if (cur && cur.zh && cur.zh !== op.zh) e.prev = cur.zh;
          reader.edits[op.block] = e;
        }
      } else if (op.op === "note") {
        const cur = reader.notes[op.note.id];
        if (cur && (cur.updated || "") > (op.note.updated || "")) continue;
        reader.notes[op.note.id] = JSON.parse(JSON.stringify(op.note));
      } else if (op.op === "note_del") {
        const cur = reader.notes[op.id];
        if (!cur || at >= (cur.updated || "")) reader.notes[op.id] = { ...(cur || { id: op.id }), deleted: true, updated: at };
      } else if (op.op === "paper_note") {
        const cur = reader.paper_note || {};
        if (at >= (cur.at || "")) reader.paper_note = { body: op.body || "", at };
      } else if (op.op === "progress") {
        if (at >= (reader.progress.at || "")) Object.assign(reader.progress, { block: op.block, at }, op.ratio != null ? { ratio: op.ratio } : {});
      }
    }
    return reader;
  }

  function rebuildReader() { S.reader = applyOps(JSON.parse(JSON.stringify(serverReader || {})), outbox); }
  function saveOutbox() { if (!PR.ls.set(outboxKey, outbox)) setStatus("error", PR.t("浏览器存储已满，修改只在内存里，请尽快导出")); }
  function setStatus(s, text) { PR.store.status = s; PR.emit("status", { s, text, pending: outbox.length }); }
  function statusIdle() {
    if (mode === "static") setStatus("local", outbox.length ? PR.t("存在本浏览器") : PR.t("离线版"));
    else setStatus("saved", PR.t("已保存"));
  }

  /* 頁面呼叫這個提交修改 */
  PR.commit = function (op) {
    op.at = op.at || PR.nowIso();
    // 同一目標還沒發出去的舊操作合併掉，避免佇列無限長
    if (op.op === "note") outbox = outbox.filter((o) => !(o.op === "note" && o.note.id === op.note.id));
    if (op.op === "edit") outbox = outbox.filter((o) => !(o.op === "edit" && o.block === op.block));
    if (op.op === "progress" || op.op === "paper_note") outbox = outbox.filter((o) => o.op !== op.op);
    outbox.push(op);
    saveOutbox();
    rebuildReader();
    PR.emit("reader", op);
    if (mode === "server") { if (op.op !== "progress") setStatus("saving", PR.t("保存中")); scheduleFlush(op.op === "progress" ? 3000 : 250); }
    else statusIdle();
  };

  function scheduleFlush(ms) { clearTimeout(flushT); flushT = setTimeout(flush, ms); }

  async function flush() {
    if (mode !== "server" || flushing || !outbox.length) return;
    flushing = true;
    const batch = outbox.slice();
    try {
      const r = await fetch(base() + "/ops", {
        method: "POST", headers: { "Content-Type": "application/json", "X-Token": PR.token || "" },
        body: JSON.stringify({ ops: batch, client }),
      });
      if (r.status === 403) { await reloadToken(); throw new Error("token"); }
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status);
      const res = await r.json();
      outbox = outbox.filter((o) => !batch.includes(o));   // 已寫入磁碟的刪掉，期間新加的保留
      saveOutbox();
      serverReader = applyOps(JSON.parse(JSON.stringify(serverReader || {})), batch);
      serverReader.rev = res.rev;
      // 只認 reader 的新版本：paper / layout 等要由輪詢去取內容，這裡提前記上版本號，輪詢就以為沒變、不再重畫
      if (res.versions && res.versions.reader) S.versions.reader = res.versions.reader;
      rebuildReader();
      retryMs = 1500;
      if (outbox.length) scheduleFlush(50); else statusIdle();
    } catch (e) {
      setStatus("offline", PR.t("未连上本地服务，{n} 条修改暂存在浏览器", { n: outbox.length }));
      clearTimeout(retryT);
      retryT = setTimeout(flush, retryMs);
      retryMs = Math.min(retryMs * 2, 15000);
    } finally {
      flushing = false;
    }
  }
  PR.flush = flush;

  async function reloadToken() {
    try { PR.token = (await (await fetch(base() + "/state", { cache: "no-store" })).json()).token; } catch (e) { /* 下次重試 */ }
  }

  /* ---------- 載入 ---------- */
  PR.load = async function () {
    const embedded = document.getElementById("pr-data");
    if (embedded) {
      const d = JSON.parse(embedded.textContent);
      mode = "static";
      Object.assign(S, { paper: d.paper, discussion: d.discussion || { entries: [] }, layout: d.layout || {}, images: d.images || {}, item: d.item || {}, chat: d.chat || null, demo: d.demo || null });
      serverReader = d.reader || {};
      PR.pid = PR.pid || (S.paper.meta.source_sha256 || "paper").slice(0, 12);
    } else {
      if (!PR.pid) throw new Error(PR.t("地址里没有论文 id"));
      const r = await fetch(base() + "/state", { cache: "no-store" });
      if (!r.ok) throw new Error(r.status === 404 ? PR.t("文献库里没有这篇论文") : PR.t("读取数据失败：{status}", { status: r.status }));
      const d = await r.json();
      PR.token = d.token;
      Object.assign(S, { paper: d.paper, discussion: d.discussion, layout: d.layout || {}, item: d.item || {}, job: d.job || {}, versions: d.versions, engine: d.engine });
      serverReader = d.reader || {};
    }
    const ov = (S.item || {}).meta_override || {};
    for (const [k, v] of Object.entries(ov)) if (v) S.paper.meta[k] = v;
    outboxKey = "pr-outbox-" + PR.pid + (mode === "static" ? "-static" : "");
    PR.paperKey = PR.pid;
    outbox = PR.ls.get(outboxKey, []);
    rebuildReader();
    if (mode === "server" && outbox.length) { setStatus("saving", PR.t("补存上次未保存的 {n} 条修改", { n: outbox.length })); scheduleFlush(300); }
    else statusIdle();
  };

  PR.imageUrl = (rel) => {
    if (typeof rel !== "string" || !/^(pages|figures)\/[A-Za-z0-9_.-]+\.(webp|png|jpe?g)$/i.test(rel)) return "";
    return mode === "static" ? S.images[rel] || "" : "/p/" + encodeURIComponent(PR.pid) + "/" + rel;
  };
  PR.pdfUrl = (page) => (mode === "static" ? "" : "/p/" + PR.pid + "/source.pdf#page=" + page);
  PR.canAsk = () => mode === "server" && S.engine && S.engine !== "none";

  /* ---------- 輪詢：翻譯方追加討論/譯文、背景翻譯進度、另一個標籤頁改了筆記 ---------- */
  async function poll() {
    if (mode !== "server" || document.hidden) return;
    let v;
    try {
      v = await (await fetch(base() + "/versions", { cache: "no-store" })).json();
      if (PR.store.status === "offline") flush();
    } catch (e) {
      if (!outbox.length) setStatus("offline", PR.t("未连上本地服务（只读）"));
      return;
    }
    const changed = [];
    for (const name of ["paper", "discussion", "layout", "reader", "job"]) if (v[name] && v[name] !== S.versions[name]) changed.push(name);
    if (!changed.length) return;
    for (const name of changed) {
      if (name === "reader" && (flushing || outbox.length)) continue; // 自己正在寫，等寫完
      const d = await (await fetch(base() + "/part/" + name, { cache: "no-store" })).json();
      S.versions[name] = d.version;
      if (name === "reader") { serverReader = d.data; rebuildReader(); } else S[name] = d.data || {};
    }
    if (changed.includes("paper")) { const ov = (S.item || {}).meta_override || {}; for (const [k, val] of Object.entries(ov)) if (val) S.paper.meta[k] = val; }
    PR.emit("remote", changed);
  }
  PR.poll = poll;
  PR.startPolling = function () {
    if (mode !== "server") return;
    setInterval(poll, 2500);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
    window.addEventListener("focus", poll);
    window.addEventListener("online", flush);
  };

  window.addEventListener("beforeunload", (e) => {
    if (mode === "server" && outbox.some((o) => o.op !== "progress")) { flush(); e.preventDefault(); e.returnValue = ""; }
  });

  /* 讓模型做事（回答問題、重譯一段）：交給服務的小任務佇列 */
  PR.ask = async function (kind, body) {
    const job = await PR.api(base() + "/" + kind, { method: "POST", body });
    PR.emit("job-started", job);
    const t = setInterval(async () => {
      const list = (await PR.api("/api/jobs?pid=" + encodeURIComponent(PR.pid))).jobs;
      const j = list.find((x) => x.id === job.id);
      if (!j || ["done", "error"].includes(j.state)) {
        clearInterval(t);
        await poll();
        PR.emit("job-finished", j || job);
      }
    }, 2000);
    return job;
  };

  /* ---------- 匯出 ---------- */
  PR.exportOps = function () {
    const ops = [];
    for (const [block, e] of Object.entries(S.reader.edits || {})) if (e.zh != null) ops.push({ op: "edit", block, zh: e.zh, base: e.base, at: e.at });
    for (const n of Object.values(S.reader.notes || {})) ops.push({ op: "note", note: n, at: n.updated });
    if ((S.reader.paper_note || {}).body) ops.push({ op: "paper_note", body: S.reader.paper_note.body, at: S.reader.paper_note.at });
    return { paper: PR.paperKey, exported: PR.nowIso(), ops };
  };
})(window.PR);
