"""各增补项的判定与修改规则，与 Deployment 下 PowerShell 安装脚本保持一致。"""
from collections import OrderedDict

from .xmlspan import (INDENT, Patch, XmlFormatError, append_child, child, children, clone_text, path,
                      same_structure, set_text, to_element)

OP3D = "OP3D"
MOD = "MOD"
ISO = "ISO"
SCHEMA_FILES = OrderedDict([
    (OP3D, ("OpenPlant_3D", "OpenPlant_3D.01.08.ecschema.xml")),
    (MOD, ("OpenPlant_3D_Supplemental_Modeling", "OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml")),
    (ISO, ("OpenPlant_3D_Supplemental_Isometrics_Isoextractor",
           "OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml")),
])
OP_NS = "OpenPlant_CustomAttributes.08.11"
ISO_NS = "OpenPlant_IsoExtractor_Custom_Attributes.01.08"

PLUGIN = "SteelSectionProbe"
SUPPORT_HANDLER = "NativePipeSupportComponent"
TRUNNION_CLASSES = ("SINGLE_PIPE_TRUNNION", "DOUBLE_PIPE_TRUNNION", "SIMPLE_ELBOW_SUPPORT")
PIPE_CLAMP_CLASS = "SSP_PIPE_CLAMP"
ACTUATOR_CLASS = "SSP_CEL_VALVE_ACTUATOR"
ACTUATOR_HANDLER = "CelValveActuatorComponent"
# 显示名沿用已安装工作集中的原值，否则已装过的工作集会被误判为冲突。
ACTUATOR_LABEL = "CEL GEARBOX_OPERATOR Callback Check"
ACTUATOR_PROPERTIES = (("SSP_CEL_VERSION", "int"), ("SSP_CEL_NAME", "string"), ("SSP_CEL_SOURCE", "string"),
                       ("SSP_CEL_SHA256", "string"), ("SSP_CEL_DATA", "binary"), ("SSP_CEL_TOKEN", "string"))
# KB0098072：PLANT_BASE_OBJECT 上这三个自定义属性必须带子节点，空壳会让 ISO 取属性时拿到 DBNull。
ISO_SCHEMA_CLASS = "PLANT_BASE_OBJECT"
ISO_SCHEMA_NODES = (
    ("IE_Mappings", ("END_POINT_ORDER_MAP", "OVR_END_PREPARATION")),
    ("L00_LABEL_SECTION_LABELS", ("LBL_SECT_LABELS",)),
    ("SPECIFIC_BOM_LABELS", ("ATTRIBUTES",)),
)

INSTALLED = "installed"
ADD = "add"
MODIFY = "modify"
CONFLICT = "conflict"
ERROR = "error"


class Item(object):
    """一个增补项在一份文件中的判定结果。"""

    def __init__(self, feature, file_key, target, status, message, patches=None, details=None, locate=None):
        self.feature = feature
        self.file_key = file_key
        self.target = target
        self.status = status
        self.message = message
        self.patches = patches or []
        self.details = details or []
        self.locate = locate or []
        self.original_line = None
        self.new_line = None


class Context(object):
    def __init__(self, feature, docs):
        self.feature = feature
        self.docs = docs
        self.items = []
        self._order = 0

    def order(self):
        self._order += 1
        return self._order

    def add(self, *args, **kwargs):
        item = Item(self.feature, *args, **kwargs)
        self.items.append(item)
        return item


def _class(doc, type_name):
    return child(doc.root, "ECClass", doc.root.ns, typeName=type_name)


def _class_path(type_name, *rest):
    text = "ECClass[@typeName='%s']" % type_name
    return "/".join([text] + list(rest))


def _creation(doc, type_name):
    ec = doc.root.ns
    return path(_class(doc, type_name), ("ECCustomAttributes", ec), ("CREATION_ATTRIBUTE", OP_NS)) \
        if _class(doc, type_name) is not None else None


def _bom_labels(doc, cls):
    return path(cls, ("ECCustomAttributes", doc.root.ns), ("BOM_LABELS", ISO_NS)) if cls is not None else None


