"""驱动真实窗口采集视觉证据：各状态截图、Inspector 报告与几何测量，输出到 tests/.evidence。"""
import json
import os
import shutil
import sys
import time
import uuid

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import fluentqt as fq  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from application import controller as controller_module  # noqa: E402
from application.controller import PatchController  # noqa: E402
from infrastructure.patcher_gateway import PatcherGateway  # noqa: E402
from infrastructure.settings_store import SettingsStore  # noqa: E402
from ui.shell.main_window import MainWindow  # noqa: E402
from ui.theme import tokens  # noqa: E402

from schema_patcher import engine  # noqa: E402  (由 patcher_gateway 加入路径)

BACKUPS = os.path.abspath(os.path.join(ROOT, "..", "..", "..", "迁移备份"))
FIXTURES = {
    "OpenPlant_3D.01.08.ecschema.xml": os.path.join(
        BACKUPS, "耳轴Schema安装_20261015", "schema-backup",
        "OpenPlant_3D.01.08.ecschema.xml.6c32ea08e4cf4a209b3cef8382f0f48b.bak"),
    "OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml": os.path.join(
        BACKUPS, "耳轴Schema安装_20261015", "schema-backup",
        "OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml.0d8ba51294084301bd6cf420e4f2c67f.bak"),
    "OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml": os.path.join(
        BACKUPS, "管夹引注按管架编号_20261014_085db60", "工作集Schema",
        "OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml"
        ".20261014_224638_990.ba5f6d4d355a43d3948e46e2572d3023.bak"),
}
OUT = os.path.join(ROOT, "tests", ".evidence")


class FixtureGateway(PatcherGateway):
    """只写 tests/.work 下的临时夹具，跳过“OPM 是否在运行”的检测；产品代码仍强制检测。"""

    def apply(self, plan, backup_dir):
        from domain.ledger import ApplyOutcome
        result = engine.apply_plan(plan, backup_dir, check_processes=False)
        files = tuple((r["schema"], r["backup"]) for r in result.files)
        return ApplyOutcome(result.run_dir, result.log_path, files), result.log_text


def sync_runner(work, done):
    try:
        result, error = work(), None
    except Exception as caught:
        result, error = None, caught
    done(result, error)


def make_workspace(base):
    """原始 Schema 副本，并预装轴测引注后改坏表达式，制造一处“项目自定义引注”冲突。"""
    schema = os.path.join(base, "WorkSets", "CINF_F1301BB", "Standards", "OpenPlant", "Schemas")
    os.makedirs(schema)
    for name, source in FIXTURES.items():
        shutil.copyfile(source, os.path.join(schema, name))
    plan = engine.load_plan(schema, "iso_tag")
    engine.apply_plan(plan, os.path.join(base, "seed-backup"), check_processes=False)
    iso = os.path.join(schema, "OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml")
    with open(iso, "rb") as stream:
        data = stream.read()
    with open(iso, "wb") as stream:
        stream.write(data.replace(b"IIf(IM.Match(this.DEVICE_TYPE_CODE", b"IIf(IM.Match(this.PROJECT_CODE", 1))
    return schema, iso, data


class Harness(object):
    def __init__(self, app, window, controller):
        self.app, self.window, self.controller, self.page = app, window, controller, window.page
        self.measurements = {}

    def settle(self, rounds=15):
        for _ in range(rounds):
            self.app.processEvents()

    def shot(self, name, width=1440, height=900, widget=None):
        if widget is None:
            self.window.resize(width, height)
        self.settle()
        path = os.path.join(OUT, name + ".png")
        (widget or self.window).grab().save(path)
        print(path)
        return path

    def wait_idle(self, timeout=30):
        deadline = time.time() + timeout
        while self.controller.state.busy and time.time() < deadline:
            self.app.processEvents()
            time.sleep(0.02)
        assert not self.controller.state.busy, "检查超时"

    def entry_rows(self):
        model = self.page.model
        return [r for r in range(model.rowCount()) if model.entry(r) is not None]

    def select(self, status):
        row = next(r for r in self.entry_rows() if self.page.model.entry(r).status == status)
        self.page.list.setCurrentIndex(self.page.model.index(row))
        return row

    def measure_rows(self):
        lst = self.page.list
        rects = [lst.visualRect(self.page.model.index(r)) for r in range(self.page.model.rowCount())]
        entries = [rects[r].height() for r in self.entry_rows()]
        headers = [rects[r].height() for r in range(len(rects)) if self.page.model.entry(r) is None]
        cadence = [rects[r + 1].top() - rects[r].top() for r in self.entry_rows()[:-1]
                   if self.page.model.entry(r + 1) is not None]
        self.measurements["entry-row-height"] = sorted(set(entries))
        self.measurements["header-row-height"] = sorted(set(headers))
        self.measurements["row-cadence"] = sorted(set(cadence))

    def measure_layout(self):
        page = self.page
        strip = page.strip.geometry()
        banner = page.banner.geometry()
        footer = page.footer.geometry()
        self.measurements["edge-inset-left"] = strip.left()
        self.measurements["edge-inset-right"] = page.width() - strip.right() - 1
        self.measurements["strip-to-banner-gap"] = banner.top() - strip.bottom() - 1
        self.measurements["detail-width"] = page.detail_card.width()
        self.measurements["control-height"] = page.strip.check.height()
        self.measurements["footer-bottom-inset"] = page.height() - footer.bottom() - 1

    def measure_scroll_end(self):
        lst = self.page.list
        lst.scrollToBottom()
        self.settle()
        first = (lst.verticalScrollBar().maximum(), lst.viewport().height())
        self.settle()
        second = (lst.verticalScrollBar().maximum(), lst.viewport().height())
        last = lst.visualRect(self.page.model.index(self.page.model.rowCount() - 1))
        self.measurements["scroll-range-stable"] = first == second
        self.measurements["last-row-bottom-vs-viewport"] = [last.bottom(), lst.viewport().height()]
        return last.bottom() < lst.viewport().height()


