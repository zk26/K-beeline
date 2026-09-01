"""K-Beeline 启动入口（开发调试与 PyInstaller 打包共用）。

包含全局崩溃捕获：任何未处理异常都会写入
%LOCALAPPDATA%\\KBeeline\\logs\\crash.log，便于远程排查用户机器上的问题。
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _write_crash_log(text: str) -> None:
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        log_dir = os.path.join(base, "KBeeline", "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "crash.log"), "a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(text)
            f.write("\n")
    except Exception:
        pass


def _excepthook(exc_type, exc_value, exc_tb):
    _write_crash_log("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook


def main_entry() -> int:
    try:
        from app.main import main
        return main()
    except Exception:
        _write_crash_log(traceback.format_exc())
        raise


if __name__ == "__main__":
    sys.exit(main_entry())