def _ie_tags(labels):
    tags = []
    other = child(labels, "OTH_ATTRIBUTES", ISO_NS)
    if other is None:
        return tags
    for struct in children(other, "BOM_ATTR_STRUCT", ISO_NS):
        name = child(struct, "NAME", ISO_NS)
        if name is not None and name.text == "IE_TAG":
            tags.extend(children(struct, "ECX_VALUE", ISO_NS))
    return tags


def _wrap_attributes(inner):
    return lambda ind: "<ECCustomAttributes>\n" + ind + INDENT + inner + "\n" + ind + "</ECCustomAttributes>"


# 新增顶层类与 PowerShell 安装脚本逐字一致（不加缩进），因为脚本按 OuterXml 原文判断是否已安装。
def _wrap_class(type_name, domain, inner):
    text = ('<ECClass typeName="%s" isDomainClass="%s"><ECCustomAttributes>%s</ECCustomAttributes></ECClass>'
            % (type_name, domain, inner))
    return lambda ind: text


def _append_into_attributes(ctx, doc, cls, inner):
    """inner 放进 cls 的 ECCustomAttributes；没有该节点时连同节点一起追加到类末尾。"""
    attributes = child(cls, "ECCustomAttributes", doc.root.ns)
    if attributes is None:
        return append_child(doc, cls, _wrap_attributes(inner), ctx.order())
    return append_child(doc, attributes, lambda ind: inner, ctx.order())


def _fields(creation, names):
    return dict((name, child(creation, name, OP_NS)) for name in names)


def _new_root_class(ctx, file_key, type_name, build, expected_fragment):
    """新增顶层类：已存在且一致视为已安装，已存在但不同视为冲突。"""
    doc = ctx.docs[file_key]
    existing = _class(doc, type_name)
    target = _class_path(type_name)
    if existing is not None:
        current = to_element(clone_text(doc, existing), doc.root.ns)
        expected = to_element(expected_fragment, doc.root.ns)
        if same_structure(current, expected):
            ctx.add(file_key, target, INSTALLED, "已具备 %s" % type_name)
        else:
            ctx.add(file_key, target, CONFLICT, "已存在 %s 但内容与本工具预期不同，需人工核对，未覆盖。" % type_name)
        return
    patch = append_child(doc, doc.root, build, ctx.order())
    ctx.add(file_key, target, ADD, "新增类 %s" % type_name, [patch], [patch.text.strip("\r\n")],
            [("ECClass", {"typeName": type_name})])


# ---------------------------------------------------------------- 耳轴

def plan_trunnion(ctx):
    for type_name in TRUNNION_CLASSES:
        _trunnion_op3d(ctx, type_name)
        _trunnion_modeling(ctx, type_name)
        _trunnion_iso(ctx, type_name)


def _trunnion_op3d(ctx, type_name):
    doc = ctx.docs[OP3D]
    cls = _class(doc, type_name)
    target = _class_path(type_name, "ECProperty[@propertyName='SSP_RECIPE']")
    if cls is None:
        ctx.add(OP3D, target, ERROR, "工作集缺少自带耳轴类 %s。" % type_name)
        return
    prop = child(cls, "ECProperty", doc.root.ns, propertyName="SSP_RECIPE")
    if prop is None:
        fragment = '<ECProperty propertyName="SSP_RECIPE" typeName="string" />'
        patch = append_child(doc, cls, lambda ind: fragment, ctx.order())
        ctx.add(OP3D, target, ADD, "%s 增加字段 SSP_RECIPE(string)" % type_name, [patch], [fragment],
                [("ECClass", {"typeName": type_name}), ("ECProperty", {"propertyName": "SSP_RECIPE"})])
    elif prop.get("typeName") != "string":
        ctx.add(OP3D, target, CONFLICT, "%s.SSP_RECIPE 已存在但类型不是 string，禁止覆盖。" % type_name)
    else:
        ctx.add(OP3D, target, INSTALLED, "已具备 %s.SSP_RECIPE" % type_name)


