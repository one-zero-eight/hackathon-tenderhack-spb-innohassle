"""Run from search/: uv run -m src"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if __name__ == "__main__":
    import uvicorn

    os.chdir(_SRC)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9005,
        reload=False,
        app_dir=str(_SRC),
    )
