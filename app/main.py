"""应用入口：初始化 Qt 应用与主窗口"""
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.services.logging_service import get_logger, set_ui_callback
from app.ui.main_window import APP_TITLE, MainWindow
from app.utils import paths


def main() -> int:
    logger = get_logger()
    logger.info("=" * 60)
    logger.info(f"{APP_TITLE} 启动")

    app = QApplication(sys.argv)
    app.setApplicationName("KBeeline")
    app.setOrganizationName("KBeeline")
    app.setStyle("Fusion")

    icon_path = paths.resource_path("assets", "icons", "logo.png")
    app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    set_ui_callback(lambda msg, level: window.append_log(msg, level))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