def _trunnion_modeling(ctx, type_name):
    doc = ctx.docs[MOD]
    cls = _class(doc, type_name)
    target = _class_path(type_name, "ECCustomAttributes", "CREATION_ATTRIBUTE")
    locate = [("ECClass", {"typeName": type_name}), ("ECCustomAttributes", {}), ("CREATION_ATTRIBUTE", {})]
    if cls is None:
        ctx.add(MOD, target, ERROR, "工作集缺少自带耳轴类 %s。" % type_name)
        return
    stock = _creation(doc, "SUPPORT_LOCATION")
    if stock is None:
        ctx.add(MOD, target, ERROR, "SUPPORT_LOCATION 缺 CREATION_ATTRIBUTE，无法克隆。")
        return
    attributes = child(cls, "ECCustomAttributes", doc.root.ns)
    creation = child(attributes, "CREATION_ATTRIBUTE", OP_NS)
    source = creation if creation is not None else stock
    fields = _fields(source, ("ASSEMBLY_NAME", "NAMESPACE", "CLASS_NAME", "HANDLER_TYPE", "PLACEMENT_TOOL"))
    if any(fields[name] is None for name in ("ASSEMBLY_NAME", "NAMESPACE", "CLASS_NAME", "HANDLER_TYPE")):
        ctx.add(MOD, target, ERROR, "%s CREATION_ATTRIBUTE 字段不完整。" % type_name)
        return
    assembly, namespace, class_name = (fields[n].text for n in ("ASSEMBLY_NAME", "NAMESPACE", "CLASS_NAME"))
    if creation is not None and assembly == PLUGIN and namespace == PLUGIN and class_name == SUPPORT_HANDLER:
        if fields["HANDLER_TYPE"].text != "Support":
            ctx.add(MOD, target, CONFLICT, "%s 已指向本插件但 HANDLER_TYPE 不是 Support。" % type_name)
        else:
            ctx.add(MOD, target, INSTALLED, "已具备 %s → %s" % (type_name, SUPPORT_HANDLER))
        return
    if creation is not None and assembly == PLUGIN and class_name != SUPPORT_HANDLER:
        ctx.add(MOD, target, CONFLICT, "%s 已有其它 %s 组件 %s，禁止覆盖。" % (type_name, PLUGIN, class_name))
        return
    wanted = OrderedDict([("ASSEMBLY_NAME", PLUGIN), ("NAMESPACE", PLUGIN), ("CLASS_NAME", SUPPORT_HANDLER),
                          ("HANDLER_TYPE", "Support")])
    if fields["PLACEMENT_TOOL"] is not None:
        wanted["PLACEMENT_TOOL"] = "PipeSupportPlacementTool"
    if creation is None:
        clone = clone_text(doc, stock, dict((fields[n], v) for n, v in wanted.items()))
        patch = _append_into_attributes(ctx, doc, cls, clone)
        ctx.add(MOD, target, ADD, "%s 新增 CREATION_ATTRIBUTE（克隆 SUPPORT_LOCATION）→ %s" % (type_name, SUPPORT_HANDLER),
                [patch], [clone], locate)
        return
    patches, details = [], []
    for name, value in wanted.items():
        if fields[name].text != value:
            patches.append(set_text(doc, fields[name], value, ctx.order()))
            details.append("%s：%s → %s" % (name, fields[name].text, value))
    ctx.add(MOD, target, MODIFY, "%s CREATION_ATTRIBUTE 改为指向 %s" % (type_name, SUPPORT_HANDLER), patches, details, locate)


def _trunnion_iso(ctx, type_name):
    doc = ctx.docs[ISO]
    cls = _class(doc, type_name)
    target = _class_path(type_name, "ECCustomAttributes", "BOM_LABELS")
    if cls is None:
        ctx.add(ISO, target, ERROR, "工作集缺少自带耳轴类 %s。" % type_name)
        return
    labels = _bom_labels(doc, cls)
    if labels is not None:
        tags = _ie_tags(labels)
        if tags and tags[0].text == "this.ALIAS":
            ctx.add(ISO, target, INSTALLED, "已具备 %s IE_TAG=this.ALIAS" % type_name)
        else:
            ctx.add(ISO, target, CONFLICT, "%s 已有项目自定义 BOM 标签，禁止覆盖；请人工将 IE_TAG 改为 this.ALIAS。" % type_name)
        return
    base = _bom_labels(doc, _class(doc, "PLANT_BASE_OBJECT"))
    if base is None:
        ctx.add(ISO, target, ERROR, "PLANT_BASE_OBJECT 缺 BOM_LABELS。")
        return
    tags = _ie_tags(base)
    if not tags:
        ctx.add(ISO, target, ERROR, "PLANT_BASE_OBJECT 默认 IE_TAG 缺失。")
        return
    clone = clone_text(doc, base, {tags[0]: "this.ALIAS"})
    patch = _append_into_attributes(ctx, doc, cls, clone)
    ctx.add(ISO, target, ADD, "%s 新增 BOM_LABELS（克隆 PLANT_BASE_OBJECT，IE_TAG=this.ALIAS）" % type_name,
            [patch], [clone], [("ECClass", {"typeName": type_name}), ("ECCustomAttributes", {}), ("BOM_LABELS", {})])


