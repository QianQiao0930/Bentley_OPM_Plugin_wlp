"""Read-only verification of the UI-only contract against the saved baseline."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

PROJECT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(Path(__file__).with_name("contracts.json").read_text(encoding="utf-8"))
NAME = "{http://schemas.microsoft.com/winfx/2006/xaml}Name"
EVENTS = ("Click", "SelectionChanged", "Checked", "Unchecked", "TextChanged", "LostFocus",
          "PreviewTextInput", "SizeChanged", "ScrollChanged", "PreviewKeyDown", "MouseLeftButtonDown", "Loaded")
for filename, baseline in MANIFEST.items():
    page = ET.parse(PROJECT / "UI" / filename).getroot()
    named = {node.get(NAME): node for node in page.iter() if node.get(NAME)}
    for name, attributes in baseline["named"].items():
        assert name in named, (filename, name)
        for key, value in attributes.items():
            assert named[name].get(key) == value, (filename, name, key)
    handlers = sorted({node.get(key) for node in page.iter() for key in EVENTS if node.get(key)})
    assert handlers == baseline["events"], filename
    for choice in baseline["choices"]:
        assert any(node.tag == choice["tag"] and dict(node.attrib) == choice["attributes"]
                   for node in page.iter()), (filename, choice)
    for binding in baseline["bindings"]:
        assert any(node.get(binding["attribute"]) == binding["value"] for node in page.iter()), (filename, binding)
    source = (PROJECT / "UI" / (filename + ".cs")).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(source).hexdigest() == baseline["businessSha256"], filename
    print(filename + ": original UI contract and business source preserved")
