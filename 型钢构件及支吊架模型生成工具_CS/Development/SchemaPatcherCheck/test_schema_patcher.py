"""Deployment/SchemaPatcher 离线检查：合成夹具覆盖各分支，真实原始 Schema 与 PowerShell 安装脚本做等价与互认比对。"""
import os
import shutil
import stat
import subprocess
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Deployment", "SchemaPatcher"))

from schema_patcher.engine import PatchError, apply_plan, format_log, load_plan  # noqa: E402
from schema_patcher.features import iso_tag_expression  # noqa: E402
from schema_patcher.xmlspan import same_structure  # noqa: E402

OBJ = os.path.join(HERE, "obj")
NAMES = {
    "OP3D": "OpenPlant_3D.01.08.ecschema.xml",
    "MOD": "OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml",
    "ISO": "OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml",
}
SCHEMA_NAMES = {"OP3D": "OpenPlant_3D", "MOD": "OpenPlant_3D_Supplemental_Modeling",
                "ISO": "OpenPlant_3D_Supplemental_Isometrics_Isoextractor"}
BACKUP_ROOT = os.path.abspath(os.path.join(REPO, "..", "迁移备份"))
REAL_FIXTURES = {
    "OP3D": os.path.join(BACKUP_ROOT, "耳轴Schema安装_20261015", "schema-backup",
                         "OpenPlant_3D.01.08.ecschema.xml.6c32ea08e4cf4a209b3cef8382f0f48b.bak"),
    "MOD": os.path.join(BACKUP_ROOT, "耳轴Schema安装_20261015", "schema-backup",
                        "OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml.0d8ba51294084301bd6cf420e4f2c67f.bak"),
    "ISO": os.path.join(BACKUP_ROOT, "管夹引注按管架编号_20261014_085db60", "工作集Schema",
                        "OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml"
                        ".20261014_224638_990.ba5f6d4d355a43d3948e46e2572d3023.bak"),
}
PS_INSTALL = os.path.join(REPO, "Deployment", "Install-NativeSupportEditing.ps1")
PS_ISOTAG = os.path.join(REPO, "Deployment", "Install-PipeClampIsoTag.ps1")

EC = "http://www.bentley.com/schemas/Bentley.ECXML.2.0"
OP = "OpenPlant_CustomAttributes.08.11"
ISO = "OpenPlant_IsoExtractor_Custom_Attributes.01.08"


def _creation(assembly, cls, namespace, tool, handler, indent="            "):
    i = indent + "    "
    return (indent + '<CREATION_ATTRIBUTE xmlns="%s">\n' % OP
            + i + "<ASSEMBLY_NAME>%s</ASSEMBLY_NAME>\n" % assembly
            + i + "<CLASS_NAME>%s</CLASS_NAME>\n" % cls
            + i + "<NAMESPACE>%s</NAMESPACE>\n" % namespace
            + i + "<PLACEMENT_TOOL>%s</PLACEMENT_TOOL>\n" % tool
            + i + "<HANDLER_TYPE>%s</HANDLER_TYPE>\n" % handler
            + indent + "</CREATION_ATTRIBUTE>\n")


