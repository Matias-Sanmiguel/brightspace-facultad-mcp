"""Internal subprocess for time- and memory-bounded document parsing."""
from pathlib import Path
import json
import sys

from .core import AppError
from .documents import extract_document


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
        resource.setrlimit(resource.RLIMIT_CPU,(30,30))
    except (ImportError,ValueError,OSError):
        # Windows does not provide resource; the parent still enforces a hard
        # wall-clock deadline, file/ZIP/page/decoded-byte and output budgets.
        pass
    try:
        result={'ok':True,'documento':extract_document(Path(sys.argv[1]),int(sys.argv[2]))}
    except AppError as exc:
        result=exc.result()
    # This pipe is a UTF-8 protocol, independent of the Windows console locale.
    sys.stdout.buffer.write(json.dumps(result,ensure_ascii=False).encode("utf-8") + b"\n")


if __name__=='__main__':
    main()
