"""检查/写入流程与视图状态。只依赖 QtCore；界面通过 stateChanged 渲染，通过方法表达意图。"""
import threading
from dataclasses import dataclass, replace
from typing import Optional

from PySide6.QtCore import QObject, Signal

from domain.ledger import NO_CHANGE_TEXT, LedgerSnapshot, mark_written

IDLE, CHECKING, CHECKED, APPLYING, APPLIED = "idle", "checking", "checked", "applying", "applied"


@dataclass(frozen=True)
class Banner:
    severity: str  # info / success / warning / error
    title: str
    message: str


@dataclass(frozen=True)
class ViewState:
    phase: str = IDLE
    schema_dir: str = ""
    backup_dir: str = ""
    feature_key: str = ""
    snapshot: Optional[LedgerSnapshot] = None
    stale: bool = False
    banner: Optional[Banner] = None
    last_run_dir: str = ""
    has_log: bool = False

    @property
    def busy(self):
        return self.phase in (CHECKING, APPLYING)

    @property
    def can_check(self):
        return not self.busy and bool(self.schema_dir.strip())

    @property
    def apply_hint(self):
        snap = self.snapshot
        if self.busy:
            return ""
        if snap is None:
            return "先检查，确认改动后才能写入"
        if self.stale:
            return "参数已变更，请重新检查"
        if self.phase == APPLIED:
            return "已写入并备份；可再次检查核对"
        if snap.blocked:
            return "执行修改已锁定"
        if snap.nothing_to_do:
            return "无需修改"
        if not self.backup_dir.strip():
            return "请先选择备份文件夹"
        return "将修改%d处，涉及%d个文件，写入前先备份" % (len(snap.pending), len(snap.files))

    @property
    def can_apply(self):
        snap = self.snapshot
        return (not self.busy and snap is not None and not self.stale and self.phase == CHECKED
                and not snap.blocked and bool(snap.pending) and bool(self.backup_dir.strip()))


def _thread_runner(work, done):
    def target():
        try:
            result, error = work(), None
        except Exception as caught:  # 交给控制器转成界面提示
            result, error = None, caught
        done(result, error)
    threading.Thread(target=target, daemon=True).start()


class PatchController(QObject):
    stateChanged = Signal(object)
    _finished = Signal(int, object, object, object)

    def __init__(self, gateway, settings, runner=_thread_runner, parent=None):
        super().__init__(parent)
        self._gateway = gateway
        self._settings = settings
        self._runner = runner
        self._generation = 0
        self._plan = None
        self._logs = []
        self._features = gateway.features()
        saved = settings.load()
        keys = [f.key for f in self._features]
        feature = saved["feature"] if saved["feature"] in keys else keys[0]
        self._state = ViewState(schema_dir=saved["schema_dir"], backup_dir=saved["backup_dir"], feature_key=feature)
        self._finished.connect(self._on_finished)

    # ---------------------------------------------------------------- 查询
    @property
    def state(self):
        return self._state

    def features(self):
        return list(self._features)

    def feature(self, key):
        return next(f for f in self._features if f.key == key)

    def session_log(self):
        return "\n".join(self._logs)

    def confirmation_text(self):
        snap = self._state.snapshot
        return ("将修改%d处，涉及：\n%s\n\n原文件会先备份到：\n%s\n\n请确认 OPM 已关闭。"
                % (len(snap.pending), "\n".join(snap.files), self._state.backup_dir))

    # ---------------------------------------------------------------- 输入
    def set_schema_dir(self, path):
        self._set_input(schema_dir=path.strip())

    def set_backup_dir(self, path):
        self._update(backup_dir=path.strip())
        self._save_settings()

    def set_feature(self, key):
        self._set_input(feature_key=key)

    def _set_input(self, **changes):
        current = self._state
        if all(getattr(current, k) == v for k, v in changes.items()):
            return
        stale = current.snapshot is not None
        self._update(stale=stale, **changes)
        self._save_settings()

    # ---------------------------------------------------------------- 动作
    def check(self):
        state = self._state
        if not state.can_check:
            return
        self._generation += 1
        generation = self._generation
        self._update(phase=CHECKING, banner=Banner("info", "正在检查", "只读检查，不会改动文件。"))
        schema_dir, feature = state.schema_dir, state.feature_key
        self._runner(lambda: self._gateway.check(schema_dir, feature),
                     lambda result, error: self._finished.emit(generation, "check", result, error))

    def apply(self):
        if not self._state.can_apply or self._plan is None:
            return
        self._generation += 1
        generation = self._generation
        plan, state = self._plan, self._state
        gateway = self._gateway

        def work():
            outcome, log_text = gateway.apply(plan, state.backup_dir)
            try:
                after, _ = gateway.check(state.schema_dir, state.feature_key)
            except Exception:  # 已写入成功，复查失败只是少了刷新，不影响结果
                after = None
            return outcome, log_text, after

        self._update(phase=APPLYING, banner=Banner("info", "正在写入", "正在备份并写入，请勿关闭窗口。"))
        self._runner(work, lambda result, error: self._finished.emit(generation, "apply", result, error))

    def save_log(self, path):
        self._gateway.save_text(path, self.session_log() or "（本次会话尚无检查或修改记录）\n")

    def can_close(self):
        return not self._state.busy

    # ---------------------------------------------------------------- 结果
    def _on_finished(self, generation, kind, result, error):
        if generation != self._generation:
            return
        if kind == "check":
            self._check_finished(result, error)
        else:
            self._apply_finished(result, error)

    def _check_finished(self, result, error):
        if error is not None:
            self._plan = None
            self._update(phase=IDLE, snapshot=None, stale=False,
                         banner=Banner("error", "检查失败", "%s：%s" % (type(error).__name__, error)))
            return
        snapshot, plan = result
        self._plan = plan
        self._logs.append(self._gateway.detailed_log(plan))
        if snapshot.blocked:
            banner = Banner("error", snapshot.summary, "未修改任何文件。请按台账中红色条目人工处理后重新检查。")
        elif snapshot.nothing_to_do:
            banner = Banner("success", "无需修改", NO_CHANGE_TEXT)
        else:
            banner = Banner("info", snapshot.summary, "核对无误后执行修改，写入前会先备份原文件。")
        self._update(phase=CHECKED, snapshot=snapshot, stale=False, banner=banner, has_log=True)

    def _apply_finished(self, result, error):
        if error is not None:
            self._update(phase=CHECKED, banner=Banner("error", "修改失败", str(error)))
            return
        outcome, log_text, after = result
        self._plan = None
        self._logs.append(log_text)
        before = self._state.snapshot
        snapshot = mark_written(after, before) if after is not None and before is not None else before
        self._update(phase=APPLIED, last_run_dir=outcome.run_dir, snapshot=snapshot, has_log=True,
                     banner=Banner("success", "修改完成，原文件已备份", "重启 OPM 后生效。备份与改动记录在“打开备份文件夹”中。"))

    # ---------------------------------------------------------------- 内部
    def _update(self, **changes):
        self._state = replace(self._state, **changes)
        self.stateChanged.emit(self._state)

    def _save_settings(self):
        s = self._state
        self._settings.save({"schema_dir": s.schema_dir, "backup_dir": s.backup_dir, "feature": s.feature_key})
