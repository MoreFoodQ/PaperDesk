/* 頁面開著就連著一條 WebSocket，讓服務知道還有人在用。
   啟動器使用 --exit-on-close 時，所有頁面離線且背景工作完成後，服務會自動結束（見 easyread/presence.py）。 */
(function () {
  "use strict";
  if (location.protocol !== "http:" || typeof WebSocket === "undefined") return;
  let retries = 0;
  function connect() {
    let ws;
    try { ws = new WebSocket("ws://" + location.host + "/api/presence"); } catch (e) { return; }
    ws.onopen = () => { retries = 0; };
    ws.onclose = () => { retries += 1; setTimeout(connect, Math.min(30000, 1000 * retries)); };  // 斷了就重連（服務重新啟動過）
  }
  connect();
})();
