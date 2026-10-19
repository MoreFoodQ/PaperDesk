/* 右側面板（PDF 原頁 / 筆記 / 問 AI）寬度：拖面板左邊緣調整，按兩下恢復預設，記在本機。
   把手單獨掛在 body 上，面板內容重繪不會把它沖掉。 */
(function (PR) {
  "use strict";
  const body = document.body;
  const root = document.documentElement;
  const KEY = "paperdesk-panel-w";
  const MIN = 320, TEXT_MIN = 420;  // 面板至少 320px，正文至少留 420px
  const clamp = (w) => {
    const dock = document.getElementById("workspaceDock");
    const rail = dock ? dock.getBoundingClientRect().width : 0;
    const outline = innerWidth >= 1360 && body.classList.contains("drawer-open") ? document.getElementById("drawer").getBoundingClientRect().width : 0;
    const available = document.documentElement.clientWidth - rail - outline - TEXT_MIN - 80;
    return Math.round(Math.max(MIN, Math.min(available, w)));
  };
  const setW = (w) => w ? root.style.setProperty("--side-w", clamp(w) + "px") : root.style.removeProperty("--side-w");
  let saved = PR.ls.get(KEY, 0);
  setW(saved);

  /* 寬度變了：正文重排並停在剛才讀的段，原頁按新寬度換合適清晰度的圖 */
  function relayout() {
    const anchor = PR.readingBlock && PR.readingBlock();
    const node = anchor && document.getElementById("b-" + anchor);
    const before = node ? node.getBoundingClientRect().top : 0;
    PR.fitWide(); PR.renderMargin();
    if (node) window.scrollBy(0, node.getBoundingClientRect().top - before);
    if (PR.side === "pages" && PR.refreshPages) PR.refreshPages();
  }

  const grip = PR.el("div", { class: "panel-grip", title: PR.t("拖动调整面板宽度（双击恢复）") });
  body.appendChild(grip);
  grip.addEventListener("mousedown", (e) => {
    e.preventDefault();
    body.classList.add("resizing");
    const move = (ev) => { saved = window.innerWidth - ev.clientX; setW(saved); };
    const up = () => {
      document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up);
      body.classList.remove("resizing");
      saved = clamp(saved);
      PR.ls.set(KEY, saved);
      relayout();
    };
    document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
  });
  grip.addEventListener("dblclick", () => { saved = 0; setW(0); PR.ls.set(KEY, 0); relayout(); });
  /* 窗口變窄時別讓面板把正文擠沒 */
  window.addEventListener("resize", () => { if (saved) setW(saved); });  // 同步改，main.js 裡防抖後的重排就用上新寬度
  new MutationObserver(() => { if (saved) setW(saved); }).observe(body, { attributes: true, attributeFilter: ["class"] });
})(window.PR);
