from easyread.cli import main


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--pdf-worker':
        from easyread.pdf_worker import main as worker_main
        worker_main(sys.argv[2:])
    else:
        main()
