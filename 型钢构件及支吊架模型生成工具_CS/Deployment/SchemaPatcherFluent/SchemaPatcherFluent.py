"""Fluent 版 Schema 增补工具入口。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from app.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