BODIES = {
    "OP3D": (
        '    <ECClass typeName="SUPPORT_LOCATION" isDomainClass="True">\n'
        "        <BaseClass>SUPPORT</BaseClass>\n"
        '        <ECProperty propertyName="Geometry" typeName="binary" />\n'
        "    </ECClass>\n"
        '    <ECClass typeName="SINGLE_PIPE_TRUNNION" isDomainClass="True">\n'
        "        <BaseClass>MISC_SUPPORT</BaseClass>\n"
        "    </ECClass>\n"
        '    <ECClass typeName="DOUBLE_PIPE_TRUNNION" isDomainClass="True" />\n'
        '    <ECClass typeName="SIMPLE_ELBOW_SUPPORT" isDomainClass="True"><BaseClass>MISC_SUPPORT</BaseClass></ECClass>\n'
        '    <ECClass typeName="GEARBOX_OPERATOR" isDomainClass="True">\n'
        "        <BaseClass>MANUAL_VALVE_OPERATING_DEVICE</BaseClass>\n"
        "    </ECClass>\n"
        '    <ECClass typeName="UNRELATED" description="不应改动 &amp; 原样保留" />\n'),
    "MOD": (
        '    <ECClass typeName="SUPPORT_LOCATION" isDomainClass="False">\n        <ECCustomAttributes>\n'
        + _creation("Bentley.Building.Mechanical.ComponentLibrary", "SupportLocation",
                    "Bentley.Building.Mechanical.ComponentLibrary.Supports", "PipeSupportPlacementTool", "Support")
        + "        </ECCustomAttributes>\n    </ECClass>\n"
        '    <ECClass typeName="SINGLE_PIPE_TRUNNION" isDomainClass="False">\n        <ECCustomAttributes>\n'
        + _creation("Bentley.Building.Mechanical.ComponentLibrary", "SinglePipeTrunnion",
                    "Bentley.Building.Mechanical.ComponentLibrary.Supports", "PipeSupportPlacementTool", "Support")
        + "        </ECCustomAttributes>\n    </ECClass>\n"
        '    <ECClass typeName="DOUBLE_PIPE_TRUNNION" isDomainClass="False" />\n'
        '    <ECClass typeName="SIMPLE_ELBOW_SUPPORT" isDomainClass="False">\n        <ECCustomAttributes>\n'
        '            <Other xmlns="%s"><Value>1</Value></Other>\n' % OP
        + "        </ECCustomAttributes>\n    </ECClass>\n"
        '    <ECClass typeName="GEARBOX_OPERATOR" isDomainClass="False">\n        <ECCustomAttributes>\n'
        '            <OpenPlant_3D_Catalogue_ClassProperties xmlns="%s">\n                <ClassMapping />\n'
        "                <Table>TOPWORKS</Table>\n            </OpenPlant_3D_Catalogue_ClassProperties>\n" % OP
        + _creation("Bentley.Building.Mechanical.ComponentLibrary", "GearBoxOperatorScript",
                    "Bentley.Building.Mechanical.ComponentLibrary.ValveOperator", "TopworksPlacementTool", "Topwork")
        + "        </ECCustomAttributes>\n    </ECClass>\n"),
    "ISO": (
        '    <ECClass typeName="PLANT_BASE_OBJECT" isDomainClass="False">\n        <ECCustomAttributes>\n'
        '            <BOM_LABELS xmlns="%s">\n                <OTH_ATTRIBUTES>\n' % ISO
        + "                    <BOM_ATTR_STRUCT>\n                        <NAME>IE_TAG</NAME>\n"
        "                        <ECX_VALUE>this.NAME &amp; \"-\" &amp; this.NUMBER</ECX_VALUE>\n"
        "                    </BOM_ATTR_STRUCT>\n"
        "                    <BOM_ATTR_STRUCT>\n                        <NAME>IE_DESCRIPT</NAME>\n"
        "                        <ECX_VALUE>this.DESCRIPTION</ECX_VALUE>\n"
        "                    </BOM_ATTR_STRUCT>\n"
        "                </OTH_ATTRIBUTES>\n            </BOM_LABELS>\n        </ECCustomAttributes>\n    </ECClass>\n"
        + "".join('    <ECClass typeName="%s" isDomainClass="False">\n        <ECCustomAttributes>\n'
                  '            <IE_VALUE_MAP xmlns="%s">\n                <VALUE>SUPP_TRUNNION</VALUE>\n'
                  "            </IE_VALUE_MAP>\n        </ECCustomAttributes>\n    </ECClass>\n" % (t, ISO)
                  for t in ("SINGLE_PIPE_TRUNNION", "DOUBLE_PIPE_TRUNNION", "SIMPLE_ELBOW_SUPPORT"))),
}


def _fixture_bytes(key):
    text = ('<?xml version="1.0" encoding="utf-8"?>\n<ECSchema schemaName="%s" version="1.8" xmlns="%s">\n%s</ECSchema>'
            % (SCHEMA_NAMES[key], EC, BODIES[key]))
    return b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8")


def _read(path):
    with open(path, "rb") as stream:
        return stream.read()


def _parse(path):
    return ET.fromstring(_read(path))


def _class(root, type_name):
    return next((c for c in root if c.get("typeName") == type_name), None)


class Workspace(object):
    def __init__(self, sources=None):
        self.root = os.path.join(OBJ, uuid.uuid4().hex)
        self.schema = os.path.join(self.root, "Schemas")
        self.backup = os.path.join(self.root, "backup")
        os.makedirs(self.schema)
        for key, name in NAMES.items():
            target = os.path.join(self.schema, name)
            if sources:
                shutil.copyfile(sources[key], target)
            else:
                with open(target, "wb") as stream:
                    stream.write(_fixture_bytes(key))

    def path(self, key):
        return os.path.join(self.schema, NAMES[key])

    def snapshot(self):
        return dict((k, _read(self.path(k))) for k in NAMES)

    def cleanup(self):
        for folder, _, files in os.walk(self.root):
            for name in files:
                os.chmod(os.path.join(folder, name), stat.S_IWRITE | stat.S_IREAD)
        shutil.rmtree(self.root, ignore_errors=True)