# ---------------------------------------------------------------- 正式管夹

def plan_pipe_clamp(ctx):
    target = _class_path(PIPE_CLAMP_CLASS)
    op3d = ctx.docs[OP3D]
    if _class(op3d, "SUPPORT_LOCATION") is None:
        ctx.add(OP3D, target, ERROR, "OpenPlant_3D 缺少基类 SUPPORT_LOCATION。")
    else:
        fragment = ('<ECClass typeName="%s" isDomainClass="True" displayLabel="Pipe Clamp">'
                    '<BaseClass>SUPPORT_LOCATION</BaseClass>'
                    '<ECProperty propertyName="SSP_RECIPE" typeName="string" /></ECClass>' % PIPE_CLAMP_CLASS)
        _new_root_class(ctx, OP3D, PIPE_CLAMP_CLASS, lambda ind: fragment, fragment)

    modeling = ctx.docs[MOD]
    stock = _creation(modeling, "SUPPORT_LOCATION")
    fields = _fields(stock, ("ASSEMBLY_NAME", "NAMESPACE", "CLASS_NAME", "HANDLER_TYPE")) if stock is not None else {}
    if stock is None:
        ctx.add(MOD, target, ERROR, "SUPPORT_LOCATION 缺 CREATION_ATTRIBUTE。")
    elif any(fields[n] is None for n in ("ASSEMBLY_NAME", "NAMESPACE", "CLASS_NAME")):
        ctx.add(MOD, target, ERROR, "SUPPORT_LOCATION CREATION_ATTRIBUTE 字段不完整。")
    elif fields["HANDLER_TYPE"] is None or fields["HANDLER_TYPE"].text != "Support":
        ctx.add(MOD, target, ERROR, "SUPPORT_LOCATION 的 HANDLER_TYPE 不是 Support。")
    else:
        clone = clone_text(modeling, stock, {fields["ASSEMBLY_NAME"]: PLUGIN, fields["NAMESPACE"]: PLUGIN,
                                             fields["CLASS_NAME"]: SUPPORT_HANDLER})
        build = _wrap_class(PIPE_CLAMP_CLASS, "False", clone)
        _new_root_class(ctx, MOD, PIPE_CLAMP_CLASS, build, build(""))

    iso = ctx.docs[ISO]
    base = _bom_labels(iso, _class(iso, "PLANT_BASE_OBJECT"))
    tags = _ie_tags(base) if base is not None else []
    if base is None:
        ctx.add(ISO, target, ERROR, "PLANT_BASE_OBJECT 缺 BOM_LABELS。")
    elif len(tags) != 1:
        ctx.add(ISO, target, ERROR, "PLANT_BASE_OBJECT 的 IE_TAG 缺失或不唯一。")
    else:
        build = _wrap_class(PIPE_CLAMP_CLASS, "False", clone_text(iso, base, {tags[0]: "this.ALIAS"}))
        _new_root_class(ctx, ISO, PIPE_CLAMP_CLASS, build, build(""))


# ---------------------------------------------------------------- 轴测图引注

def iso_tag_expression(fallback):
    return 'IIf(IM.Match(this.DEVICE_TYPE_CODE,"SSPPC"),IM.GetValue("ALIAS",(%s)),(%s))' % (fallback, fallback)


