"""Build the Python service used by the packaged Electron application."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "backend"
WORK = ROOT / "build" / "pyinstaller"
REQUIRED = ("easyread", "pypdfium2", "pypdfium2_raw", "pdfplumber", "PIL", "pypdf", "truststore", "certifi")


def python_with_pyinstaller() -> list[str]:
    candidates: list[str] = []
    configured = os.environ.get("PYTHON")
    if configured:
        candidates.append(configured)
    venv = ROOT / (".venv\\Scripts\\python.exe" if os.name == "nt" else ".venv/bin/python")
    if venv.exists():
        candidates.append(str(venv))
    candidates.append(sys.executable)
    for candidate in candidates:
        probe = subprocess.run([candidate, "-c", "import PyInstaller"], cwd=ROOT, capture_output=True)
        if probe.returncode == 0:
            return [candidate]
    raise SystemExit("未找到 PyInstaller。请运行：python -m pip install pyinstaller")


def check_dependencies(python: list[str]) -> None:
    for module in REQUIRED:
        probe = subprocess.run(python + ["-c", f"import {module}"], cwd=ROOT, capture_output=True)
        if probe.returncode:
            raise SystemExit(f"无法加载后端依赖 {module}。请使用打包的 Python 安装：python -m pip install pyinstaller .")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制檯預設不是 UTF-8，下面的中文提示會讓指令碼崩掉
    python = python_with_pyinstaller()
    check_dependencies(python)  # 驗證透過後再清理舊產物
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if not OUT.resolve().is_relative_to(ROOT.resolve()) or not WORK.resolve().is_relative_to(ROOT.resolve()):
        raise SystemExit('Build paths leave the project.')
    cmd = python + ["-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noupx",
                    "--name", "easyread-backend", "--distpath", str(OUT),
                    "--workpath", str(WORK), "--specpath", str(WORK),
                    "--paths", str(ROOT),
                    *[arg for module in REQUIRED for arg in ("--collect-all", module)],
                    str(ROOT / "scripts" / "backend_entry.py")]
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"后端已生成：{OUT / 'easyread-backend' / ('easyread-backend.exe' if os.name == 'nt' else 'easyread-backend')}")


if __name__ == "__main__":
    main()