def _apply(ws, feature):
    plan = load_plan(ws.schema, feature)
    return plan, apply_plan(plan, ws.backup, check_processes=False)


class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.cleanup()

    def test_check_is_read_only(self):
        before = self.ws.snapshot()
        for feature in ("trunnion", "pipe_clamp", "iso_tag", "valve_actuator", "all"):
            plan = load_plan(self.ws.schema, feature)
            self.assertFalse(plan.blocked, [i.message for i in plan.items if i.status in ("conflict", "error")])
            self.assertTrue(plan.pending)
        self.assertEqual(before, self.ws.snapshot())
        self.assertFalse(os.path.exists(self.ws.backup))

    def test_apply_all_content_backup_and_idempotent(self):
        before = self.ws.snapshot()
        plan, result = _apply(self.ws, "all")
        for record in result.files:
            self.assertEqual(_read(record["backup"]), before[record["key"]], "backup must be byte exact")
        for key in NAMES:
            data = _read(self.ws.path(key))
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"), "BOM preserved")
            self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), "CRLF preserved")
        self.assertIn('typeName="UNRELATED" description="不应改动 &amp; 原样保留" />'.encode("utf-8"),
                      _read(self.ws.path("OP3D")))

        op3d = _parse(self.ws.path("OP3D"))
        for t in ("SINGLE_PIPE_TRUNNION", "DOUBLE_PIPE_TRUNNION", "SIMPLE_ELBOW_SUPPORT"):
            props = [p.get("propertyName") for p in _class(op3d, t).findall("{%s}ECProperty" % EC)]
            self.assertIn("SSP_RECIPE", props)
        actuator = _class(op3d, "SSP_CEL_VALVE_ACTUATOR")
        self.assertEqual(actuator.find("{%s}BaseClass" % EC).text, "GEARBOX_OPERATOR")
        self.assertEqual([p.get("typeName") for p in actuator.findall("{%s}ECProperty" % EC)],
                         ["int", "string", "string", "string", "binary", "string"])

        mod = _parse(self.ws.path("MOD"))
        for t in ("SINGLE_PIPE_TRUNNION", "DOUBLE_PIPE_TRUNNION", "SIMPLE_ELBOW_SUPPORT", "SSP_PIPE_CLAMP"):
            creation = _class(mod, t).find("{%s}ECCustomAttributes/{%s}CREATION_ATTRIBUTE" % (EC, OP))
            self.assertEqual(creation.find("{%s}CLASS_NAME" % OP).text, "NativePipeSupportComponent", t)
            self.assertEqual(creation.find("{%s}ASSEMBLY_NAME" % OP).text, "SteelSectionProbe", t)
            self.assertEqual(creation.find("{%s}HANDLER_TYPE" % OP).text, "Support", t)
        self.assertIsNotNone(_class(mod, "SIMPLE_ELBOW_SUPPORT").find("{%s}ECCustomAttributes/{%s}Other" % (EC, OP)))
        gear = _class(mod, "SSP_CEL_VALVE_ACTUATOR").find("{%s}ECCustomAttributes/{%s}CREATION_ATTRIBUTE" % (EC, OP))
        self.assertEqual(gear.find("{%s}CLASS_NAME" % OP).text, "CelValveActuatorComponent")
        self.assertEqual(gear.find("{%s}HANDLER_TYPE" % OP).text, "Topwork")
        stock = _class(mod, "GEARBOX_OPERATOR").find("{%s}ECCustomAttributes/{%s}CREATION_ATTRIBUTE" % (EC, OP))
        self.assertEqual(stock.find("{%s}CLASS_NAME" % OP).text, "GearBoxOperatorScript", "stock class untouched")

        iso = _parse(self.ws.path("ISO"))
        fallback = 'this.NAME & "-" & this.NUMBER'
        support = _class(iso, "SUPPORT_LOCATION")
        tag = support.find(".//{%s}BOM_ATTR_STRUCT[{%s}NAME='IE_TAG']/{%s}ECX_VALUE" % (ISO, ISO, ISO))
        self.assertEqual(tag.text, iso_tag_expression(fallback))
        for t in ("SINGLE_PIPE_TRUNNION", "SSP_PIPE_CLAMP"):
            tag = _class(iso, t).find(".//{%s}BOM_ATTR_STRUCT[{%s}NAME='IE_TAG']/{%s}ECX_VALUE" % (ISO, ISO, ISO))
            self.assertEqual(tag.text, "this.ALIAS", t)
        base = _class(iso, "PLANT_BASE_OBJECT").find(".//{%s}ECX_VALUE" % ISO)
        self.assertEqual(base.text, fallback, "base labels untouched")

        after = self.ws.snapshot()
        again = load_plan(self.ws.schema, "all")
        self.assertTrue(again.nothing_to_do)
        with self.assertRaises(PatchError):
            apply_plan(again, self.ws.backup, check_processes=False)
        self.assertEqual(after, self.ws.snapshot())
        self.assertEqual(len(os.listdir(self.ws.backup)), 1, "nothing-to-do must not create a new backup")

        log = _read(result.log_path).decode("utf-8-sig")
        self.assertIn("修改后第", log)
        self.assertIn("ECClass[@typeName='SINGLE_PIPE_TRUNNION']", log)
        self.assertIn("ASSEMBLY_NAME：Bentley.Building.Mechanical.ComponentLibrary → SteelSectionProbe", log)
        self.assertTrue(os.path.isfile(result.receipt_path))

    def test_each_feature_then_all_installed(self):
        for feature in ("valve_actuator", "iso_tag", "pipe_clamp", "trunnion"):
            _apply(self.ws, feature)
            self.assertTrue(load_plan(self.ws.schema, feature).nothing_to_do, feature)
        self.assertTrue(load_plan(self.ws.schema, "all").nothing_to_do)

    def test_partial_install_completes_missing_half(self):
        _apply(self.ws, "valve_actuator")
        backup = os.path.join(self.ws.backup, os.listdir(self.ws.backup)[0], NAMES["MOD"] + ".bak")
        shutil.copyfile(backup, self.ws.path("MOD"))
        plan = load_plan(self.ws.schema, "valve_actuator")
        self.assertEqual([(i.file_key, i.status) for i in plan.items], [("OP3D", "installed"), ("MOD", "add")])

    def test_conflicts_block_without_writing(self):
        _apply(self.ws, "all")
        path = self.ws.path("MOD")
        data = _read(path)
        marker = b'<ECClass typeName="SSP_PIPE_CLAMP"'
        start = data.index(marker)
        tampered = data[:start] + data[start:].replace(b"NativePipeSupportComponent", b"ProjectCustomComponent", 1)
        with open(path, "wb") as stream:
            stream.write(tampered)
        iso = self.ws.path("ISO")
        iso_data = _read(iso)
        start = iso_data.index(b'<ECClass typeName="SINGLE_PIPE_TRUNNION"')
        with open(iso, "wb") as stream:
            stream.write(iso_data[:start] + iso_data[start:].replace(b"this.ALIAS", b"this.NAME", 1))
        before = self.ws.snapshot()
        for feature in ("pipe_clamp", "trunnion", "all"):
            plan = load_plan(self.ws.schema, feature)
            self.assertTrue(plan.blocked, feature)
            with self.assertRaises(PatchError):
                apply_plan(plan, self.ws.backup, check_processes=False)
        self.assertEqual(before, self.ws.snapshot())

    def test_trunnion_refuses_other_plugin_component(self):
        path = self.ws.path("MOD")
        data = _read(path)
        start = data.index(b'<ECClass typeName="SINGLE_PIPE_TRUNNION"')
        part = data[start:].replace(b"Bentley.Building.Mechanical.ComponentLibrary</ASSEMBLY_NAME>",
                                    b"SteelSectionProbe</ASSEMBLY_NAME>", 1)
        with open(path, "wb") as stream:
            stream.write(data[:start] + part)
        plan = load_plan(self.ws.schema, "trunnion")
        self.assertTrue(any(i.status == "conflict" and "SINGLE_PIPE_TRUNNION" in i.message for i in plan.items))

    def test_backup_folder_rules(self):
        plan = load_plan(self.ws.schema, "all")
        with self.assertRaises(PatchError):
            apply_plan(plan, "", check_processes=False)
        with self.assertRaises(PatchError):
            apply_plan(plan, os.path.join(self.ws.schema, "bak"), check_processes=False)
        self.assertFalse(os.path.exists(os.path.join(self.ws.schema, "bak")))

    def test_changed_after_check_is_refused(self):
        plan = load_plan(self.ws.schema, "all")
        with open(self.ws.path("MOD"), "ab") as stream:
            stream.write(b"\r\n")
        before = self.ws.snapshot()
        with self.assertRaises(PatchError):
            apply_plan(plan, self.ws.backup, check_processes=False)
        self.assertEqual(before, self.ws.snapshot())

    def test_rollback_when_a_write_fails(self):
        before = self.ws.snapshot()
        os.chmod(self.ws.path("ISO"), stat.S_IREAD)
        plan = load_plan(self.ws.schema, "all")
        with self.assertRaises(PatchError) as raised:
            apply_plan(plan, self.ws.backup, check_processes=False)
        self.assertIn("已回滚", str(raised.exception))
        self.assertEqual(before, self.ws.snapshot())

    def test_missing_file_and_wrong_schema(self):
        os.remove(self.ws.path("ISO"))
        self.assertTrue(load_plan(self.ws.schema, "trunnion").blocked)
        self.assertFalse(load_plan(self.ws.schema, "valve_actuator").blocked, "actuator does not need ISO")
        shutil.copyfile(self.ws.path("MOD"), self.ws.path("ISO"))
        self.assertTrue(load_plan(self.ws.schema, "iso_tag").blocked)

    def test_check_log_lists_every_item(self):
        plan = load_plan(self.ws.schema, "all")
        log = format_log(plan)
        self.assertIn("只读检查", log)
        self.assertEqual(log.count("[新增]") + log.count("[修改]"), len(plan.pending))


