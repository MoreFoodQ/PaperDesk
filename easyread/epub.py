"""Bounded, offline EPUB 2/3 import into the existing page-based reader.

No archive members are extracted, and no publisher HTML/CSS is served.
Call inspect/prepare through pdf_isolation, never in the HTTP process.
"""
from __future__ import annotations

import io
import json
import os
import posixpath
import re
import stat
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from .i18n import tr

MAX_ARCHIVE = 32 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_MEMBER = 8 * 1024 * 1024
MAX_TEXT = 500_000
MAX_PAGES = 200


def _fail(message):
    raise ValueError(message)


def _xml(data):
    if b'\x00' in data or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        _fail(tr('EPUB 的 XML 宣告不受支援。'))
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        _fail(tr('EPUB 的結構資料無法解析。'))


def _local(base, href):
    url = urlsplit(href)
    if url.scheme or url.netloc:
        _fail(tr('EPUB 章節必須包含在檔案內。'))
    decoded = unquote(url.path)
    if decoded.startswith('/') or '\\' in decoded or '\x00' in decoded:
        _fail(tr('EPUB 含有不安全的檔案路徑。'))
    name = posixpath.normpath(posixpath.join(posixpath.dirname(base), decoded))
    if name in ('', '.', '..') or name.startswith('../'):
        _fail(tr('EPUB 含有不安全的檔案路徑。'))
    return name


