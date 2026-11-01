"""按字节位置读取 XML，只在指定位置插入/替换，其余字节保持原样。"""
import xml.etree.ElementTree as ET
import xml.parsers.expat

INDENT = "    "
_XML_NS = "http://www.w3.org/XML/1998/namespace"


class XmlFormatError(Exception):
    pass


class Node(object):
    __slots__ = ("qname", "local", "prefix", "ns", "attrs", "nsdecl", "scope", "start", "start_end",
                 "end_start", "end", "line", "children", "parent", "text_parts")

    def __init__(self, qname, attrs, scope, nsdecl, parent):
        prefix, _, local = qname.rpartition(":")
        self.qname = qname
        self.prefix = prefix
        self.local = local
        self.attrs = attrs
        self.nsdecl = nsdecl
        self.scope = scope
        self.ns = scope.get(prefix, "") if prefix else scope.get("", "")
        self.parent = parent
        self.children = []
        self.text_parts = []
        self.start = self.start_end = self.end = 0
        self.end_start = None
        self.line = 0

    @property
    def self_closing(self):
        return self.end_start is None

    @property
    def text(self):
        return "".join(self.text_parts)

    def get(self, name, default=None):
        return self.attrs.get(name, default)


class Patch(object):
    __slots__ = ("offset", "length", "text", "order")

    def __init__(self, offset, length, text, order=0):
        self.offset = offset
        self.length = length
        self.text = text
        self.order = order


def _scan_tag_end(data, pos):
    quote = None
    for i in range(pos, len(data)):
        c = data[i]
        if quote is not None:
            if c == quote:
                quote = None
        elif c in (0x22, 0x27):
            quote = c
        elif c == 0x3E:
            return i + 1
    raise XmlFormatError("标签未闭合（字节 %d）" % pos)


def escape_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def apply_patches(data, patches, newline):
    ordered = sorted(patches, key=lambda p: (p.offset, p.order))
    out = bytearray()
    cursor = 0
    for patch in ordered:
        if patch.offset < cursor:
            raise XmlFormatError("同一位置存在重叠修改（字节 %d），停止写入。" % patch.offset)
        out += data[cursor:patch.offset]
        out += patch.text.replace("\r\n", "\n").replace("\n", newline).encode("utf-8")
        cursor = patch.offset + patch.length
    out += data[cursor:]
    return bytes(out)


class Document(object):
    """一份 Schema 文件：原始字节 + 带字节区间的节点树。"""

    def __init__(self, data, name=""):
        self.data = data
        self.name = name
        self.newline = "\r\n" if b"\r\n" in data else "\n"
        self._check_declaration()
        self.root = self._parse()

    def _check_declaration(self):
        head = self.data[:200].lstrip(b"\xef\xbb\xbf").lower()
        if head.startswith(b"<?xml"):
            end = head.find(b"?>")
            declaration = head[:end]
            if b"encoding" in declaration and b"utf-8" not in declaration and b"utf8" not in declaration:
                raise XmlFormatError("%s 不是 UTF-8 编码，停止处理。" % self.name)
        if self.data.startswith(b"\xff\xfe") or self.data.startswith(b"\xfe\xff"):
            raise XmlFormatError("%s 是 UTF-16 编码，停止处理。" % self.name)

    def _parse(self):
        data = self.data
        parser = xml.parsers.expat.ParserCreate()
        parser.buffer_text = False
        stack = []
        holder = []
        base_scope = {"xml": _XML_NS}

        def start(qname, attrs):
            pos = parser.CurrentByteIndex
            if data[pos:pos + 1] != b"<":
                raise XmlFormatError("%s 无法定位节点 %s 的字节位置。" % (self.name, qname))
            parent = stack[-1] if stack else None
            scope = parent.scope if parent is not None else base_scope
            nsdecl = {}
            for key, value in attrs.items():
                if key == "xmlns":
                    nsdecl[""] = value
                elif key.startswith("xmlns:"):
                    nsdecl[key[6:]] = value
            if nsdecl:
                scope = dict(scope)
                scope.update(nsdecl)
            node = Node(qname, attrs, scope, nsdecl, parent)
            if node.prefix and node.prefix not in scope:
                raise XmlFormatError("%s 第 %d 行使用了未声明的前缀 %s。" % (self.name, parser.CurrentLineNumber, node.prefix))
            node.start = pos
            node.start_end = _scan_tag_end(data, pos)
            node.line = parser.CurrentLineNumber
            if parent is None:
                holder.append(node)
            else:
                parent.children.append(node)
            stack.append(node)

        def end(qname):
            node = stack.pop()
            pos = parser.CurrentByteIndex
            if data[pos:pos + 2] == b"</":
                node.end_start = pos
                node.end = _scan_tag_end(data, pos)
            else:
                node.end_start = None
                node.end = node.start_end

        def chars(text):
            if stack:
                stack[-1].text_parts.append(text)

        parser.StartElementHandler = start
        parser.EndElementHandler = end
        parser.CharacterDataHandler = chars
        try:
            parser.Parse(data, True)
        except xml.parsers.expat.ExpatError as error:
            raise XmlFormatError("%s XML 格式错误：%s" % (self.name, error))
        if not holder:
            raise XmlFormatError("%s 没有根节点。" % self.name)
        return holder[0]

    def raw(self, node):
        return self.data[node.start:node.end].decode("utf-8")

    def line_of(self, offset):
        return self.data.count(b"\n", 0, offset) + 1

    def line_indent(self, pos):
        newline = self.data.rfind(b"\n", 0, pos)
        segment = self.data[newline + 1:pos]
        return segment.decode("utf-8") if segment.strip() == b"" else ""

    def apply(self, patches):
        return apply_patches(self.data, patches, self.newline)


