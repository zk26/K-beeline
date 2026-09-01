"""GUI 冒烟测试（Qt offscreen 离屏模式，不需要真实显示器）。

用法: .venv\\Scripts\\python tests\\smoke_gui.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)

    from app.ui.main_window import MainWindow
    win = MainWindow()
    win.show()

    assert win.post_radio.isChecked()
    win.activate_radio.setChecked(True)
    assert not win.proxy_check.isChecked() and not win.location_check.isChecked()
    win.post_radio.setChecked(True)
    assert not win.proxy_check.isChecked() and not win.location_check.isChecked()
    print("[OK] 模式切换默认开关")

    win.append_log("smoke test", "INFO")
    assert win.log_view.document().blockCount() >= 1
    print("[OK] 日志输出")

    QTimer.singleShot(800, app.quit)
    app.exec()
    print("\n===== smoke_gui 全部通过 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
