"""An original one-page PDF fixture for the real import/translate/chat flow.

Sends only this fixture to the user's configured model. No personal documents.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from easyread import config
folder = root / "verification"
folder.mkdir(exist_ok=True)
pdf = folder / "PaperDesk-verification.pdf"
writer = PdfWriter()
page = writer.add_blank_page(595, 842)
font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
lines = [
    "PaperDesk: A Small Reading Experiment", "Original verification fixture - not a research publication", "",
    "Abstract", "This document tests a reading workbench. It contains no private data.",
    "The goal is to compare an original passage with a Traditional Chinese translation.", "",
    "1. Method", "Readers inspect the original text, write notes, and ask a focused question.",
    "Two test conditions are defined: reading only, and reading with short explanations.", "",
    "2. Observations", "A pilot example used four tasks. Three were completed without assistance.",
    "One task required an explanation. The completion proportion was 3/4, or 75 percent.",
    "These are illustrative numbers, not measured research results.", "",
    "3. Limitations", "No controlled study was conducted. No causal claim can be made.",
    "Further evaluation would require a larger sample and a reproducible protocol.",
]
content = "BT /F1 12 Tf 50 780 Td 23 TL\n" + "\n".join("(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*" for line in lines) + "\nET"
stream = DecodedStreamObject()
stream.set_data(content.encode("ascii"))
page[NameObject("/Contents")] = writer._add_object(stream)
writer.write(pdf)

base = json.loads(config.SERVER_INFO.read_text(encoding='utf-8'))['url']
token = config.server_token()
def request(path, body=None, raw=False):
    data = body if raw else json.dumps(body).encode() if body is not None else None
    headers = {"X-Token": token, "Content-Type": "application/pdf" if raw else "application/json"}
    with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=120) as response:
        return json.loads(response.read())

token = request("/api/library")["token"]
result = request("/api/import?name=PaperDesk-verification.pdf&translate=1&target=zh-TW", pdf.read_bytes(), True)
pid = result["id"]
print("Imported fixture:", pid, flush=True)
deadline = time.monotonic() + 160
while time.monotonic() < deadline:
    state = request("/api/p/" + pid + "/state")
    job = state.get("job") or {}
    if job.get("state") not in ("queued", "running"):
        print("Translation:", job.get("state"), flush=True)
        if job.get("state") in ("error", "partial"):
            raise RuntimeError(job.get("error") or job)
        paper = state["paper"]
        assert paper["meta"]["target"] == "zh-TW", paper["meta"]
        assert paper.get("blocks"), "Translation produced no blocks"
        print("Title:", paper["meta"].get("title_zh"), flush=True)
        break
    time.sleep(2)
else:
    raise TimeoutError("Translation did not finish")
(folder / "paper-id.txt").write_text(pid, encoding="utf-8")
(folder / "translation.json").write_text(json.dumps(paper, ensure_ascii=False, indent=2), encoding="utf-8")
print("Open:", base + "/read/" + pid, flush=True)
