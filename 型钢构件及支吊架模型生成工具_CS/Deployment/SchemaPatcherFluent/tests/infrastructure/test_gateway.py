import os
import shutil
import sys
import unittest
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from domain.ledger import ADDED, INSTALLED, MODIFIED  # noqa: E402
from infrastructure.patcher_gateway import PatchFailed, PatcherGateway  # noqa: E402
from infrastructure.settings_store import SettingsStore  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tests", "ui"))
from capture_evidence import FIXTURES  # noqa: E402


@unittest.skipUnless(all(os.path.isfile(p) for p in FIXTURES.values()), "原始 Schema 备份不存在")
class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.base = os.path.join(ROOT, "tests", ".work", uuid.uuid4().hex)
        self.schema = os.path.join(self.base, "Schemas")
        os.makedirs(self.schema)
        for name, source in FIXTURES.items():
            shutil.copyfile(source, os.path.join(self.schema, name))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_check_apply_recheck(self):
        gateway = PatcherGateway()
        self.assertEqual([f.key for f in gateway.features()],
                         ["trunnion", "pipe_clamp", "iso_tag", "iso_schema", "valve_actuator", "all"])
        snap, plan = gateway.check(self.schema, "all")
        self.assertEqual((snap.count(ADDED), snap.count(MODIFIED), len(snap.pending)), (12, 3, 15))
        self.assertTrue(all(e.file_lines > 1000 for e in snap.entries))
        self.assertIn("只读检查", gateway.detailed_log(plan))
        with self.assertRaises(PatchFailed):
            gateway.apply(plan, os.path.join(self.schema, "inside"))
        # 写入路径与 OPM 运行检测由引擎负责，这里只验证适配：OPM 未运行时才写
        if gateway.running_opm():
            self.skipTest("OPM 正在运行，跳过写入")
        outcome, log = gateway.apply(plan, os.path.join(self.base, "backup"))
        self.assertTrue(os.path.isfile(outcome.log_path))
        self.assertEqual(len(outcome.files), 3)
        self.assertIn("修改后第", log)
        again, _ = gateway.check(self.schema, "all")
        self.assertTrue(again.nothing_to_do)
        self.assertEqual(again.count(INSTALLED), len(again.entries))

    def test_settings_fallback_and_roundtrip(self):
        legacy = os.path.join(self.base, "legacy.json")
        with open(legacy, "w", encoding="utf-8-sig") as stream:
            stream.write('{"schema_dir": "A", "backup_dir": "B", "feature": "iso_tag"}')
        store = SettingsStore(os.path.join(self.base, "new", "s.json"), legacy)
        self.assertEqual(store.load()["feature"], "iso_tag")
        store.save({"schema_dir": "C", "backup_dir": "D", "feature": "all"})
        self.assertEqual(store.load()["schema_dir"], "C")
        self.assertEqual(SettingsStore(os.path.join(self.base, "x.json"), os.path.join(self.base, "y.json")).load()["schema_dir"], "")


if __name__ == "__main__":
    unittest.main()
