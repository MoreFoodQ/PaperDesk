# PaperDesk

**繁體中文** | [English](README.en.md)

![Python](https://img.shields.io/badge/Python-3.10%E2%80%933.13-3776AB?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-20%2B-5FA04E?logo=nodedotjs&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-Vanilla-F7DF1E?logo=javascript&logoColor=black)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-663399?logo=css&logoColor=white)

繁體中文論文閱讀工作台，整合 PDF／EPUB 閱讀與原文對照、翻譯、GPT 問答、筆記與文獻庫管理。

PaperDesk 在本機執行，以瀏覽器開啟閱讀介面，預設透過官方 Codex CLI 連線模型。目前提供 Windows x64 安裝版與原始碼版。

[快速開始](#快速開始) · [使用指南](docs/USAGE.md) · [架構](ARCHITECTURE.md) · [參與開發](CONTRIBUTING.md)

## 功能

- **文獻庫管理**：匯入本機 PDF、EPUB 或公開論文網址，搜尋、分類、查看詳情及回收站還原。
- **雙語閱讀**：切換原文、譯文與雙語模式，透過目錄、術語及 PDF 面板對照原頁。
- **圖片文字翻譯**：預設翻譯圖片內文字，可在「設定 → 模型」關閉；圖說與正文照常翻譯，略過的圖片文字可單獨補翻。[行為說明](docs/FIGURE-TRANSLATION.md)
- **GPT 閱讀助手**：使用相關段落與選用頁圖進行翻譯、提問及筆記輔助。
- **筆記與匯出**：文字批註、論文筆記、自動保存，以及 Markdown 與單一 HTML 離線匯出。
- **模型與用量設定**：Codex CLI、Claude Code、本機模型服務及自訂 API；官方帳號額度查詢與本機每日使用門檻。
- **閱讀偏好**：繁體中文／英文介面、字型、字級、行距、快捷鍵及五組深色配色。

## 介面預覽

以下截圖使用合成示範文件與筆記。

### 論文閱讀工作台

雙語段落、論文目錄與 PDF 原頁對照。

![論文閱讀工作台：雙語段落與 PDF 原頁對照](img/reading-workspace.png)

<details>
<summary>文獻庫、筆記與閱讀設定</summary>

### 文獻庫

![文獻庫：分類、搜尋與論文詳情](img/library.png)

### 論文筆記

![論文筆記：閱讀重點與後續問題](img/notes.png)

### 閱讀設定

![閱讀設定：深色配色與語言選項](img/reading-settings.png)

</details>

## 快速開始

### Windows 安裝版

從 [GitHub Releases](https://github.com/MoreFoodQ/PaperDesk/releases) 的 Assets 下載 `PaperDesk-Setup-0.3.1.exe`，安裝後開啟 PaperDesk。安裝版包含 Python 後端與官方 Codex 原生 CLI，不需另外安裝 Python、Node.js 或 npm。

只看 PDF／EPUB 時，匯入選「先不處理」。需要翻譯或 GPT 問答時，到「設定 → 模型」按「登入 ChatGPT／Codex」，在瀏覽器完成官方登入；已有有效的 Codex 登入可直接沿用。

此版本未使用程式碼簽章憑證。可比對 Release 的 `SHA256SUMS.txt`；Windows 可能顯示未知發行者提示。

### 原始碼執行

以下環境需求適用於從原始碼執行或開發專案。

### 環境需求

| 項目 | 需求 |
|---|---|
| 作業系統 | Windows x64 |
| Python | 64 位元 3.10–3.13，建議 3.12 |
| Node.js | 20 以上，包含 npm，建議 24 |
| 模型帳號 | 使用翻譯與問答時，需要有效的 Codex CLI 登入或其他模型服務設定 |

### 安裝

Clone 此 repository，或從 GitHub 的 **Code → Download ZIP** 下載並解壓。開啟專案資料夾，在 PowerShell 執行：

```powershell
.\Setup-PaperDesk.cmd
```

也可以雙擊 `Setup-PaperDesk.cmd`。安裝器會建立專案內的 Python 環境與官方 Codex CLI，使用固定版本及完整性驗證安裝依賴。

### 登入 Codex

```powershell
node .tools/codex/node_modules/@openai/codex/bin/codex.js login
node .tools/codex/node_modules/@openai/codex/bin/codex.js login status
```

已有有效 CLI 登入時可直接沿用。單純閱讀本機 PDF 與寫筆記不需要模型登入。

> 以 ChatGPT 帳號登入 Codex CLI 時，翻譯與問答使用 Codex／代理工作額度。API 金鑰模式依 API 帳戶計費。ChatGPT 網頁登入與 CLI 登入是不同的流程。

### 啟動

```powershell
.\Open-PaperDesk.cmd
```

啟動器會開啟本機服務與瀏覽器。預設網址為 `http://127.0.0.1:8876`；連線埠被使用時，以啟動器開啟的網址為準。後續開啟也使用同一個啟動器。

## 文件格式

支援 PDF，以及無 DRM 的 EPUB 2／3 文字型書籍。EPUB 依章節順序重新分頁，沿用閱讀、翻譯、GPT 問答、筆記與離線 HTML 匯出；原始 EPUB 會保留並可下載。閱讀頁碼不等於原書頁碼，不適合作為原書頁碼引用。

EPUB 不執行書內腳本、不載入外部圖片；CSS 版面會改為統一閱讀排版。固定版面、SVG、MathML、影音、DRM 與混淆字型目前不支援。檔案上限 32 MiB、解壓內容 64 MiB、200 個閱讀頁面；超過上限會停止處理。詳細行為與限制請見 [文件格式](docs/FORMATS.md)。

## 使用方式

1. 匯入 PDF 或 EPUB。只看文件時選「先不處理」；「閱讀原文」會使用模型整理內容，翻譯則可指定範圍。
2. 在文獻庫雙擊論文，進入閱讀工作台。
3. 切換原文、譯文或雙語，開啟 PDF 面板查看原頁。
4. 選取文字建立批註，或在筆記面板記錄整篇筆記。
5. 在 GPT 面板提問，視需要加入相關段落或頁圖。

在「設定 → 模型」新增模型與自訂 API；「設定 → 額度與用量」查詢官方額度或設定本機門檻；「設定 → 閱讀」調整排版、語言與配色。

深色模式預設為石墨青藍，另提供北歐霧藍、暮色薰衣草、森林薄荷與夜幕紫。

更多操作、備份與常見問題，見[使用指南](docs/USAGE.md)。

## 資料與隱私

原始碼版的 PDF、EPUB、筆記、對話及偏好預設儲存在專案的 `data/`；安裝版預設使用 `%USERPROFILE%\PaperDesk`，視窗快取使用 `%APPDATA%\PaperDesk`。重新安裝或移除程式會保留閱讀資料。模型登入由官方 CLI 管理。

- 使用 AI 翻譯、整理或問答時，相關文字、對話及選用頁圖會送至所選模型服務。
- 網址匯入與線上文獻資料補齊會連線外部服務；本機文獻資料補齊預設關閉。
- 文獻庫可以放在本機或自行選擇的同步資料夾；雲端上傳由使用者安裝的同步軟體處理。
- 備份前請等待背景工作完成並關閉服務。分享專案時，請排除個人資料、金鑰與登入憑證。

詳細資料流與安全限制見 [CONNECTIONS.md](CONNECTIONS.md)；漏洞回報方式見 [SECURITY.md](SECURITY.md)。

## 開發

前端位於 `easyread/web/`，Python 後端位於 `easyread/`。內部套件名稱保留為 `easyread`。

安裝完成後，在專案根目錄執行：

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
$files = (Get-ChildItem tests -Filter 'test_*.cjs').FullName
node --test $files
.\.venv\Scripts\python.exe scripts/verify_source.py
```

上述測試使用合成資料，不需要真實模型呼叫。測試覆蓋與驗證紀錄見 [docs/VALIDATION.md](docs/VALIDATION.md)。開發流程見 [CONTRIBUTING.md](CONTRIBUTING.md)。

產生原始碼發布包：

```powershell
.\.venv\Scripts\python.exe scripts/prepare_source_release.py
```

輸出至 `outputs/`，包含來源 ZIP、逐檔 manifest 與 SHA-256。平台支援及已知限制見 [docs/RELEASE.md](docs/RELEASE.md)。

## 授權與致謝

PaperDesk 基於 [EasyRead](https://github.com/Edwardxlai/easyread) 開發，採用 [MIT License](LICENSE)，並保留上游著作權通知。來源版本與主要變更見 [PROVENANCE.md](PROVENANCE.md)。

第三方授權通知位於 [licenses/](licenses/THIRD-PARTY-NOTICES.md)。匯入的論文與其他文件依各自授權使用。
