/* 右側面板：原文頁（隨閱讀位置翻頁、框出當前段）。和筆記面板共用右側，一次開一個。 */
(function (PR) {
  "use strict";
  const S = PR.state;
  const body = document.body;
  let pvPage = 1, pvBlock = null;
  const pages = () => (S.paper.meta || {}).pages || [];
  const boxesOf = (loc) => loc.boxes && loc.boxes.length ? loc.boxes : [loc.box];

  /* 右側面板開關：pages | notes | null */
  /* 面板滑出的同時正文就讓位：重排只要幾十毫秒（fitWide 不再重量公式），不必等面板滑完再跳一下。 */
  PR.side = null;
  PR.openSide = function (name) {
    PR.side = name;
    body.classList.toggle("pv-open", name === "pages");
    body.classList.toggle("np-open", name === "notes");
    body.classList.toggle("ch-open", name === "chat");
    PR.$('[data-act="chat"]').classList.toggle("on", name === "chat");
    PR.$('[data-act="pages"]').classList.toggle("on", name === "pages");
    PR.$('[data-act="notes"]').classList.toggle("on", name === "notes");
    if (name) { const t = PR.$("#toast"); if (t) t.classList.remove("open"); }  // 提示條別擋住面板底部的輸入框
    if (body.classList.contains("side-open") === !!name) return;  // 面板之間切換：正文寬度不變
    const anchor = PR.readingBlock && PR.readingBlock();
    const node = anchor && document.getElementById("b-" + anchor);
    const before = node ? node.getBoundingClientRect().top : 0;
    body.classList.toggle("side-open", !!name);
    PR.fitWide(); PR.renderMargin();
    if (node) window.scrollBy(0, node.getBoundingClientRect().top - before);  // 重排後還停在剛才讀的地方
  };

  PR.togglePages = function (force) {
    const open = force != null ? force : PR.side !== "pages";
    PR.openSide(open ? "pages" : null);
    if (open) PR.syncPage(true); else pair(null);
  };
  PR.openPage = function (page, blockId) {
    pvBlock = blockId || null;
    if (PR.side !== "pages") PR.openSide("pages");
    showPage(page, blockId);
  };

  /* 原圖是 2.4 倍渲染（約 1500 像素寬、幾百 KB），面板用不了那麼大：要一張和麵板一樣寬的，服務端生成一次後快取 */
  function srcOf(n) {
    const p = pages()[n - 1];
    if (!p) return "";
    const base = PR.imageUrl(p.img);
    if (PR.store.mode !== "server") return base;
    const need = (PR.$(".pv-scroll").clientWidth || 480) * (devicePixelRatio || 1);
    return need <= 1000 ? base + "?w=1000" : need <= 1600 ? base + "?w=1600" : base;  // 1000 寬的服務端已提前生成好
  }
  let pageNodes = [], pageSource = null;
  const scroller = PR.$(".pv-scroll");
  function loadPage(n) {
    const entry = pageNodes[n - 1];
    if (!entry) return;
    const src = srcOf(n);
    if (entry.img.getAttribute("src") === src) return;
    entry.node.classList.add("loading");
    entry.img.onload = () => entry.node.classList.remove("loading");
    entry.img.setAttribute("src", src);
  }
  function loadNearby(n) {
    for (let i = Math.max(1, n - 2); i <= Math.min(pages().length, n + 2); i++) loadPage(i);
  }
  function ensurePages() {
    if (pageSource === pages()) return;
    pageSource = pages();
    pageNodes = pageSource.map((p, i) => {
      const node = document.createElement("div"), img = document.createElement("img"), hl = document.createElement("div");
      node.className = "pv-page";
      node.dataset.n = String(i + 1);
      node.style.aspectRatio = (p.w || 612) + " / " + (p.h || 792);
      img.alt = "Page " + (i + 1); img.decoding = "async";
      hl.className = "pv-hl";
      node.replaceChildren(img, hl);
      node.addEventListener("click", (e) => pickPage(e, i + 1));
      node.addEventListener("mousemove", (e) => {
        const r = node.getBoundingClientRect();
        node.classList.toggle("pickable", !!blockAt((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height, i + 1));
      });
      return { node, img, hl };
    });
    scroller.replaceChildren(...pageNodes.map(p => p.node));
  }
  PR.preloadPage = () => {}; // Images are loaded near the panel viewport.
  function updatePageLabel() {
    PR.$(".pv-label").textContent = PR.t("第 {p} / {n} 页", { p: pvPage, n: pages().length });
    const pdf = PR.$('[data-pv="pdf"]'), url = PR.pdfUrl(pvPage);
    if ((S.paper.meta || {}).format === 'epub') {
      pdf.textContent = PR.t('閱讀版 PDF');
      pdf.title = PR.t('EPUB 重新分頁產生的閱讀版 PDF，不是原書頁碼。');
    }
    pdf.style.display = url ? "" : "none";
    if (url) pdf.href = url;
  }
  function pageTop(node) {
    return node.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
  }
  let panelInput = false, programmaticUntil = 0;
  ["wheel", "pointerdown", "touchstart", "keydown"].forEach(type => scroller.addEventListener(type, () => {
    panelInput = true;
    holdUntil = Date.now() + 2000;
  }, { passive: true }));
  scroller.addEventListener("scrollend", () => { programmaticUntil = 0; });
  // Switching back to the text must immediately return control to that pane.
  ["wheel", "pointerdown", "touchstart", "keydown"].forEach(type => document.addEventListener(type, (e) => {
    if (e.target.closest("#pageview")) return;
    panelInput = false;
    holdUntil = 0;
  }, { passive: true, capture: true }));
  function followPanel(entry, middle) {
    if (!PR.$(".pv-follow input").checked) return;
    const r = entry.node.getBoundingClientRect();
    const y = Math.max(0, Math.min(1, (middle - r.top) / r.height));
    let best = null, bestBox = null, distance = Infinity;
    for (const id in S.layout) {
      const loc = S.layout[id];
      if (loc.page !== pvPage || !PR.blockById[id]) continue;
      for (const box of boxesOf(loc)) {
        if (!box) continue;
        const d = Math.max(box[1] - y, y - box[3], 0);
        if (d < distance) { best = id; bestBox = box; distance = d; }
      }
    }
    // Older imports may have page numbers but no paragraph coordinates.
    if (!best) best = Object.keys(PR.blockById).find(id => PR.blockById[id].page === pvPage);
    const node = best && document.getElementById("b-" + best);
    if (!node) return;
    pvBlock = best;
    highlightBlock(pvPage, best);
    const rect = node.getBoundingClientRect();
    const fraction = bestBox ? Math.max(0, Math.min(1, (y - bestBox[1]) / Math.max(0.001, bestBox[3] - bestBox[1]))) : 0;
    window.scrollTo({ top: Math.max(0, window.scrollY + rect.top + fraction * rect.height - window.innerHeight * 0.3), behavior: "instant" });
  }
  scroller.addEventListener("scroll", () => {
    if (!pageNodes.length || PR.side !== "pages") return;
    // Native scrollbar drags can emit scroll without a DOM pointerdown.
    if (Date.now() >= programmaticUntil) panelInput = true;
    if (panelInput) holdUntil = Date.now() + 2000;
    const middle = scroller.getBoundingClientRect().top + scroller.clientHeight / 2;
    const entry = pageNodes.find(p => p.node.getBoundingClientRect().bottom > middle) || pageNodes[pageNodes.length - 1];
    pvPage = Number(entry.node.dataset.n);
    updatePageLabel(); loadNearby(pvPage);
    if (panelInput) followPanel(entry, middle);
  }, { passive: true });

  function highlightBlock(page, blockId) {
    pageNodes.forEach(p => p.hl.classList.remove("on"));
    const hl = pageNodes[page - 1].hl;
    const loc = blockId && S.layout[blockId];
    pair(loc && loc.page === page ? blockId : null);
    if (loc && loc.page === page) {
      const boxes = boxesOf(loc);
      hl.replaceChildren(...boxes.map(([x0, y0, x1, y1]) => {
        const region = document.createElement("div");
        region.className = "pv-region";
        Object.assign(region.style, { left: (x0 * 100 - 0.4) + "%", top: (y0 * 100 - 0.3) + "%", width: ((x1 - x0) * 100 + 0.8) + "%", height: ((y1 - y0) * 100 + 0.6) + "%" });
        return region;
      }));
      hl.classList.add("on");
    }
  }

  function showPage(page, blockId) {
    const list = pages();
    if (!list.length) return;
    pvPage = Math.min(list.length, Math.max(1, page));
    ensurePages();
    panelInput = false;
    programmaticUntil = Date.now() + 1500;
    const { node } = pageNodes[pvPage - 1];
    loadNearby(pvPage); updatePageLabel();
    highlightBlock(pvPage, blockId);
    const loc = blockId && S.layout[blockId];
    if (loc && loc.page === pvPage) {
      const boxes = boxesOf(loc);
      const [, y0, , y1] = boxes[0];
      scroller.scrollTo({ top: Math.max(0, pageTop(node) + ((y0 + y1) / 2) * node.offsetHeight - scroller.clientHeight / 2), behavior: "smooth" });
    } else {
      scroller.scrollTo({ top: Math.max(0, pageTop(node) - 18), behavior: "smooth" });
    }
  }

  /* 譯文裡和原頁框對應的那段也標出來（同一個顏色），一眼看出左右是哪兩段 */
  let paired = null, holdUntil = 0;
  function pair(id) {
    if (paired === id) return;
    const old = paired && document.getElementById("b-" + paired);
    if (old) old.classList.remove("pv-pair");
    paired = id;
    const node = id && document.getElementById("b-" + id);
    if (node) node.classList.add("pv-pair");
  }
  PR.on("block-rendered", (id) => { if (id === paired) { paired = null; pair(id); } });  // 段落重畫後補回標記
  PR.on("rendered", () => { const id = paired; paired = null; pair(id); });
  PR.on("remote", (changed) => { if (PR.side === "pages" && changed.includes("layout")) showPage(pvPage, pvBlock); });

  /* 點原頁上的某一段 → 正文跳到那段譯文（排版特殊、看不出語序時，從原文找回去） */
  function blockAt(x, y, page = pvPage) {
    let best = null, area = Infinity;
    for (const id in S.layout) {
      const l = S.layout[id];
      if (l.page !== page || !PR.blockById[id]) continue;
      for (const [x0, y0, x1, y1] of boxesOf(l)) {
        const a = (x1 - x0) * (y1 - y0);
        if (x >= x0 - 0.01 && x <= x1 + 0.01 && y >= y0 - 0.006 && y <= y1 + 0.006 && a < area) { best = id; area = a; }
      }
    }
    return best;
  }
  function pickPage(e, page) {
    const r = e.currentTarget.getBoundingClientRect();
    const id = blockAt((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height, page);
    if (!id) return;
    pvPage = page;
    pvBlock = id;
    holdUntil = Date.now() + 1500;  // 跳過去的滾動會觸發“跟隨閱讀位置”，別讓它把剛點的段換掉
    showPage(pvPage, id);
    PR.jumpTo("b-" + id);
  }

  PR.syncPage = function (force) {
    if (PR.side !== "pages") return;
    if (!force && (!PR.$(".pv-follow input").checked || Date.now() < holdUntil)) return;
    const reading = PR.readingBlock();
    // Selection controls an explicit click; scrolling follows the viewport.
    const id = force ? (PR.currentBlock && PR.currentBlock()) || reading : reading;
    const b = PR.blockById[id];
    if (!b) {  // 還在標題區，不在任何一段上：給第 1 頁，別讓面板空著
      if (force || pvBlock) { pvBlock = null; showPage(1); }
      return;
    }
    if (!force && id === pvBlock) return;
    pvBlock = id;
    const loc = S.layout[id];
    showPage(loc ? loc.page : b.page, id);
  };

  PR.$("#pageview").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pv]");
    if (!b) return;
    const act = b.dataset.pv;
    if (act === "close") { PR.togglePages(false); pair(null); }
    if (act === "prev") PR.pageStep(-1);
    if (act === "next") PR.pageStep(1);
  });
  PR.refreshPages = () => showPage(pvPage);  // 面板寬度變了，按新寬度換圖
  PR.pageStep = (d) => {
    showPage(pvPage + d);
    const entry = pageNodes[pvPage - 1];
    if (!entry) return;
    holdUntil = Date.now() + 2000;
    followPanel(entry, entry.node.getBoundingClientRect().top);
  };
})(window.PR);