def children(node, local, ns=None, **attrs):
    result = []
    for child_node in node.children:
        if child_node.local != local or (ns is not None and child_node.ns != ns):
            continue
        if all(child_node.attrs.get(k) == v for k, v in attrs.items()):
            result.append(child_node)
    return result


def child(node, local, ns=None, **attrs):
    if node is None:
        return None
    found = children(node, local, ns, **attrs)
    return found[0] if found else None


def path(node, *steps):
    """steps: (local, ns) 依次向下取第一个匹配子节点；任何一级缺失返回 None。"""
    current = node
    for local, ns in steps:
        current = child(current, local, ns)
        if current is None:
            return None
    return current


def append_child(doc, node, build, order=0):
    """把 build(缩进) 生成的片段作为 node 的最后一个子节点插入；片段后续行自带绝对缩进。"""
    node_indent = doc.line_indent(node.start)
    if node.self_closing:
        child_indent = node_indent + INDENT
        close = node.start_end - 2
        if doc.data[close:node.start_end] != b"/>":
            raise XmlFormatError("无法识别自闭合节点 %s。" % node.qname)
        while close > node.start and doc.data[close - 1:close] in (b" ", b"\t", b"\r", b"\n"):
            close -= 1
        text = ">\n" + child_indent + build(child_indent) + "\n" + node_indent + "</" + node.qname + ">"
        return Patch(close, node.start_end - close, text, order)
    if node.children:
        last = node.children[-1]
        child_indent = doc.line_indent(last.start) or node_indent + INDENT
        return Patch(last.end, 0, "\n" + child_indent + build(child_indent), order)
    inner = doc.data[node.start_end:node.end_start]
    child_indent = node_indent + INDENT
    if inner.strip() == b"":
        text = "\n" + child_indent + build(child_indent) + "\n" + node_indent
        return Patch(node.start_end, len(inner), text, order)
    return Patch(node.end_start, 0, build(child_indent), order)


def set_text(doc, node, value, order=0):
    if node.children:
        raise XmlFormatError("节点 %s 含子节点，不能直接改值。" % node.qname)
    escaped = escape_text(value)
    if node.self_closing:
        close = node.start_end - 2
        while close > node.start and doc.data[close - 1:close] in (b" ", b"\t", b"\r", b"\n"):
            close -= 1
        return Patch(close, node.start_end - close, ">" + escaped + "</" + node.qname + ">", order)
    return Patch(node.start_end, node.end_start - node.start_end, escaped, order)


def _undeclared_prefixes(node):
    needed = set()

    def walk(current, declared):
        declared = declared | set(current.nsdecl)
        if current.prefix not in declared and (current.prefix or current.ns):
            needed.add(current.prefix)
        for name in current.attrs:
            if ":" in name:
                prefix = name.split(":", 1)[0]
                if prefix not in ("xmlns", "xml") and prefix not in declared:
                    needed.add(prefix)
        for sub in current.children:
            walk(sub, declared)

    walk(node, set())
    return needed


def clone_text(doc, node, edits=None):
    """复制 node 的原始文本，可同时改若干后代叶子节点的值；必要时补上命名空间声明，保证移到别处仍然等价。"""
    sub = []
    for target, value in (edits or {}).items():
        patch = set_text(doc, target, value)
        sub.append(Patch(patch.offset - node.start, patch.length, patch.text))
    raw = apply_patches(doc.data[node.start:node.end], sub, "\n").decode("utf-8")
    declarations = ""
    for prefix in sorted(_undeclared_prefixes(node)):
        uri = node.scope.get(prefix)
        if uri is None:
            raise XmlFormatError("节点 %s 的命名空间无法确定，不能安全复制。" % node.qname)
        name = "xmlns" if prefix == "" else "xmlns:" + prefix
        declarations += ' %s="%s"' % (name, uri.replace("&", "&amp;").replace('"', "&quot;"))
    if declarations:
        head = len(node.qname) + 1
        raw = raw[:head] + declarations + raw[head:]
    return raw


def to_element(fragment, default_ns):
    wrapper = '<w xmlns="%s">%s</w>' % (default_ns, fragment)
    return ET.fromstring(wrapper)[0]


def _norm(value):
    return (value or "").strip()


def same_structure(a, b):
    """忽略缩进空白的结构比较：标签、属性、文本、子节点顺序都必须一致。"""
    if a.tag != b.tag or a.attrib != b.attrib or _norm(a.text) != _norm(b.text) or _norm(a.tail) != _norm(b.tail):
        return False
    if len(a) != len(b):
        return False
    return all(same_structure(x, y) for x, y in zip(a, b))
