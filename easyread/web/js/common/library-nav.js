/* 記錄每次從文獻庫進入閱讀頁的位置；每個連結有獨立記錄，回傳連結只帶記錄 ID。 */
(function (PR) {
  "use strict";
  const KEY = "paperdesk-library-navigation", PARAM = "library", HISTORY_KEY = "easyreadLibraryReturn";
  const idOk = (id) => typeof id === "string" && /^[a-zA-Z0-9_-]{1,128}$/.test(id);
  const textOk = (s, max) => typeof s === "string" && s.length <= max;
  const valid = (s) => s && s.version === 1 && idOk(s.paper) && textOk(s.view, 40) &&
    (s.tag === null || textOk(s.tag, 128)) && textOk(s.q, 2000) && textOk(s.sort, 20) &&
    textOk(s.label, 128) && Number.isFinite(s.scroll) && s.scroll >= 0 &&
    (s.offset === null || Number.isFinite(s.offset));
  function records() {
    try {
      const data = JSON.parse(localStorage.getItem(KEY) || "{}");
      return data && typeof data === "object" && !Array.isArray(data) ? data : {};
    } catch (_) { return {}; }
  }
  function read(token) {
    if (!idOk(token)) return null;
    const all = records(), value = Object.prototype.hasOwnProperty.call(all, token) ? all[token] : null;
    return valid(value) ? value : null;
  }
  function rememberHistory(token, url) {
    try { history.replaceState({ ...(history.state || {}), [HISTORY_KEY]: token }, "", url); } catch (_) { /* 無法記錄時仍可正常打開論文。 */ }
  }
  PR.libraryNav = {
    readerUrl(paper, state) {
      const url = "/read/" + encodeURIComponent(paper);
      const value = { ...state, paper, version: 1 };
      if (!valid(value)) return url;
      const token = PR.uid("l"), all = records();
      all[token] = value;
      // 每條記錄保留自己的分類，多個閱讀標籤頁不會互相覆蓋。
      const keys = Object.keys(all);
      keys.slice(0, Math.max(0, keys.length - 100)).forEach((key) => delete all[key]);
      // 瀏覽器新標籤頁不一定複製會話儲存，用同源儲存讓新標籤頁也能找到自己的來源。
      try { localStorage.setItem(KEY, JSON.stringify(all)); }
      catch (_) { return url; }
      rememberHistory(token, location.href);
      return url + "?" + PARAM + "=" + encodeURIComponent(token);
    },
    restore() {
      const token = (history.state || {})[HISTORY_KEY] || new URLSearchParams(location.search).get(PARAM);
      const value = read(token);
      if (value && location.pathname === "/") {
        const url = new URL(location.href);
        url.searchParams.delete(PARAM);
        rememberHistory(token, url.pathname + url.search + url.hash);
      }
      return value;
    },
    readerBack(paper) {
      const token = new URLSearchParams(location.search).get(PARAM), value = read(token);
      if (!value || value.paper !== paper) return;
      const back = PR.$("#backBtn");
      if (!back) return;
      back.href = "/?" + PARAM + "=" + encodeURIComponent(token);
      back.title = PR.t("返回“{name}”", { name: value.tag || value.label || PR.t("文献库") });
    },
  };
})(window.PR);
