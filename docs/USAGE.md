# PaperDesk · 繁體中文論文閱讀工作臺

PaperDesk 是在自己電腦上執行的論文閱讀工具，提供 PDF 原文對照、繁體翻譯、GPT 問答、筆記與文獻庫。預設透過官方 **Codex CLI** 連線模型。

> **先看這三點**
>
> 1. 第一次安裝需要 Python、Node.js，以及你自己的 Codex CLI 登入。
> 2. ChatGPT 網頁已登入，**不等於 Codex CLI 已登入**。
> 3. 使用 ChatGPT 帳號登入 CLI 時，翻譯與問答使用訂閱提供的 **Codex／代理工作用量**，不是一般 ChatGPT 對話窗的訊息額度。

此版本為 **0.2.0 Windows x64 原始碼版**，沒有 EXE 安裝包。PaperDesk 基於 [EasyRead](https://github.com/Edwardxlai/easyread) 的 MIT 原始碼改作，保留其 PDF、文獻庫與批註核心，重做閱讀工作臺與安全防護。

## 目錄

- [第一次安裝](#第一次安裝)
- [登入模型帳號](#登入模型帳號)
- [每天如何開啟](#每天如何開啟)
- [閱讀與翻譯](#閱讀與翻譯)
- [額度從哪裡來](#額度從哪裡來)
- [資料、連線與隱私](#資料連線與隱私)
- [常見問題](#常見問題)
- [備份、更新與分享](#備份更新與分享)
- [開發與驗證](#開發與驗證)
- [授權與發布範圍](#授權與發布範圍)

## 第一次安裝

### 1. 準備環境

| 專案 | 本版要求 | 推薦、已驗證環境 |
|---|---|---|
| 作業系統 | Windows x64 | Windows x64 |
| Python | 64 位元，3.10–3.13 | Python 3.12 |
| Node.js | 20 以上，包含 npm | Node.js 24 |
| 網路 | 初次下載依賴、登入及使用雲端模型時需要 | 能連線至套件來源與選用的模型服務 |
| 帳號 | 可使用 Codex 的個人帳號，或自行設定的模型服務 | 用自己的 ChatGPT 帳號登入 Codex CLI |

安裝 Python 與 Node.js 後，重新開啟終端機，確認：

```powershell
python --version
node --version
npm.cmd --version
```

Python 安裝器若提供「Add Python to PATH」，請勾選。不要只安裝瀏覽器版 ChatGPT：本程式需要本機 Python 與 Node.js。

### 2. 解壓原始碼

將專案完整解壓至自己可寫入的資料夾，例如 `C:\Projects\PaperDesk`。含空白的路徑已驗證可以使用。

不要直接在 ZIP 內執行，也不要只下載其中一個 `.cmd`。請保留整個專案，包括 `scripts/`、`easyread/`、`LICENSE` 等檔案。

### 3. 執行安裝器

雙擊 `Setup-PaperDesk.cmd`，等它顯示安裝完成。如果失敗，先閱讀視窗最後的錯誤，不要連續重複啟動。

安裝器會：

- 在專案內建立 `.venv/`，安裝固定版本的 Python 套件並驗證 wheel SHA-256。
- 在 `.tools/codex/` 安裝官方 Codex CLI **0.162.1**，使用固定 npm lock 與完整性驗證。
- 檢查 Python 版本、架構、Node.js 與 CLI 原生執行檔。
- 不修改全域 Codex CLI，不執行 npm 安裝 scripts，也不安裝 Electron 建置鏈。

**安裝器不會替你登入模型帳號。** 安裝完成後，繼續下一節。

## 登入模型帳號

在檔案總管開啟 PaperDesk 資料夾，在該資料夾開啟 PowerShell，執行：

```powershell
node .tools/codex/node_modules/@openai/codex/bin/codex.js login
```

依照官方 CLI 開啟的瀏覽器頁面，以自己的 ChatGPT 帳號完成登入。然後檢查：

```powershell
node .tools/codex/node_modules/@openai/codex/bin/codex.js login status
```

確認顯示已透過 ChatGPT 登入，再開啟 PaperDesk。

### 我已經用過 Codex，還需要登入嗎？

若在**同一個 Windows 使用者、同一套 CLI 登入儲存位置**已有有效登入，通常可以直接沿用，先執行 `login status` 確認即可。只在 ChatGPT 網頁登入，並不保證 CLI 有登入。

官方 CLI 自行管理憑證。預設沿用使用者的 `.codex`，若設定 `CODEX_HOME`，則使用該位置。PaperDesk 不會將 OAuth 憑證複製到專案 `data/`，也不會附帶開發者的帳號給其他使用者。

模型許可權與用量依登入帳號決定；安裝成功不代表所有模型都可用。**不要共用他人的 `.codex`、API 金鑰或登入連結。**

### 是否需要 API 金鑰？

使用 ChatGPT 帳號登入 Codex CLI 的預設流程不需要 API 金鑰。若自行改用 API 引擎，或將 CLI 切換成 API 金鑰登入，費用與許可權改由該 API 帳戶決定。

官方說明：[登入方式](https://learn.chatgpt.com/docs/auth)、[用量規則](https://learn.chatgpt.com/docs/pricing)。

## 每天如何開啟

雙擊 **`Open-PaperDesk.cmd`**；也可使用 `start.cmd`。

啟動器會啟動或重用目前的本機服務，並在預設瀏覽器開啟工作臺。它會附上本次服務需要的本機登入資訊。

預設網址為 `http://127.0.0.1:8876`。如果連線埠已被其他程式佔用，服務可能使用另一個本機連線埠，請以啟動器開啟的網址為準。

**請從啟動器開啟，不要只點舊網址。** 新瀏覽器、無痕視窗或服務重啟後，原網址可能缺少有效的本機登入 Cookie，因而拒絕存取。

本機工作臺登入與 Codex 帳號登入是兩件事：前者保護電腦上的文獻庫，後者決定模型是否能用及由誰負擔用量。啟動工作臺不會自動完成 Codex 帳號登入。

所有工作臺分頁關閉、服務閒置且背景工作完成後，啟動器模式可自動結束服務。翻譯進行中請等工作結束，不要強制關閉程式。

## 閱讀與翻譯

1. **匯入論文**：拖曳本機 PDF 或 EPUB、點「匯入論文」，或貼上公開論文網址／編號。
2. **選擇處理方式**：需要翻譯時選翻譯範圍；只想本機看 PDF 時，確認關閉 AI 翻譯／整理。AI 整理原文也會呼叫模型。
3. **進入工作臺**：在文獻庫選取論文檢視詳情，雙擊開啟閱讀頁。
4. **原文對照**：切換原文、譯文或雙語；右側 PDF 面板可檢視原頁。
5. **筆記與問答**：選取文字寫筆記或提問；GPT 問答可使用相關段落、對話及選用頁圖。
6. **選擇模型**：在「設定 → 模型」選擇可用模型、推理程度與速度；預設沿用 CLI 設定，不固定寫死模型名稱。

介面預設繁體中文，也保留英文。中文系統及舊版簡體介面偏好會使用繁體介面。論文翻譯預設為繁體中文；「設定 → 閱讀」可以分別調整介面與翻譯語言，**新設定不會改寫已完成的譯文**。

## 額度從哪裡來

### 模型與外部 API

全新安裝只建立 Codex 的 GPT 卡片；需要 Claude Code 時可自行新增。模型設定依「雲端 API 服務／本機模型服務／自訂位址」分類。服務費用與可用模型以供應商提供的資訊為準。

新增其他服務：在「設定 → 模型 → 新增模型 → 外部 API → 自訂位址」填入服務商提供的 base URL、API 格式、API 金鑰與模型 ID，再按新增。也可讀取服務商的模型清單；預設不推薦或固定外部模型 ID。服務是否免費、支援圖片與可用區域均以服務商為準。

既有 API 模型設定保留端點與相容性。其他供應商可透過自訂 API 加入。介面與閱讀助手採繁體中文及台灣常用學術詞彙，區分研究結果、推論與補充說明，保留原文縮寫與公式。

### 登入、模型與用量的差別

| 專案 | 代表什麼 |
|---|---|
| ChatGPT 帳號登入 | 以哪個人的訂閱與許可權使用官方 CLI |
| GPT 模型 | 實際執行翻譯／問答的模型；選 GPT 不會把 CLI 請求改歸一般聊天額度 |
| Codex／代理工作用量 | 預設 CLI 流程消耗的訂閱用量，會與帳號的其他相關工作共用 |
| 一般 ChatGPT 對話窗 | 不同的使用入口；PaperDesk CLI 不能指定從其聊天訊息上限扣除 |
| API 金鑰 | API 帳戶的用量計費，不是 ChatGPT 訂閱聊天額度 |

模型與任務的用量可能不同，長篇翻譯與簡短提問的消耗也有差異。請以官方帳號當下的限制為準。

官方第三方 [Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt) 也可能使用訂閱，但官方說明仍將這類請求歸於 Codex／ChatGPT Work 用量；目前 PaperDesk 使用的是 CLI 登入流程。

### 檢視剩餘額度

開啟 **「設定 → 額度與用量 → 讀取官方額度」**。

取得方式如下：

1. PaperDesk 啟動專案內的官方 CLI `app-server`。
2. CLI 使用既有帳號登入，向官方服務查詢 `account/rateLimits/read`。
3. PaperDesk 將官方已用百分比換算為剩餘百分比，顯示視窗、重置時間與查詢時間。

在 CLI 已登入的前提下，**不必另外填 API 金鑰或設定額度帳號**。程式不是讀取 ChatGPT 網頁 Cookie，也不是依本機 token 紀錄猜官方餘額。

此查詢不開始模型對話、不消耗重置券；結果快取 60 秒，連續點選不會立即再次查詢。畫面是查詢當時的快照，不保證每個模型此刻都能使用。無法取得或過期時，不會當作剩餘零。

查詢的是帳號共用額度，不是 PaperDesk 專屬額度，也不是每個模型的獨立餘額。API 與其他供應商目前沒有通用餘額查詢，請看供應商的官方帳單或控制檯。

### 本機每日限制

同頁可設定每日呼叫嘗試與服務回報 token 上限，預設 **0＝未啟用限制**。翻譯與問答共用，以臺北時間每日歸帳。

這是避免本程式持續發起新呼叫的限制，不是官方剩餘額度或金額硬上限。已開始的回覆可能超過 token 門檻；不回報 token 的服務不能靠此限制費用。其他 Codex 程式的使用也不受 PaperDesk 的本機限制控制。

## 資料、連線與隱私

### 哪些資料留在本機？

原始碼啟動模式使用專案的 `data/`，儲存文獻庫、PDF、筆記、對話、設定與記錄。不要把它當成發布用原始碼分享。

| 動作 | 是否連外／送出什麼 |
|---|---|
| 本機 PDF 匯入，且不使用 AI／線上補齊 | 在本機處理 PDF；預設不查線上作者／年份 |
| 開啟「線上補齊文獻資料」 | arXiv 編號或 DOI 送至 arXiv／Semantic Scholar；不將整份 PDF 傳給它們 |
| 網址／編號／標題匯入 | 連線公開論文網站與查詢服務取得 PDF／文獻資料 |
| AI 翻譯、AI 整理、GPT 問答 | 相關論文文字、對話及選用頁圖傳送至選定模型服務 |
| 手動查詢額度 | 官方 CLI 查詢帳號額度，不傳論文、不開始模型對話 |
| 第一次安裝 | 從 PyPI 與官方 npm registry 下載依賴 |

**本機執行不等於完全離線。** 若沿用的 Codex 設定有自訂 provider／代理，模型連線也會沿用相關設定；「使用官方 CLI」不代表忽略使用者設定。詳細目的地與取捨見 [CONNECTIONS.md](../CONNECTIONS.md)。

### 安全保護與限制

- HTTP 僅繫結本機位址；讀取與寫入要求本機登入，並驗證 Host／Origin。
- 網址下載拒絕 `file://`、本機／內網位址及轉址到非公開 IP；本機 PDF 請使用檔案匯入。
- 已補強模型／共享資料的 HTML escaping、匯出路徑與跨來源金鑰保護。
- Codex 子程式使用唯讀限制，停用非必要 shell、hooks、搜尋與 MCP 等工具；瀏覽器不能指定 CLI 執行檔或注入額外引數。必要安全設定失敗時停止，不放寬後重試。
- PDF 放在獨立程式並限制資源、逾時與並行數，降低解析崩潰對主程式的影響。
- 選用 API 金鑰及本機服務通行憑證使用 Windows DPAPI 保護；繫結 Windows 使用者，換帳號／電腦時需要重新登入或填入相關金鑰。
- PaperDesk 目前沒有自動下載更新服務。

這些防護**不是完整 OS 檔案沙箱或安全認證**，不能抵禦已接管同一 Windows 帳號的惡意程式。不要分享帶本機登入資訊的網址。

## 常見問題

| 狀況 | 建議處理 |
|---|---|
| 點 `127.0.0.1:8876` 開不起來／拒絕存取 | 雙擊 `Open-PaperDesk.cmd`，使用它開啟的瀏覽器與網址；新瀏覽器需要本機登入 |
| ChatGPT 網頁已登入，模型卻不能用 | 在專案資料夾執行上面的 CLI `login status`；未登入則執行 `login` |
| 換 Windows 帳號／電腦後不能登入 | 用自己的帳號重新完成 CLI 登入；不要複製別人的憑證 |
| 剩餘額度顯示無法取得 | 先確認 CLI 登入及網路，等 60 秒再查；不要解讀為剩餘零 |
| 模型達到用量限制 | 等官方視窗重置，或選帳號允許的其他模型；不保證換模型有獨立額度 |
| 找不到 Python 或 Node.js | 安裝符合版本與架構的環境，重開終端機，執行版本檢查 |
| `py` 找不到 Python | 安裝器會嘗試 PATH 的 `python`；若仍失敗，確認 `python --version` 正常且不是商店捷徑 |
| 顯示 CLI 未完整安裝／版本不符 | 重新執行 `Setup-PaperDesk.cmd`；不要任意替換 `.tools/` 的套件 |
| 服務連不上模型 | 檢查所選服務、網路及既有代理設定；不要關閉憑證校驗或繞過安全設定 |
| 作者／年份沒填完整 | 本機文獻補齊預設關閉，可手動補充或明確開啟線上補齊 |
| 介面仍顯示舊文字 | 重新整理；必要時關閉閒置工作臺，再從啟動器重開。已完成譯文不會自動改寫 |

若安裝器視窗一閃即逝，可在專案資料夾的 PowerShell 執行，以保留錯誤訊息：

```powershell
cmd /c Setup-PaperDesk.cmd
```

回報問題時提供操作步驟、版本及錯誤訊息，先移除金鑰、登入 URL、帳號資訊與不宜分享的論文內容。不要直接貼整份 `data/` 或 `.codex`。

## 備份、更新與分享

備份前等背景工作完成並關閉服務。自己的 `data/` 含個人文獻與筆記，可備份供自己恢復，**請勿將個人資料納入公開發布包**。API 加密資料不能保證在不同 Windows 帳號還原；遷移時應重新設定登入及金鑰。

更新前備份個人資料，取得新版本原始碼後重新執行 Setup。

分享專案時，提供原始碼或來源發布 ZIP，由使用者各自安裝與登入。請排除：

- `data/`、`.codex/`、`.aws/`、`.claude/` 或 `.env`。
- `.venv/`、`.tools/`、`node_modules/`。
- 個人 log、測試證據、API 金鑰、OAuth 憑證與帶登入資訊的網址。

專案有 `.gitignore`，但它不會清除已提交的秘密。發布前執行來源檢查；若檔案曾進入 Git 歷史，須另行處理，不能只從最新版本刪除。

## 開發與驗證

在已安裝的專案根目錄執行：

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'
$files = (Get-ChildItem tests -Filter 'test_*.cjs').FullName
node --test $files
.venv/Scripts/python.exe scripts/verify_source.py
.venv/Scripts/python.exe scripts/prepare_source_release.py --check-only
```

單元測試與 `verify_source.py` 使用合成資料，不需要模型呼叫。`verify_source.py` 在獨立資料目錄驗證登入、PDF 匯入／圖片／閱讀／離線匯出，不使用開發者的文獻庫。

瀏覽器驗證：`scripts/verify_browser.cjs` 需要另外準備 Playwright 與 Chromium，可用 `PAPERDESK_PLAYWRIGHT`、`PAPERDESK_CHROME` 指定；不屬一般使用者安裝需求。不要把 `tests/e2e.cjs` 當作一般 Node 單元測試一起執行。

最新本機驗證為 **344 個 Python、109 個 JavaScript 單元測試透過**，並檢查合成介面的設定、匯入與閱讀面板。最新來源包在乾淨 Python 3.12 環境也通過 344 個 Python 與 109 個 JavaScript 測試。GitHub Actions 尚未在 GitHub 實際執行；本機透過不等於遠端 CI 已透過。

產生發布包：

```powershell
.venv/Scripts/python.exe scripts/prepare_source_release.py
```

輸出於 `outputs/`：

- `paperdesk-0.2.0-source.zip`：白名單來源包。
- `RELEASE-MANIFEST.json`：逐檔 SHA-256。
- `SHA256SUMS.txt`：ZIP 的 SHA-256。

來源工具會檢查私密路徑、可能的憑證模式與依賴來源完整性，**不會自動推送 GitHub**；模式檢查也不等於能識別所有秘密。

前端位於 `easyread/web/`，繁體字典位於 `easyread/web/i18n/zh-TW.json`。執行時不需要 OpenCC；開發時重新產生詞典才需要另外安裝 `opencc-python-reimplemented`。內部模組名 `easyread` 保留以維持相容，產品名稱為 PaperDesk。

## 授權與發布範圍

上游：[Edwardxlai/easyread](https://github.com/Edwardxlai/easyread)，基準 commit `1fef04f5398711d351c16a8140541713fec1def5`。MIT 全文見 [LICENSE](../LICENSE)，第三方通知見 `licenses/`。

MIT 允許修改與再發布，須保留原著作權與授權通知。第三方依賴及匯入的論文依各自權利與授權使用。

本次 freeze 僅涵蓋 Windows x64 原始碼。未製作或簽章 EXE，也未發布至 GitHub。一般 Setup 不安裝 Electron 建置鏈；2026-10-11 的該建置鏈盤點仍有 8 項 moderate 警示，屬未來 EXE 發行前的處理範圍，不宣稱已修補。

Freeze 表示已完成所列發布門檻與記錄取捨，不保證零 bug。後續以可重現錯誤、重大漏洞與必要相容性修正為主。

詳細紀錄：

- [Freeze 範圍與取捨](RELEASE.md)
- [連線與資料流](../CONNECTIONS.md)

雲端文獻庫設定使用「雲端空間」用詞。PaperDesk 只偵測 OneDrive、Dropbox、iCloud 的既有本機同步資料夾，也允許自行選擇其他同步資料夾；不替你登入雲端帳號或上傳檔案。選擇同步資料夾後，檔案由該服務的同步軟體上傳。EasyRead 子資料夾名稱保留為相容路徑。

深色模式預設使用「石墨青藍」。到「設定 → 閱讀 → 深色配色」可切換北歐霧藍、暮色薰衣草、森林薄荷與夜幕紫；按「儲存」後，文獻庫與閱讀頁共用並保存至本機偏好。取消或按 Esc 會還原預覽。配色只影響深色模式，淺色與跟隨系統選項保留。

完整功能收尾結果、低成本模型實測用量與覆蓋限制：[全功能驗證](VALIDATION.md)。

## EPUB 閱讀

0.2.0 起支援無 DRM 的 EPUB 2／3 文字型書籍，從本機選取或拖曳匯入。網址／DOI／arXiv 匯入仍以 PDF 為主。EPUB 的章節、段落、基本清單與表格文字及內嵌 JPEG／PNG／GIF／WebP 圖片會轉成統一閱讀頁面；動畫僅保留第一張影格。

原始檔存為 `source.epub`，下載時回傳原始位元組；`source.pdf` 是本機產生的閱讀版 PDF。頁碼與版面不是原書排版，閱讀版 PDF 是頁圖組成；App 的文字上下文另存於 `extract/`。原書樣式、連結互動及精細表格排版不會保留。筆記、翻譯和匯出沿用既有資料結構。

支援範圍、字型要求與安全上限請見 [文件格式](FORMATS.md)。EPUB 本身不需要新套件或新模型設定；開啟模型處理後仍消耗原來的 CLI／API 額度。