class _Run(object):
    def __init__(self, completed):
        self.returncode = completed.returncode
        self.stdout = self._decode(completed.stdout)
        self.stderr = self._decode(completed.stderr)

    @staticmethod
    def _decode(data):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("oem", errors="replace")


def _powershell(*args):
    return _Run(subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"] + list(args),
                               capture_output=True))


@unittest.skipUnless(all(os.path.isfile(p) for p in REAL_FIXTURES.values()), "原始 Schema 备份不存在")
class RealSchemaParityTests(unittest.TestCase):
    def setUp(self):
        self.python_ws = Workspace(REAL_FIXTURES)
        self.ps_ws = Workspace(REAL_FIXTURES)

    def tearDown(self):
        self.python_ws.cleanup()
        self.ps_ws.cleanup()

    def test_same_result_as_powershell_and_mutual_recognition(self):
        original = self.python_ws.snapshot()
        plan, result = _apply(self.python_ws, "all")
        self.assertEqual(len(result.files), 3)
        for key in NAMES:
            before, after = original[key], _read(self.python_ws.path(key))
            self.assertEqual(after[:3], before[:3], "BOM state preserved")
            self.assertEqual(after.count(b"\n"), after.count(b"\r\n"), "CRLF preserved")
            self.assertLess(len(after) - len(before), 20000, "only additions expected")

        run = _powershell(PS_INSTALL, "-SchemaDirectory", self.ps_ws.schema, "-Features", "All",
                          "-BackupDirectory", self.ps_ws.backup, "-Apply")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        run = _powershell(PS_ISOTAG, "-SchemaPath", self.ps_ws.path("ISO"), "-BackupDirectory", self.ps_ws.backup, "-Apply")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

        # PowerShell 脚本整份重写时把属性里的 &#xA; 写成字面换行（重读后变空格），比对时按属性空白归一。
        for key in NAMES:
            ours, theirs = _parse(self.python_ws.path(key)), _parse(self.ps_ws.path(key))
            for element in list(ours.iter()) + list(theirs.iter()):
                for name, value in element.attrib.items():
                    element.attrib[name] = " ".join(value.split())
            self.assertTrue(same_structure(ours, theirs), "%s differs from PowerShell result" % key)
        self.assertIn(b"&#xA;", _read(self.python_ws.path("OP3D")), "python keeps untouched character references")

        self.assertTrue(load_plan(self.ps_ws.schema, "all").nothing_to_do, "python must recognise PowerShell install")
        preview = _powershell(PS_INSTALL, "-SchemaDirectory", self.python_ws.schema, "-Features", "All")
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertIn("无需修改", preview.stdout, preview.stdout + preview.stderr)
        preview = _powershell(PS_ISOTAG, "-SchemaPath", self.python_ws.path("ISO"))
        self.assertIn("无需修改", preview.stdout, preview.stdout + preview.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