def plan_iso_tag(ctx):
    doc = ctx.docs[ISO]
    target = _class_path("SUPPORT_LOCATION", "ECCustomAttributes", "BOM_LABELS")
    locate = [("ECClass", {"typeName": "SUPPORT_LOCATION"}), ("ECCustomAttributes", {}), ("BOM_LABELS", {})]
    base = _bom_labels(doc, _class(doc, "PLANT_BASE_OBJECT"))
    if base is None:
        ctx.add(ISO, target, ERROR, "未找到 PLANT_BASE_OBJECT 默认 BOM 标签，停止写入。")
        return
    tags = _ie_tags(base)
    if len(tags) != 1 or not tags[0].text.strip():
        ctx.add(ISO, target, ERROR, "默认 IE_TAG 映射不唯一或为空，停止写入。")
        return
    expression = iso_tag_expression(tags[0].text)
    clone = clone_text(doc, base, {tags[0]: expression})
    cls = _class(doc, "SUPPORT_LOCATION")
    if cls is None:
        build = _wrap_class("SUPPORT_LOCATION", "False", clone)
        patch = append_child(doc, doc.root, build, ctx.order())
        ctx.add(ISO, target, ADD, "新增类 SUPPORT_LOCATION 及 BOM_LABELS（DEVICE_TYPE_CODE=SSPPC 时引注取 ALIAS）",
                [patch], ["IE_TAG = " + expression, patch.text.strip("\r\n")], locate)
        return
    existing = _bom_labels(doc, cls)
    if existing is not None:
        old = _ie_tags(existing)
        if old and old[0].text == expression:
            ctx.add(ISO, target, INSTALLED, "已具备管夹管架编号引注映射")
        else:
            ctx.add(ISO, target, CONFLICT, "SUPPORT_LOCATION 已有项目自定义 BOM 标签，禁止覆盖；请人工合并 IE_TAG 条件表达式。")
        return
    patch = _append_into_attributes(ctx, doc, cls, clone)
    ctx.add(ISO, target, ADD, "SUPPORT_LOCATION 增加 BOM_LABELS（DEVICE_TYPE_CODE=SSPPC 时引注取 ALIAS）",
            [patch], ["IE_TAG = " + expression, clone], locate)


# ---------------------------------------------------------------- 自定义执行机构

def plan_valve_actuator(ctx):
    target = _class_path(ACTUATOR_CLASS)
    op3d = ctx.docs[OP3D]
    if _class(op3d, "GEARBOX_OPERATOR") is None:
        ctx.add(OP3D, target, ERROR, "OpenPlant_3D 缺少基类 GEARBOX_OPERATOR。")
    else:
        fragment = ('<ECClass typeName="%s" isDomainClass="True" displayLabel="%s"><BaseClass>GEARBOX_OPERATOR</BaseClass>'
                    % (ACTUATOR_CLASS, ACTUATOR_LABEL)
                    + "".join('<ECProperty propertyName="%s" typeName="%s" />' % p for p in ACTUATOR_PROPERTIES)
                    + "</ECClass>")
        _new_root_class(ctx, OP3D, ACTUATOR_CLASS, lambda ind: fragment, fragment)

    modeling = ctx.docs[MOD]
    creation = _creation(modeling, "GEARBOX_OPERATOR")
    if creation is None:
        ctx.add(MOD, target, ERROR, "GEARBOX_OPERATOR 缺 CREATION_ATTRIBUTE。")
        return
    fields = _fields(creation, ("ASSEMBLY_NAME", "NAMESPACE", "CLASS_NAME", "HANDLER_TYPE", "PLACEMENT_TOOL"))
    if any(f is None for f in fields.values()):
        ctx.add(MOD, target, ERROR, "GEARBOX_OPERATOR CREATION_ATTRIBUTE 字段不完整。")
        return
    if fields["HANDLER_TYPE"].text != "Topwork" or fields["PLACEMENT_TOOL"].text != "TopworksPlacementTool":
        ctx.add(MOD, target, ERROR, "GEARBOX_OPERATOR 不是预期的原生 Topwork/TopworksPlacementTool 配置。")
        return
    clone = clone_text(modeling, creation, {fields["ASSEMBLY_NAME"]: PLUGIN, fields["NAMESPACE"]: PLUGIN,
                                            fields["CLASS_NAME"]: ACTUATOR_HANDLER})
    build = _wrap_class(ACTUATOR_CLASS, "False", clone)
    _new_root_class(ctx, MOD, ACTUATOR_CLASS, build, build(""))


