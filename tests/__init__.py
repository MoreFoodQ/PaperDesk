"""測試統一用中文介面：從原始碼執行時資料目錄就是倉庫，作者在介面上切成英文後，prefs.json 不能影響測試結果。"""
import os

os.environ.setdefault("EASYREAD_LANG", "zh")
