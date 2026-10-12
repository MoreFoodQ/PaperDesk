"""Generate the checked-in Traditional Chinese UI dictionary; development only."""
import json
from pathlib import Path
from opencc import OpenCC

root = Path(__file__).resolve().parents[1]
folder = root / "easyread" / "web" / "i18n"
english = json.loads((folder / "en.json").read_text(encoding="utf-8"))
converter = OpenCC("s2twp")
dictionary = {key: converter.convert(key) for key in english}
replacements = {"文獻庫": "文獻庫", "文件夾": "資料夾", "文件": "檔案", "信息": "資訊",
                "視頻": "影片", "鼠標": "滑鼠", "界面": "介面", "服務器": "伺服器", "令牌": "權杖"}
for key, value in dictionary.items():
    for source, replacement in replacements.items():
        value = value.replace(source, replacement)
    dictionary[key] = value
dictionary.update({
    "把英文论文，读成舒服的中文": "讓每篇論文，成為你的知識。",
    "问 AI": "問 GPT", "选一个翻译引擎": "連接 GPT 閱讀助手",
    "导入 PDF，后台逐页翻译；公式、表格照原文排好，随时对照原文，边读边划线、记笔记、提问。":
        "匯入 PDF，以繁體中文研讀。原文、公式、筆記與 GPT 問答，都在同一個工作台。",
    "没有现成的论文？试试": "想先試讀公開論文？",
    "中文": "簡體中文", "宋体": "明體", "黑体": "黑體", "星标": "收藏",
    "自定义地址": "自訂位址",
})
# Keep reviewed Taiwan terminology and product copy; generate only missing entries.
existing = folder / 'zh-TW.json'
if existing.exists():
    dictionary.update(json.loads(existing.read_text(encoding='utf-8')))
(folder / "zh-TW.json").write_text(json.dumps(dictionary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Generated {len(dictionary)} Traditional Chinese UI entries")