# ---------------------------------------------------------------- 轴测图 Schema（KB0098072）

def _iso_node(type_name, required):
    """生成一个完整的自定义属性节点；缩进由 append_child 传入的绝对缩进决定。"""
    def build(indent):
        inner = "".join("\n%s%s<%s />" % (indent, INDENT, name) for name in required)
        return '<%s xmlns="%s">%s\n%s</%s>' % (type_name, ISO_NS, inner, indent, type_name)
    return build


def _iso_rebuild(doc, node, required, order):
    """保留原开始标签（含 xmlns），按官方顺序重建整个节点；调用方已保证没有项目自定义子节点。"""
    indent = doc.line_indent(node.start)
    raw = doc.data[node.start:node.start_end].decode("utf-8")
    start = raw.rstrip()[:-2].rstrip() + ">" if raw.rstrip().endswith("/>") else raw
    inner = "".join("\n%s<%s />" % (indent + INDENT, name) for name in required)
    return Patch(node.start, node.end - node.start, start + inner + "\n%s</%s>" % (indent, node.qname), order)


def plan_iso_schema(ctx):
    """只检查所选目录里的 Isoextractor：三个节点缺失或空壳时补必需子节点；项目自定义一律冲突。"""
    doc = ctx.docs[ISO]
    base = _class_path(ISO_SCHEMA_CLASS, "ECCustomAttributes")
    cls = _class(doc, ISO_SCHEMA_CLASS)
    if cls is None:
        ctx.add(ISO, base, ERROR, "工作集缺少 %s 类。" % ISO_SCHEMA_CLASS)
        return
    attrs = child(cls, "ECCustomAttributes", doc.root.ns)
    if attrs is None:
        ctx.add(ISO, base, ERROR, "%s 缺少 ECCustomAttributes。" % ISO_SCHEMA_CLASS)
        return
    for type_name, required in ISO_SCHEMA_NODES:
        target = _class_path(ISO_SCHEMA_CLASS, "ECCustomAttributes", type_name)
        found = children(attrs, type_name)
        if len(found) > 1:
            ctx.add(ISO, target, CONFLICT, "%s 重复出现 %d 次，禁止自动处理。" % (type_name, len(found)))
            continue
        if found and found[0].ns != ISO_NS:
            ctx.add(ISO, target, CONFLICT, "%s 的命名空间不是 %s，禁止改写。" % (type_name, ISO_NS))
            continue
        if not found:
            patch = append_child(doc, attrs, _iso_node(type_name, required), ctx.order())
            ctx.add(ISO, target, ADD, "新增 %s（%s）" % (type_name, "、".join(required)),
                    [patch], [patch.text.strip("\r\n")],
                    [("ECClass", {"typeName": ISO_SCHEMA_CLASS}), ("ECCustomAttributes", {}), (type_name, {})])
            continue
        node = found[0]
        actual = [item.local for item in node.children]
        extras = [name for name in actual if name not in required]
        if extras:
            ctx.add(ISO, target, CONFLICT, "%s 含有非官方子节点 %s，禁止覆盖。" % (type_name, "、".join(extras)))
            continue
        if any(item.ns != ISO_NS for item in node.children):
            ctx.add(ISO, target, CONFLICT, "%s 的子节点命名空间不一致，禁止改写。" % type_name)
            continue
        rewritten = [item.local for item in node.children if item.children or item.text.strip()]
        if rewritten:
            ctx.add(ISO, target, CONFLICT, "%s 的子节点 %s 已有项目内容，禁止覆盖。" % (type_name, "、".join(rewritten)))
            continue
        missing = [name for name in required if name not in actual]
        if not missing:
            ctx.add(ISO, target, INSTALLED, "已具备 %s（%s）" % (type_name, "、".join(required)))
            continue
        patch = _iso_rebuild(doc, node, required, ctx.order())
        ctx.add(ISO, target, ADD, "%s 补齐子节点 %s" % (type_name, "、".join(missing)),
                [patch], [patch.text.strip("\r\n")],
                [("ECClass", {"typeName": ISO_SCHEMA_CLASS}), ("ECCustomAttributes", {}), (type_name, {})])


