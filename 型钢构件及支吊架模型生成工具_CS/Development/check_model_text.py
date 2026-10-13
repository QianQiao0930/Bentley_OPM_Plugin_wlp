"""Read-only guard for the fixed-size DGN model-text policy; no Bentley host required."""
from pathlib import Path
import re
import sys

PROJECT = Path(__file__).resolve().parents[1]
FACTORY = PROJECT / "Services/ModelTextFactory.cs"
RUNTIME_ROOTS = ("App", "Data", "Domain", "Services", "Tools", "OpenPlant", "Registration", "UI", "Infrastructure")
# Ignore documentation, string literals and WPF labels when looking for native creation calls.
LITERALS = re.compile(r'//[^\n]*|/\*.*?\*/|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
FORBIDDEN = re.compile(
    r"\bnew\s+(?:[\w]+\.)*(?:TextBlockProperties|RunProperties|TextElement|TextNodeElement|TextString)\s*\("
    r"|\bTextHandlerBase\s*\.\s*CreateElement\s*\("
    r"|\bCreateTextElement\w*\s*\("
    r"|\bBentley\.DgnPlatformNET\.TextBlock\s*\("
    r"|\bAddAnnotationScale\s*\("
)


def code_only(text):
    return LITERALS.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def main():
    failures = []
    scanned = 0
    for directory in RUNTIME_ROOTS:
        for path in sorted((PROJECT / directory).rglob("*.cs")):
            if "obj" in path.parts or "bin" in path.parts:
                continue
            scanned += 1
            if path == FACTORY:
                continue
            source = code_only(path.read_text(encoding="utf-8-sig"))
            matches = list(FORBIDDEN.finditer(source))
            # Unqualified TextBlock is native only when its Bentley namespace is imported;
            # explicit WPF imports/aliases keep ordinary interface text outside this policy.
            if "using Bentley.DgnPlatformNET;" in source and "using System.Windows.Controls;" not in source:
                matches += list(re.finditer(r"\bnew\s+TextBlock\s*\(", source))
            for match in matches:
                line = source.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(PROJECT)}:{line}: use ModelTextFactory for model text")

    factory = code_only(FACTORY.read_text(encoding="utf-8-sig"))
    for required in ("properties.ClearAnnotationScale();", "properties.RemoveTextStyle();",
                     "properties.IsViewIndependent = false;", "run.RemoveTextStyle();",
                     "run.FontSize =", "annotation.HasAnnotationScale("):
        if required not in factory:
            failures.append(f"ModelTextFactory is missing policy operation: {required}")
    if re.search(r"\bAddToModel\s*\(|\bAddToDgnModel\s*\(", factory):
        failures.append("ModelTextFactory must return an orphan element; caller owns preview/confirmation")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"PASS: {scanned} runtime C# files; model-text creation is centralized and fixed-size policy is present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
