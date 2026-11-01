"""组装根：创建应用、主题、引擎适配、设置、控制器与窗口。"""
import sys

import fluentqt as fq
from PySide6.QtWidgets import QApplication

from application.controller import PatchController
from infrastructure.patcher_gateway import PatcherGateway
from infrastructure.settings_store import SettingsStore
from ui.shell.main_window import MainWindow


def main(argv=None):
    fq.prepare_high_dpi_application()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("SchemaPatcherFluent")
    fq.initialize_resources()
    fq.apply_user_theme()
    controller = PatchController(PatcherGateway(), SettingsStore())
    window = MainWindow(controller)
    window.show()
    return app.exec()
