/* 句子對齊：paper.json 的段落和清單項可以帶 sents（[[英文句尾, 譯文句尾], …]，按 JS 字串位置，最後一項是兩邊總長）。
   有就把原文和譯文都切成一句一個 <span class="snt" data-s="i">，兩邊同號的句子互相對應；
   沒有（舊論文、模型沒對上）、或者譯文被我改過（“我的修改”），就按整段對應。
   標註同步：一邊有劃線或筆記，另一邊對應的句子（沒有句子對應時是整段）標一道虛線或段邊色條，點它和點劃線一樣。 */
(function (PR) {
  "use strict";
  const S = PR.state;

  function objOf(key) {
    const [id, field] = String(key).split("#");
    const b = PR.blockById[id];
    if (!b) return null;
    if (b.type === "para" && field == null) return b;
    if (b.type === "list" && /^\d+$/.test(field || "")) return (Array.isArray(b.items) ? b.items : [])[+field] || null;
    return null;
  }

  /* 這處的句子對齊還對得上文字就回傳 sents，否則 null */
  PR.alignOf = function (key) {
    const o = objOf(key);
    const s = o && o.sents;
    if (!Array.isArray(s) || s.length < 2) return null;
    const en = o.en || "", zh = o.zh || "", last = s[s.length - 1];
    if (!Array.isArray(last) || last[0] !== en.length || last[1] !== zh.length) return null;
    for (let i = 0; i < s.length; i++) {
      const prev = i ? s[i - 1] : [0, 0];
      if (!Array.isArray(s[i]) || !(s[i][0] > prev[0]) || !(s[i][1] > prev[1])) return null;
    }
    return s;
  };

  const balanced = (t) => (t.split("**").length % 2 === 1) && ((t.match(/(?<!\\)\$/g) || []).length % 2 === 0);

  /* 正文 HTML：對得上就一句一個 span，否則和原來一樣整段 PR.md。side：en 原文 / zh 譯文 */
  PR.sentMd = function (key, side, text) {
    const s = PR.alignOf(key), o = objOf(key);
    if (!s || !o || (side === "zh" && PR.editOf(key)) || text !== (side === "en" ? o.en : o.zh)) return PR.md(text);
    const col = side === "en" ? 0 : 1;
    const parts = [];
    let prev = 0;
    for (const row of s) { parts.push(text.slice(prev, row[col])); prev = row[col]; }
    if (!parts.every(balanced)) return PR.md(text);  // 句界切在 **粗體** 或公式中間：不切，整段顯示
    return parts.map((p, i) => {
      const lead = p.match(/^\s*/)[0];
      return lead + '<span class="snt" data-s="' + i + '">' + PR.md(p.slice(lead.length)) + "</span>";
    }).join("");
  };

  /* ---------- 原文 / 譯文兩個元素互相找 ---------- */
  const isEnEl = (el) => el.classList.contains("en") || el.classList.contains("en-main");
  PR.isEnEl = isEnEl;
  /* 原文元素對應的 .zh[data-key]（同一層的兄弟；閱讀原文沒譯的塊，.zh 自己就是原文） */
  PR.zhOfEl = function (el) {
    if (el.classList.contains("zh")) return el;
    return Array.from(el.parentElement ? el.parentElement.children : []).find((n) => n.classList.contains("zh") && n.dataset.key) || null;
  };
  PR.enOfZh = function (zh) {
    if (!zh || zh.classList.contains("en-main")) return null;
    return Array.from(zh.parentElement ? zh.parentElement.children : []).find((n) => n.classList.contains("en")) || null;
  };
  /* 一條標註掛在哪個元素上：side 為 en 找原文，其餘（舊標註沒有 side）找譯文 */
  PR.noteEl = function (zh, side) {
    if (!zh) return null;
    if (side !== "en" || zh.classList.contains("en-main")) return zh;
    return PR.enOfZh(zh);
  };
  const partner = (el) => (isEnEl(el) && !el.classList.contains("en-main") ? PR.zhOfEl(el) : el.classList.contains("zh") && !el.classList.contains("en-main") ? PR.enOfZh(el) : null);

  /* ---------- 標註同步到另一邊 ---------- */
  const MIR = ["mir", "mir-para", "c-yellow", "c-green", "c-blue", "c-pink", "mir-q"];
  PR.applyMirrors = function (scope) {
    scope = scope || PR.$("#paper");
    if (!scope) return;
    PR.$$("[data-mirror]", scope).forEach((el) => { el.classList.remove(...MIR); el.removeAttribute("data-mirror"); el.removeAttribute("title"); });
    const byNote = {};  // 一次取出所有劃線按筆記分組，不必每條筆記查一遍全文
    PR.$$("mark.hl[data-note]", scope).forEach((m) => (byNote[m.dataset.note] = byNote[m.dataset.note] || []).push(m));
    for (const n of PR.myNotes()) {
      const marks = n.quote && byNote[n.id];
      if (!marks) continue;
      const src = marks[0].closest(".zh, .en");
      const other = src && partner(src);
      if (!other) continue;
      const idx = new Set(marks.map((m) => m.closest(".snt")).filter(Boolean).map((sp) => sp.dataset.s));
      const spans = idx.size ? PR.$$(":scope .snt", other).filter((sp) => idx.has(sp.dataset.s)) : [];
      const targets = spans.length ? spans : [other];
      const cls = [spans.length ? "mir" : "mir-para", "c-" + (n.color || "yellow")].concat(n.kind === "question" ? ["mir-q"] : []);
      const tip = isEnEl(src) ? PR.t("对应原文里的标注") : PR.t("对应译文里的标注");
      // 同一處有幾條標註時留第一條（按時間排在前面的），顏色不會疊在一起
      targets.filter((t) => !t.dataset.mirror).forEach((t) => { t.classList.add(...cls); t.dataset.mirror = n.id; t.title = tip; });
    }
  };

  /* 點同步標記：和點劃線一樣（劃線彈改色菜單，筆記和問題打開編輯）。
     整段的同步標記只有段邊那道色條能點，點段落其餘地方照常（出操作條、按兩下改譯文）；正在改這段時不攔 */
  document.addEventListener("click", (e) => {
    const el = e.target.closest && e.target.closest("[data-mirror]");
    if (!el || e.target.closest("mark.hl, a, button, textarea") || el.querySelector("textarea") || getSelection().toString()) return;
    if (el.classList.contains("mir-para")) {
      const r = el.getBoundingClientRect();
      if (e.clientX > r.left + 14) return;
    }
    const n = (S.reader.notes || {})[el.dataset.mirror];
    if (!n || n.deleted) return;
    e.stopPropagation();
    PR.noteMarkClick(el, n);
  }, true);

  /* 雙語對照時指著一句，另一邊對應的那句也淡淡標出來 */
  let lit = [];
  document.addEventListener("mouseover", (e) => {
    const sp = e.target.closest && e.target.closest("#paper .snt");
    const host = sp && sp.closest(".zh, .en");
    const other = host && partner(host);
    const pair = other && other.offsetParent ? PR.$$(":scope .snt", other).find((x) => x.dataset.s === sp.dataset.s) : null;
    const next = pair ? [sp, pair] : [];
    if (next[0] === lit[0]) return;
    lit.forEach((x) => x.classList.remove("pair"));
    lit = next;
    lit.forEach((x) => x.classList.add("pair"));
  });
})(window.PR);
