import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from PySide6.QtCore import QCoreApplication  # noqa: E402

from application.controller import APPLIED, CHECKED, IDLE, PatchController  # noqa: E402
from domain.ledger import (ADDED, CONFLICT, INSTALLED, WRITTEN, ApplyOutcome, FeatureOption, LedgerEntry,  # noqa: E402
                           LedgerSnapshot)

APP = QCoreApplication.instance() or QCoreApplication([])


def snapshot(*statuses):
    return LedgerSnapshot("全部", "S", tuple(
        LedgerEntry(s, "OpenPlant_3D.01.08.ecschema.xml", 10, i + 1, "增加耳轴", "ECClass[@typeName='X%d']" % i, "m")
        for i, s in enumerate(statuses)))


class FakeGateway(object):
    def __init__(self):
        self.next = snapshot(ADDED)
        self.fail_check = None
        self.fail_apply = None
        self.applied = []

    def features(self):
        return [FeatureOption("trunnion", "增加耳轴", "d"), FeatureOption("all", "全部", "d")]

    def check(self, schema_dir, feature):
        if self.fail_check:
            raise self.fail_check
        return self.next, ("plan", schema_dir, feature)

    def detailed_log(self, plan):
        return "LOG %s" % (plan,)

    def apply(self, plan, backup):
        if self.fail_apply:
            raise self.fail_apply
        self.applied.append((plan, backup))
        return ApplyOutcome("R", "R/SchemaPatch.log", (("a", "b"),)), "APPLY LOG"

    def save_text(self, path, text):
        self.saved = (path, text)


class FakeSettings(object):
    def __init__(self, values=None):
        self.values = values or {"schema_dir": "S", "backup_dir": "B", "feature": "missing"}
        self.saved = []

    def load(self):
        return dict(self.values)

    def save(self, values):
        self.saved.append(dict(values))


def sync(work, done):
    try:
        done(work(), None)
    except Exception as error:
        done(None, error)


class Deferred(object):
    def __init__(self):
        self.pending = []

    def __call__(self, work, done):
        self.pending.append((work, done))

    def finish(self, index=0):
        work, done = self.pending.pop(index)
        sync(work, done)


class ControllerTests(unittest.TestCase):
    def make(self, runner=sync, settings=None):
        self.gateway = FakeGateway()
        return PatchController(self.gateway, settings or FakeSettings(), runner=runner)

    def test_initial_state_and_unknown_feature_falls_back(self):
        c = self.make()
        self.assertEqual((c.state.phase, c.state.feature_key, c.state.schema_dir), (IDLE, "trunnion", "S"))
        self.assertFalse(c.state.can_apply)
        self.assertIn("先检查", c.state.apply_hint)

    def test_check_then_apply(self):
        c = self.make()
        c.check()
        self.assertEqual(c.state.phase, CHECKED)
        self.assertTrue(c.state.can_apply)
        self.assertEqual(c.state.banner.severity, "info")
        c.apply()
        self.assertEqual(self.gateway.applied, [(("plan", "S", "trunnion"), "B")])
        self.assertEqual((c.state.phase, c.state.last_run_dir), (APPLIED, "R"))
        self.assertFalse(c.state.can_apply)
        self.assertIn("LOG", c.session_log())
        self.assertIn("APPLY LOG", c.session_log())

    def test_apply_rechecks_and_marks_written(self):
        c = self.make()
        self.gateway.next = snapshot(ADDED, INSTALLED)
        c.check()
        self.gateway.next = snapshot(INSTALLED, INSTALLED)
        c.apply()
        self.assertEqual([e.status for e in c.state.snapshot.entries], [WRITTEN, INSTALLED])

    def test_conflict_and_nothing_to_do_block_apply(self):
        c = self.make()
        self.gateway.next = snapshot(ADDED, CONFLICT)
        c.check()
        self.assertFalse(c.state.can_apply)
        self.assertEqual(c.state.banner.severity, "error")
        self.gateway.next = snapshot(INSTALLED)
        c.check()
        self.assertFalse(c.state.can_apply)
        self.assertEqual(c.state.banner.title, "无需修改")
        c.apply()
        self.assertEqual(self.gateway.applied, [])

    def test_input_change_marks_stale_and_blocks_apply(self):
        c = self.make()
        c.check()
        c.set_feature("all")
        self.assertTrue(c.state.stale)
        self.assertFalse(c.state.can_apply)
        self.assertIn("重新检查", c.state.apply_hint)
        c.check()
        self.assertFalse(c.state.stale)
        self.assertTrue(c.state.can_apply)

    def test_missing_backup_blocks_apply(self):
        c = self.make(settings=FakeSettings({"schema_dir": "S", "backup_dir": "", "feature": "all"}))
        c.check()
        self.assertFalse(c.state.can_apply)
        self.assertIn("备份文件夹", c.state.apply_hint)
        c.set_backup_dir("D:\\bak")
        self.assertTrue(c.state.can_apply)

    def test_stale_result_from_older_check_is_ignored(self):
        runner = Deferred()
        c = self.make(runner=runner)
        c.check()
        self.gateway.next = snapshot(INSTALLED)
        c._state = c._state.__class__(**dict(c._state.__dict__, phase=IDLE))  # 模拟用户再次检查
        c.check()
        runner.finish(1)
        self.assertTrue(c.state.snapshot.nothing_to_do)
        runner.finish(0)
        self.assertTrue(c.state.snapshot.nothing_to_do, "older result must not overwrite newer one")

    def test_failures_become_banners(self):
        c = self.make()
        self.gateway.fail_check = RuntimeError("boom")
        c.check()
        self.assertEqual((c.state.phase, c.state.banner.title), (IDLE, "检查失败"))
        self.gateway.fail_check = None
        c.check()
        self.gateway.fail_apply = RuntimeError("拒绝访问")
        c.apply()
        self.assertEqual((c.state.phase, c.state.banner.title), (CHECKED, "修改失败"))
        self.assertIn("拒绝访问", c.state.banner.message)

    def test_busy_blocks_close_and_settings_saved(self):
        runner = Deferred()
        settings = FakeSettings()
        c = self.make(runner=runner, settings=settings)
        c.check()
        self.assertFalse(c.can_close())
        runner.finish()
        self.assertTrue(c.can_close())
        c.set_schema_dir(" E:\\ws ")
        self.assertEqual(settings.saved[-1]["schema_dir"], "E:\\ws")

    def test_save_log(self):
        c = self.make()
        c.save_log("x.log")
        self.assertIn("尚无", self.gateway.saved[1])
        c.check()
        c.save_log("y.log")
        self.assertIn("LOG", self.gateway.saved[1])


if __name__ == "__main__":
    unittest.main()
