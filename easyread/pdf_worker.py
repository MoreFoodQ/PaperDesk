"""Dedicated PDF worker. No model credentials or backend imports in this process."""
import json
import sys
from pathlib import Path


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    root = Path(__file__).resolve().parents[1]
    if not getattr(sys, 'frozen', False):
        sys.path.insert(0, str(root))
        sys.path.insert(0, argv[0])
    import os
    os.environ['PAPERDESK_PDF_WORKER'] = '1'
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_AS, (1536*1024*1024, 1536*1024*1024))
    from easyread import pdfwork
    operation = argv[1]
    allowed = {'prepare', 'crop', 'engine_image', 'locate', 'title'}
    if operation not in allowed: raise ValueError('Invalid PDF operation')
    args = json.loads(argv[2])
    args[0] = Path(args[0])
    if operation == 'title':
        from easyread.library import _pdf_title
        result = _pdf_title(args[0])
    else:
        result = getattr(pdfwork, operation)(*args)
    print(json.dumps(str(result) if isinstance(result, Path) else result))


if __name__ == '__main__': main()
