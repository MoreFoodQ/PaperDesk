/* 正文顯示方式：原文 / 譯文 / 雙語，雙語旁邊的 ▾ 選原文在前還是譯文在前。只改排列順序和顯隱，
   .zh 始終是譯文、data-key 不變，筆記、高亮和改過的譯文都還對應原來的內容。
   偏好：mode（zh 單語 / bi 雙語），lead 單語看哪種，biOrder 雙語哪種在前，兩者互不影響。 */
(function (PR) {
  "use strict";
  const S = PR.state;
  const targetCode = () => (S.paper && S.paper.meta && S.paper.meta.target) || (S.item || {}).target || "zh";
  PR.readingView = () => (PR.prefs.mode === "bi" ? "both" : PR.prefs.lead === "original" ? "original" : "translation");
  PR.originalFirst = () => (PR.prefs.mode === "bi" ? PR.prefs.biOrder : PR.prefs.lead) === "original";
  PR.viewLabels = function () {
    const lang = PR.targetName(targetCode());
    return {
      original: PR.t("原文"), translation: PR.t("译文"), both: PR.t("双语"),
      originalFull: PR.t("{lang}原文", { lang: PR.t("英文") }), translationFull: PR.t("{lang}译文", { lang }),
    };
  };
  /* 切換顯示方式：mode 和 lead / biOrder 一起改，再走 setPref 保住閱讀位置 */
  PR.setView = function (view) {
    if (view !== "both") PR.prefs.lead = view;
    PR.setPref("mode", view === "both" ? "bi" : "zh");
  };
  PR.setBiOrder = function (first) {
    PR.prefs.biOrder = first;
    PR.setPref("mode", "bi");
  };

  const CARET = '<svg class="i sm" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 8l4 4 4-4"/></svg>';
  function viewTitle(k, L) {
    if (k !== "both") return L[k + "Full"];
    return PR.t("双语，{what}在前（B）", { what: PR.prefs.biOrder === "original" ? L.original : L.translation });
  }
  /* 頂欄和窄屏 Aa 共用一份按鈕；窄屏沒地方彈菜單，順序直接排成第二行 */
  PR.viewSegHtml = function (narrow) {
    const L = PR.viewLabels(), v = PR.readingView();
    const b = (k) => '<button data-view="' + k + '" class="' + (v === k ? "on" : "") + '" title="' + PR.esc(viewTitle(k, L)) + '">' + PR.esc(L[k]) + "</button>";
    if (!narrow) return '<div class="seg view-seg">' + b("original") + b("translation") + b("both") + "</div>";
    const o = (k) => '<button data-order="' + k + '" class="' + (PR.prefs.biOrder === k ? "on" : "") + '">' + PR.esc(PR.t("{what}在前", { what: L[k] })) + "</button>";
    return '<div class="seg view-seg">' + b("original") + b("translation") + b("both") + "</div>" +
      '<div class="order-line"><span>' + PR.t("双语顺序") + '</span><div class="seg">' + o("original") + o("translation") + "</div></div>";
  };

  const menu = PR.el("div", { id: "orderMenu", class: "menu menu-list", role: "menu" });
  document.body.append(menu);
  function renderMenu() {
    const L = PR.viewLabels();
    menu.innerHTML = ["original", "translation"].map((k) => {
      const on = PR.prefs.mode === "bi" && PR.prefs.biOrder === k;
      return '<button role="menuitemradio" aria-checked="' + on + '" data-order="' + k + '">' +
        '<span class="tick">' + (on ? PR.icon("check", "sm") : "") + "</span>" + PR.esc(PR.t("{what}在前", { what: L[k] })) + "</button>";
    }).join("");
  }
  PR.toggleOrderMenu = function (force) {
    const caret = PR.$("#bar [data-order-menu]");
    const open = force != null ? force : !menu.classList.contains("open");
    if (open && caret) {
      renderMenu();
      const r = caret.getBoundingClientRect();
      menu.style.top = r.bottom + 6 + "px";
      menu.style.left = Math.max(8, Math.min(r.right - 150, innerWidth - 160)) + "px";
    }
    menu.classList.toggle("open", open);
    if (caret) caret.setAttribute("aria-expanded", open);
  };
  menu.addEventListener("click", (e) => {
    const b = e.target.closest("[data-order]");
    if (!b) return;
    PR.toggleOrderMenu(false);
    PR.setBiOrder(b.dataset.order);
  });
  document.addEventListener("mousedown", (e) => { if (!e.target.closest("#orderMenu, [data-order-menu]")) PR.toggleOrderMenu(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && menu.classList.contains("open")) PR.toggleOrderMenu(false); });

  function syncBar() {
    const L = PR.viewLabels(), v = PR.readingView();
    PR.$$("#bar [data-view]").forEach((btn) => {
      const k = btn.dataset.view;
      btn.textContent = L[k];
      btn.classList.toggle("on", v === k);
      btn.title = viewTitle(k, L);
    });
    const caret = PR.$("#bar [data-order-menu]");
    if (caret) {
      caret.innerHTML = CARET;
      caret.classList.toggle("on", v === "both");
      caret.title = PR.t("双语顺序");
      caret.setAttribute("aria-label", caret.title);
    }
    if (menu.classList.contains("open")) renderMenu();
  }

  PR.applyReadingLanguage = function () {
    const first = PR.originalFirst();
    document.body.classList.toggle("original-first", first);
    syncBar();
    if (!S.paper) return;
    // 標題裡的英文（.en-title）拆成和譯文同級的一行，才能整體換先後
    PR.$$("#paper .en-title").forEach((en) => {
      const zh = en.parentElement;
      const original = document.createElement(zh.tagName);
      original.className = "en heading-original";
      original.lang = "en";
      const num = zh.querySelector(".num");
      if (num) original.append(num.cloneNode(true));
      original.append(...en.childNodes);
      en.remove();
      zh.after(original);
    });
    PR.$$("#paper .en").forEach((en) => {
      const zh = Array.from(en.parentElement.children).find((n) => n.classList.contains("zh"));
      if (!zh) return;
      zh.classList.add("paired-translation");
      if (first) { if (en.nextElementSibling !== zh) zh.before(en); }
      else if (zh.nextElementSibling !== en) zh.after(en);
    });
    const title = PR.$("#paper .paper-head h1"), meta = S.paper.meta;
    const secondary = PR.$("#paper .title-en");
    if (title && secondary && meta && meta.title_zh && meta.title_en) {
      title.textContent = first ? meta.title_en : meta.title_zh;
      secondary.textContent = first ? meta.title_zh : meta.title_en;
      title.lang = first ? "en" : "";
      secondary.lang = first ? "" : "en";
    }
    const description = PR.$(".reading-language-description");
    if (description && !document.body.classList.contains("en-only") && !((S.paper.translation || {}).en_pages || []).length) {
      const v = PR.readingView();
      description.textContent = v === "both" ? PR.t("正文是原文和译文") : v === "original" ? ((S.paper.meta || {}).format === "epub" ? PR.t("正文顯示原文") : PR.t("正文是英文原文")) : PR.t("正文是译文");
    }
    PR.hideBlockbar && PR.hideBlockbar();
  };
  PR.on("rendered", () => PR.applyReadingLanguage());
  PR.on("block-rendered", () => PR.applyReadingLanguage());
})(window.PR);
