/* PaperDesk: a reading workbench over the original document operations. */
(function (PR) {
  "use strict";
  const text = (tw, en) => PR.lang === "en" ? en : tw;
  const E = PR.esc;

  PR.renderWorkspace = function () {
    const L = PR.lib, box = document.querySelector("#workspaceOverview");
    if (!L || !box) return;
    const reading = L.items.filter(i => i.status === "reading");
    const marks = L.items.reduce((n, i) => n + (i.notes || 0) + (i.highlights || 0), 0);
    const running = L.items.filter(i => i.job && ["queued", "running"].includes(i.job.state)).length;
    box.querySelector("[data-total]").textContent = L.items.length;
    box.querySelector("[data-reading]").textContent = reading.length;
    box.querySelector("[data-marks]").textContent = marks;
    box.querySelector("[data-jobs]").textContent = running;
    const next = reading.sort((a, b) => String(b.last_opened || "").localeCompare(String(a.last_opened || "")))[0];
    const resume = document.querySelector("#workspaceResume");
    resume.hidden = !next;
    if (next) {
      resume.querySelector("strong").textContent = PR.titles(next).main;
      resume.querySelector("small").textContent = text("上次閱讀進度 ", "Reading progress ") + Math.round((next.progress || 0) * 100) + "%"; // i18n-ok bilingual
      resume.onclick = () => L.openReader(next.id);
    }
    const empty = document.querySelector("#workspaceHint");
    if (empty) empty.hidden = L.items.length > 0;
  };

  PR.initWorkspaceReader = function () {
    if (!document.body.classList.contains("pd-reader") || PR.store.mode !== "server") return;
    const meta = PR.state.paper.meta || {};
    const dock = document.querySelector("#workspaceDock");
    if (dock) {
      dock.innerHTML = '<a href="/" class="pd-dock-home">' + PR.logo() + '<span>PaperDesk</span></a>' +
        '<span class="pd-dock-label">' + text("研讀工具", "READING TOOLS") + '</span>' + // i18n-ok bilingual
        [["drawer", "book", text("論文目錄", "Outline")], ["pages", "page", text("原文 PDF", "Source PDF")], // i18n-ok bilingual
         ["chat", "sparkle", text("GPT 閱讀助手", "Ask GPT")], ["notes", "note", text("我的筆記", "Notes")]] // i18n-ok bilingual
          .map(([act, icon, label]) => '<button data-pd-act="' + act + '">' + PR.icon(icon) + '<span>' + E(label) + '</span></button>').join("") +
        '<div class="pd-dock-foot">' + text("繁體中文研讀", "Read with clarity") + '<br><small>' + E(meta.authors ? text("筆記儲存於本機", "Notes saved locally") : "PaperDesk") + '</small></div>'; // i18n-ok bilingual
      dock.querySelectorAll("button").forEach(button => {
        button.title = button.textContent.trim();
        button.setAttribute("aria-label", button.title);
      });
      dock.onclick = (event) => {
        const button = event.target.closest("[data-pd-act]");
        if (!button) return;
        const actions = { drawer: PR.toggleDrawer, pages: PR.togglePages, chat: PR.toggleChat, notes: PR.toggleNotesPanel };
        if (actions[button.dataset.pdAct]) actions[button.dataset.pdAct]();
      };
    }
    if (innerWidth >= 1360) {
      PR.toggleDrawer(true);
      if (PR.canChat()) PR.toggleChat(true);
    }
  };

  document.addEventListener("DOMContentLoaded", () => {
    const importButton = document.querySelector("#workspaceImport");
    if (importButton) importButton.onclick = () => PR.openImport();
    const themeButton = document.querySelector("#workspaceTheme");
    if (themeButton) themeButton.onclick = () => {
      const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      PR.applyTheme(theme); PR.savePrefs("reader", { theme });
    };
  });
})(window.PR);
