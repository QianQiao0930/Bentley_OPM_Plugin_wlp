import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from dataclasses import replace  # noqa: E402

from domain.ledger import (ADDED, CONFLICT, INSTALLED, MODIFIED, NO_CHANGE_TEXT, WRITTEN, LedgerEntry,  # noqa: E402
                           LedgerSnapshot, mark_written, split_field_change)


def entry(status, target="ECClass[@typeName='SINGLE_PIPE_TRUNNION']/ECProperty[@propertyName='SSP_RECIPE']",
          message="SINGLE_PIPE_TRUNNION 增加字段 SSP_RECIPE(string)", details=(), file_name="OpenPlant_3D.01.08.ecschema.xml"):
    return LedgerEntry(status, file_name, 38627, 32195, "增加耳轴", target, message, tuple(details))


class LedgerTests(unittest.TestCase):
    def test_location_and_short_message(self):
        self.assertEqual(entry(ADDED).location, "SINGLE_PIPE_TRUNNION / SSP_RECIPE")
        self.assertEqual(entry(ADDED).short_message, "增加字段 SSP_RECIPE(string)")
        creation = entry(MODIFIED, target="ECClass[@typeName='X']/ECCustomAttributes/CREATION_ATTRIBUTE", message="改值")
        self.assertEqual(creation.location, "X / CREATION_ATTRIBUTE")
        self.assertEqual(entry(ADDED, target="ECClass[@typeName='SSP_PIPE_CLAMP']").location, "SSP_PIPE_CLAMP")
        modeling = entry(MODIFIED, target="ECClass[@typeName='X']/ECCustomAttributes/CREATION_ATTRIBUTE",
                         message="X CREATION_ATTRIBUTE 改为指向 NativePipeSupportComponent")
        self.assertEqual(modeling.short_message, "改为指向 NativePipeSupportComponent")
        labels = entry(ADDED, target="ECClass[@typeName='X']/ECCustomAttributes/BOM_LABELS",
                       message="X 新增 BOM_LABELS（克隆 PLANT_BASE_OBJECT，IE_TAG=this.ALIAS）")
        self.assertEqual(labels.short_message, "新增（克隆 PLANT_BASE_OBJECT，IE_TAG=this.ALIAS）")
        self.assertEqual(entry(CONFLICT, target="-").location, "-")

    def test_field_changes_and_inserted_text(self):
        detail = "ASSEMBLY_NAME：Bentley.Building.Mechanical.ComponentLibrary → SteelSectionProbe"
        change = split_field_change(detail)
        self.assertEqual((change.name, change.before, change.after),
                         ("ASSEMBLY_NAME", "Bentley.Building.Mechanical.ComponentLibrary", "SteelSectionProbe"))
        self.assertIsNone(split_field_change("IE_TAG = this.ALIAS"))
        self.assertIsNone(split_field_change("<a>\n</a>"))
        added = entry(ADDED, details=['<ECProperty propertyName="SSP_RECIPE" typeName="string" />'])
        self.assertIn("SSP_RECIPE", added.inserted_text)
        self.assertEqual(entry(MODIFIED, details=[detail]).field_changes[0].after, "SteelSectionProbe")

    def test_snapshot_states(self):
        pending = LedgerSnapshot("全部", "d", (entry(ADDED), entry(MODIFIED), entry(INSTALLED)))
        self.assertFalse(pending.blocked)
        self.assertFalse(pending.nothing_to_do)
        self.assertEqual(pending.summary, "检查完成：2处待修改（1新增、1修改）")
        blocked = LedgerSnapshot("全部", "d", (entry(ADDED), entry(CONFLICT)))
        self.assertTrue(blocked.blocked)
        self.assertIn("执行修改已锁定", blocked.summary)
        done = LedgerSnapshot("全部", "d", (entry(INSTALLED),))
        self.assertTrue(done.nothing_to_do)
        self.assertEqual(done.summary, NO_CHANGE_TEXT)
        self.assertFalse(LedgerSnapshot("全部", "d", ()).nothing_to_do)

    def test_mark_written_keeps_change_description(self):
        before = LedgerSnapshot("全部", "d", (entry(ADDED, details=["<x/>"]), entry(INSTALLED, target="T2")))
        after = LedgerSnapshot("全部", "d", (replace(entry(INSTALLED, message="已具备 X"), original_line=40000),
                                             entry(INSTALLED, target="T2")))
        marked = mark_written(after, before)
        self.assertEqual([e.status for e in marked.entries], [WRITTEN, INSTALLED])
        self.assertEqual(marked.entries[0].message, "SINGLE_PIPE_TRUNNION 增加字段 SSP_RECIPE(string)")
        self.assertEqual(marked.entries[0].original_line, 40000)
        self.assertTrue(marked.nothing_to_do)


if __name__ == "__main__":
    unittest.main()