class Feature(object):
    def __init__(self, key, label, description, files, planners):
        self.key = key
        self.label = label
        self.description = description
        self.files = files
        self.planners = planners


_TRUNNION = Feature(
    "trunnion", "增加耳轴",
    "OpenPlant_3D：SINGLE/DOUBLE_PIPE_TRUNNION、SIMPLE_ELBOW_SUPPORT 各加 SSP_RECIPE 字段；\n"
    "Modeling：这三类的创建属性改为指向本插件 NativePipeSupportComponent；\n"
    "Isoextractor：这三类 IE_TAG=this.ALIAS。\n"
    "注意：改的是 OPM 自带类，改后该工作集所有耳轴（含原生工具放的）都需要本插件才能编辑。",
    (OP3D, MOD, ISO), (plan_trunnion,))
_PIPE_CLAMP = Feature(
    "pipe_clamp", "增加正式管夹",
    "三份 Schema 各新增隔离类 SSP_PIPE_CLAMP（继承 SUPPORT_LOCATION）：\n"
    "OpenPlant_3D 加 SSP_RECIPE 字段；Modeling 创建属性指向本插件 NativePipeSupportComponent；Isoextractor IE_TAG=this.ALIAS。",
    (OP3D, MOD, ISO), (plan_pipe_clamp,))
_ISO_TAG = Feature(
    "iso_tag", "修改轴测图出图",
    "Isoextractor：SUPPORT_LOCATION 增加 BOM_LABELS，DEVICE_TYPE_CODE=SSPPC 时引注取 ALIAS（管架编号），\n"
    "否则保持原表达式。主要用于旧的非参数化管夹件。",
    (ISO,), (plan_iso_tag,))
_ISO_SCHEMA = Feature(
    "iso_schema", "修复轴测图 Schema",
    "Isoextractor：PLANT_BASE_OBJECT 的 IE_Mappings、L00_LABEL_SECTION_LABELS、SPECIFIC_BOM_LABELS\n"
    "按 KB0098072 补齐必需子节点（空壳会导致 ISO 取属性时 DBNull）。\n"
    "只检查所选目录内的这一份 Schema；不改命名空间、不覆盖项目自定义。",
    (ISO,), (plan_iso_schema,))
_ACTUATOR = Feature(
    "valve_actuator", "增加执行机构",
    "OpenPlant_3D：新增 SSP_CEL_VALVE_ACTUATOR（继承 GEARBOX_OPERATOR）及 6 个 CEL 快照字段；\n"
    "Modeling：创建属性复制自 GEARBOX_OPERATOR，处理器改为本插件 CelValveActuatorComponent。Isoextractor 不改。",
    (OP3D, MOD), (plan_valve_actuator,))
_ALL = Feature(
    "all", "全部", "依次执行：增加耳轴、增加正式管夹、修改轴测图出图、增加执行机构（不含修复轴测图 Schema）。",
    (OP3D, MOD, ISO), (plan_trunnion, plan_pipe_clamp, plan_iso_tag, plan_valve_actuator))

FEATURES = OrderedDict((f.key, f) for f in (_TRUNNION, _PIPE_CLAMP, _ISO_TAG, _ISO_SCHEMA, _ACTUATOR, _ALL))
_PLANNER_LABELS = {plan_trunnion: _TRUNNION.label, plan_pipe_clamp: _PIPE_CLAMP.label,
                   plan_iso_tag: _ISO_TAG.label, plan_iso_schema: _ISO_SCHEMA.label,
                   plan_valve_actuator: _ACTUATOR.label}


def plan_feature(feature, docs):
    """返回各增补项的判定；不修改 docs。"""
    ctx = Context(feature.key, docs)
    for planner in feature.planners:
        ctx.feature = _PLANNER_LABELS[planner]
        try:
            planner(ctx)
        except XmlFormatError as error:
            ctx.add(feature.files[0], "-", ERROR, str(error))
    return ctx.items