class _Body(HTMLParser):
    boundaries = {'p', 'div', 'section', 'article', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'blockquote', 'pre', 'figcaption'}
    ignored = {'script', 'style', 'iframe', 'object', 'embed', 'template'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.body = False
        self.hidden = []
        self.parts = []
        self.blocks = []
        self.heading = False
        self.count = 0

    def flush(self):
        text = re.sub(r'\s+', ' ', ''.join(self.parts)).strip()
        self.parts = []
        if text:
            self.blocks.append(('heading' if self.heading else 'text', text))

    def handle_starttag(self, tag, attrs):
        if tag == 'body':
            self.body = True
        if not self.body:
            return
        if self.hidden:
            if tag in self.ignored:
                self.hidden.append(tag)
            return
        if tag in self.ignored:
            self.hidden.append(tag)
            return
        if tag in {'svg', 'math', 'audio', 'video'}:
            _fail(tr('此 EPUB 含有目前不支援的 SVG、MathML 或影音內容。'))
        if tag in self.boundaries:
            self.flush()
            self.heading = tag.startswith('h') and tag[1:].isdigit()
        if tag == 'br':
            self.parts.append(' ')
        if tag in {'td', 'th'}:
            self.parts.append(' | ')
        if tag == 'img':
            self.flush()
            attrs = dict(attrs)
            self.blocks.append(('image', attrs.get('src', ''), attrs.get('alt', '')))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag in self.boundaries or tag == 'body':
            self.flush()
            self.heading = False
        if tag == 'body':
            self.body = False

    def handle_data(self, data):
        if self.body and not self.hidden:
            self.count += len(data)
            if self.count > MAX_TEXT:
                _fail(tr('EPUB 超過文字處理上限。'))
            self.parts.append(data)


def _read(root):
    path = root / 'source.epub'
    if path.stat().st_size > MAX_ARCHIVE:
        _fail(tr('EPUB 超過 32 MiB 檔案上限。'))
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        _fail(tr('不是有效的 EPUB 檔案。'))
    with archive as z:
        entries = z.infolist()
        names = set()
        total = 0
        if len(entries) > 2048:
            _fail(tr('EPUB 超過壓縮檔安全上限。'))
        for item in entries:
            name = item.orig_filename  # Validate before ZipInfo normalizes Windows separators/NUL.
            if (name.startswith('/') or ':' in name or '\\' in name or '\x00' in name or
                    any(p in ('.', '..') for p in name.split('/')) or name in names or
                    stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1):
                _fail(tr('EPUB 含有不安全的檔案路徑或加密內容。'))
            names.add(name)
            total += item.file_size
            if item.file_size > MAX_MEMBER or total > MAX_TOTAL or item.file_size > max(1, item.compress_size) * 1000:
                _fail(tr('EPUB 超過壓縮檔安全上限。'))
        if 'META-INF/encryption.xml' in names:
            _fail(tr('目前不支援 DRM 或加密的 EPUB（包含混淆字型）。'))
        def read(name):
            if name not in names or name.endswith('/'):
                _fail(tr('EPUB 缺少必要的內容檔案。'))
            try:
                return z.read(name)
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
                _fail(tr('EPUB 的壓縮內容無法解析。'))
        if read('mimetype') != b'application/epub+zip':
            _fail(tr('不是有效的 EPUB 檔案。'))
        container = _xml(read('META-INF/container.xml'))
        rootfiles = [e.attrib.get('full-path', '') for e in container.iter() if e.tag.endswith('}rootfile')]
        if not rootfiles:
            _fail(tr('EPUB 缺少套件描述檔。'))
        opf_name = _local('', rootfiles[0])
        opf = _xml(read(opf_name))
        if opf.attrib.get('version') not in ('2.0', '3.0'):
            _fail(tr('目前僅支援 EPUB 2 與 EPUB 3。'))
        values = {}
        for e in opf.iter():
            tag = e.tag.rsplit('}', 1)[-1]
            if tag in {'title', 'creator', 'language'}:
                values.setdefault(tag, []).append(''.join(e.itertext()).strip())
            if tag == 'meta' and e.attrib.get('property') == 'rendition:layout' and (e.text or '').strip() == 'pre-paginated':
                _fail(tr('目前不支援固定版面的 EPUB，請改用 PDF。'))
        manifest = {}
        for e in opf.iter():
            if e.tag.rsplit('}', 1)[-1] == 'item':
                ident = e.attrib.get('id')
                if not ident or ident in manifest:
                    _fail(tr('EPUB 的內容清單無效。'))
                manifest[ident] = e.attrib
        spine = [e.attrib for e in opf.iter() if e.tag.rsplit('}', 1)[-1] == 'itemref' and e.attrib.get('linear', 'yes') != 'no']
        if not spine or len(spine) > 512:
            _fail(tr('EPUB 的章節順序無效或超過上限。'))
        chapters, text_size, image_size = [], 0, 0
        for ref in spine:
            item = manifest.get(ref.get('idref'), {})
            if item.get('media-type') != 'application/xhtml+xml':
                _fail(tr('目前僅支援 XHTML 章節的 EPUB。'))
            if 'rendition:layout-pre-paginated' in ref.get('properties', '').split():
                _fail(tr('目前不支援固定版面的 EPUB，請改用 PDF。'))
            name = _local(opf_name, item.get('href', ''))
            data = read(name)
            if b'<!ENTITY' in data.upper():
                _fail(tr('EPUB 的 XML 宣告不受支援。'))
            try:
                html = data.decode('utf-8-sig')
            except UnicodeDecodeError:
                _fail(tr('EPUB 章節必須使用 UTF-8 編碼。'))
            parser = _Body()
            parser.feed(html)
            parser.flush()
            text_size += parser.count
            if text_size > MAX_TEXT:
                _fail(tr('EPUB 超過文字處理上限。'))
            blocks = []
            for block in parser.blocks:
                if block[0] != 'image':
                    blocks.append(block)
                    continue
                src, alt = block[1:]
                if urlsplit(src).scheme or urlsplit(src).netloc:
                    blocks.append(('text', tr('［外部圖片未載入］') + (' ' + alt if alt else '')))
                    continue
                raw = read(_local(name, src))
                image_size += len(raw)
                if image_size > 32 * 1024 * 1024:
                    _fail(tr('EPUB 圖片超過處理上限。'))
                from PIL import Image
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format not in {'JPEG', 'PNG', 'GIF', 'WEBP'} or image.width * image.height > 16_000_000:
                        _fail(tr('EPUB 含有不支援或過大的圖片。'))
                    image.verify()
                blocks.append(('image', raw, alt))
            chapters.append(blocks)
        if not any(chapters):
            _fail(tr('EPUB 沒有可閱讀的內容。'))
        metadata = {'title_en': (values.get('title') or [''])[0], 'authors': ', '.join(values.get('creator', [])),
                    'source_language': (values.get('language') or [''])[0], 'format': 'epub', 'pagination': 'paperdesk-epub-v1'}
        return metadata, chapters


def inspect(root):
    return _read(Path(root))[0]


def _font(size, bold=False, cjk=False):
    from PIL import ImageFont
    candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / ('msjhbd.ttc' if bold else 'msjh.ttc'),
                  Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'), Path('/System/Library/Fonts/PingFang.ttc')]
    if not cjk:
        candidates += [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    _fail(tr('找不到 EPUB 閱讀字型；請安裝微軟正黑體或 Noto Sans CJK。'))


def prepare(root):
    """Generate page images, plain text, character anchors and a reference PDF."""
    from PIL import Image, ImageDraw
    from pypdf import PdfWriter
    root = Path(root)
    _, chapters = _read(root)
    cjk = any(re.search(r'[\u3000-\u9fff]', b[1]) for ch in chapters for b in ch if b[0] != 'image')
    normal, heading = _font(30, cjk=cjk), _font(38, True, cjk=cjk)
    (root / 'pages').mkdir(exist_ok=True)
    (root / 'extract').mkdir(exist_ok=True)
    pages = []
    writer = PdfWriter()
    with tempfile.TemporaryDirectory(prefix='.epub-render-', dir=root) as temp:
        image = None
        def new_page():
            nonlocal image, draw, y, text, chars
            image = Image.new('RGB', (1200, 1600), 'white')
            draw = ImageDraw.Draw(image)
            y, text, chars = 90, [], []
        def finish():
            nonlocal image
            if not text and y == 90:
                image.close()
                image = None
                return
            if len(pages) >= MAX_PAGES:
                _fail(tr('EPUB 超過 200 個閱讀頁面上限。'))
            n = len(pages) + 1
            name = f'page-{n:03d}'
            draw.text((90, 1530), str(n), fill='#777777', font=normal)
            page_file = Path(temp) / f'{name}.webp'
            image.save(page_file, 'WEBP', quality=84)
            os.replace(page_file, root / 'pages' / page_file.name)
            (root / 'extract' / f'{name}.txt').write_text('\n'.join(text), encoding='utf-8')
            (root / 'extract' / f'{name}.chars.json').write_text(json.dumps(chars, ensure_ascii=False), encoding='utf-8')
            pdf = Path(temp) / f'{name}.pdf'
            image.save(pdf, 'PDF', resolution=144)
            writer.append(str(pdf))
            pages.append({'n': n, 'w': 600, 'h': 800, 'img': f'pages/{name}.webp'})
            image.close()
            image = None
        draw = None
        y, text, chars = 90, [], []
        new_page()
        try:
            for chapter in chapters:
                if y > 90:
                    finish()
                    new_page()
                for block in chapter:
                    if block[0] == 'image':
                        with Image.open(io.BytesIO(block[1])) as original, original.convert('RGB') as pic:
                            pic.thumbnail((1020, 1100))
                            if y + pic.height > 1480:
                                finish()
                                new_page()
                            image.paste(pic, (90, y))
                            y += pic.height + 24
                        if block[2]:
                            text.append(block[2])
                        continue
                    font = heading if block[0] == 'heading' else normal
                    step = 54 if block[0] == 'heading' else 44
                    # Word wrapping for Latin text, character wrapping for CJK/long tokens.
                    tokens = re.findall(r'[^\W_]+(?:[’\x27][^\W_]+)*\s*|[^\w]|_', block[1], re.UNICODE)
                    line = ''
                    lines = []
                    for token in tokens:
                        if font.getlength(token) <= 1020 and font.getlength(line + token) <= 1020:
                            line += token
                            continue
                        if line:
                            lines.append(line.rstrip())
                            line = ''
                        for char in token:
                            if line and font.getlength(line + char) > 1020:
                                lines.append(line.rstrip())
                                line = ''
                            line += char
                    if line.strip():
                        lines.append(line.rstrip())
                    for line in lines:
                        if y + step > 1480:
                            finish()
                            new_page()
                        draw.text((90, y), line, font=font, fill='#20242a')
                        x = 90
                        for char in line:
                            width = font.getlength(char)
                            chars.append([char, round(x / 1200, 4), round(y / 1600, 4), round((x + width) / 1200, 4), round((y + step) / 1600, 4)])
                            x += width
                        text.append(line)
                        y += step
                    y += 18
            finish()
            output = Path(temp) / 'reference.pdf'
            writer.write(str(output))
            os.replace(output, root / 'source.pdf')
            return pages
        finally:
            if image is not None:
                image.close()
            writer.close()
