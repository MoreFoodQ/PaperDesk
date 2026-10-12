# PaperDesk 第三方通知

PaperDesk 基於 EasyRead 改作，原始著作權是 Copyright (c) 2026 LiangXiLin。
完整上游 MIT 授權保留在根目錄 LICENSE 及 EasyRead-MIT.txt。

KaTeX 0.16.22 的公式渲染、字型與相關檔案：見 KaTeX-MIT.txt。
其他子目錄是從目前測試環境安裝的 Python 套件收集的原始授權通知；
版本固定在 requirements-lock.txt。pypdfium2 及其 PDFium 元件通知一起保留。

certifi 所附 CA 憑證資料採 MPL 2.0。相應原始碼可從
https://github.com/certifi/python-certifi 取得；使用 requirements-lock.txt 所列版本的對應 tag。
MPL 全文：https://www.mozilla.org/en-US/MPL/2.0/

專案內安裝的官方 Codex CLI 採 Apache 2.0，安裝於 .tools/codex；
登入憑證仍由官方 CLI 管理。原始碼：https://github.com/openai/codex 。
CLI 的授權隨 npm 套件提供，不將使用者登入憑證包含在原始碼或發行包。

這份本機改版沒有攜帶上游示範論文作為預設文獻。
verification 中的文件是原創功能測試文件，並非研究出版品。
若另外發布原倉庫 docs/demo，需維持其論文內容的 CC BY 4.0 歸屬與修改註記。

目前交付的是本機原始碼與啟動入口。若未來製作 Electron 安裝包，
還需依實際打包的 Electron、Node、Python runtime 與 npm 依賴補齊 LICENSE/NOTICE，
並重新核對當時的依賴安全資料；本資料夾不代表已完成安裝包的全部授權盤點。

深色配色參考 Nord（https://www.nordtheme.com/）、Catppuccin Mocha（https://catppuccin.com/palette/）及 Dracula（https://draculatheme.com/spec）。PaperDesk 自行配置介面語意與次要文字對比；未加入這些主題的程式、字型或圖像。石墨青藍為本專案配色，森林薄荷延續既有 PaperDesk 配色。