KEEP = ("visual-evidence.json", "visual-review.html", "reference-selected-concept.png", "exe-launch.png")


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        if name not in KEEP and name.endswith((".png", ".json")):
            os.remove(os.path.join(OUT, name))
    base = os.path.join(ROOT, "tests", ".work", "demo")
    shutil.rmtree(base, ignore_errors=True)
    schema, iso, clean_iso = make_workspace(base)
    app = QApplication(sys.argv)
    fq.initialize_resources()
    fq.set_theme(fq.Theme.Light)
    store = SettingsStore(os.path.join(base, "settings.json"), os.path.join(base, "none.json"))
    store.save({"schema_dir": schema, "backup_dir": os.path.join(base, "Schema备份"), "feature": "all"})
    controller = PatchController(FixtureGateway(), store, runner=sync_runner)
    window = MainWindow(controller)
    # 截图（QWidget.grab）抓不到系统合成的 Mica，采集时改用纯色背景，真实运行仍为 Mica。
    window.setBackdropEffect(fq.BackdropEffect.Solid)
    messages = []
    window.page.show_message = lambda title, text, severity="info": messages.append((title, text))
    window.page.ask_confirmation = lambda text: messages.append(("confirm", text)) or True
    h = Harness(app, window, controller)
    page = window.page
    window.show()

    page.list.setFocus()
    h.shot("empty")
    page.strip.schema.edit.setFocus()
    page.strip.schema.edit.end(False)
    h.shot("input-single-line-focus")
    page.strip.schema.edit.deselect()
    page.list.setFocus()

    controller._runner = controller_module._thread_runner
    controller.check()
    h.shot("async-checking")
    h.wait_idle()
    h.settle()
    first = page.list.verticalScrollBar().maximum()
    h.settle()
    h.measurements["async-scroll-range-stable"] = first == page.list.verticalScrollBar().maximum()
    controller._runner = sync_runner
    h.shot("normal-light")
    h.measure_rows()
    h.measure_layout()
    h.select("修改")
    page.list.setFocus()
    h.shot("selected-focus-disabled")
    report = fq.inspect_widget(window)
    with open(os.path.join(OUT, "inspector.json"), "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
    fq.set_theme(fq.Theme.Dark)
    h.shot("normal-dark")
    fq.set_theme(fq.Theme.Light)
    h.shot("narrow", 1000, 720)
    selected = page.model.entry(page.list.currentIndex().row())
    narrow_dialog = page.build_detail_dialog(selected)
    narrow_dialog.show()
    h.shot("narrow-detail-dialog", widget=narrow_dialog)
    narrow_dialog.hide()
    narrow_dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    h.settle(40)
    page.restore_focus()
    h.shot("minimum", 860, 560)
    h.measurements["scroll-end-readable"] = h.measure_scroll_end()
    h.shot("scroll-end", 860, 560)
    h.window.resize(1440, 900)
    h.settle()

    controller.set_feature("valve_actuator")
    h.shot("stale")
    assert page.banner.title() == "参数已变更", page.banner.title()
    controller.check()
    h.shot("density-sparse")
    with open(iso, "wb") as stream:
        stream.write(clean_iso)
    controller.set_feature("trunnion")
    controller.check()
    h.shot("ready")
    dialog = page.build_confirmation(controller.confirmation_text())
    dialog.show()
    h.shot("transient-confirm-dialog", widget=dialog)
    dialog.hide()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    h.settle(40)
    page.restore_focus()
    controller.apply()
    h.shot("applied")
    controller.check()
    h.shot("nothing-to-do")
    window.close()

    assert any(t == "无需修改" for t, _ in messages), messages
    assert any(t == "修改完成" for t, _ in messages), messages
    with open(os.path.join(OUT, "measurements.json"), "w", encoding="utf-8") as stream:
        json.dump(h.measurements, stream, ensure_ascii=False, indent=2)
    print("measurements:", json.dumps(h.measurements, ensure_ascii=False))
    print("inspector keys:", list(report.keys()) if isinstance(report, dict) else type(report))
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
