/* 介面語言。程式碼裡只寫中文：PR.t("已匯入 {n} 篇", { n })；中文原文就是鍵，英文在 web/i18n/en.json。
   後端回傳頁面時按系統語言（或設定裡選的）寫好 <html lang>，英文時把詞典放入 #pr-i18n。 */
window.PR = window.PR || {};
(function (PR) {
  "use strict";

  let dict = {};
  try { dict = JSON.parse((document.getElementById("pr-i18n") || {}).textContent || "{}"); } catch (e) { dict = {}; }
  PR.lang = ["en", "zh-TW"].includes(document.documentElement.lang) ? document.documentElement.lang : "zh";
  PR.langChoice = document.documentElement.dataset.langChoice || "auto";  // 設定裡選的：auto 跟隨系統
  PR.target = document.documentElement.dataset.target || "zh";  // 譯文語言（論文翻成什麼），名字表在 util.js

  const fill = (s, vars) => vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m)) : s;
  PR.t = (zh, vars) => fill(PR.lang !== "zh" ? dict[zh] || zh : zh, vars);

  /* 寫死在 HTML 裡的中文：按原文整句對照替換，HTML 不用改 */
  const CJK = /[一-鿿]/;
  const ATTRS = ["placeholder", "title", "aria-label", "alt"];
  PR.translateDom = function (root) {
    if (PR.lang === "zh") return;
    root = root || document.body;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const raw = n.nodeValue, key = raw.trim();
      if (key && CJK.test(key) && dict[key]) n.nodeValue = raw.replace(key, dict[key]);
    }
    root.querySelectorAll("*").forEach((el) => ATTRS.forEach((a) => {
      const v = el.getAttribute(a);
      if (v && CJK.test(v) && dict[v.trim()]) el.setAttribute(a, dict[v.trim()]);
    }));
  };
  if (PR.lang !== "zh") {
    if (dict[document.title]) document.title = dict[document.title];
    if (document.body) PR.translateDom(document.body);
    else document.addEventListener("DOMContentLoaded", () => PR.translateDom(document.body));
  }
})(window.PR);
