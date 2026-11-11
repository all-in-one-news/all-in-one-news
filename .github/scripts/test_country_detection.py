import ast
import re
from pathlib import Path

SOURCE = Path(__file__).with_name("update_news.py")
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))

needed = {
    "INCIDENT_LOCATION_ALIASES",
    "INCIDENT_PLACE_ALIASES",
    "incident_country",
}
nodes = [
    node for node in tree.body
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.FunctionDef))
    and (
        (isinstance(node, ast.FunctionDef) and node.name in needed)
        or (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in needed for target in node.targets)
        )
        or (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id in needed
        )
    )
]
namespace = {"re": re}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
detect = namespace["incident_country"]

cases = {
    "ফতুল্লার অগ্নিকাণ্ডে কয়েকজন আহত": "BD",
    "গোপালগঞ্জে পৃথক সড়ক দুর্ঘটনায় নিহত": "BD",
    "পল্লবীতে পার্কিংয়ে থাকা বাসে আগুন": "BD",
    "মাধবপুরে সড়ক দুর্ঘটনায় চালকের মৃত্যু": "BD",
    "আসামে ট্রেন লাইনচ্যুত, আহত বেশ কয়েকজন": "IN",
    "Train derailment reported in Guwahati": "IN",
    "Fire reported in London": "GB",
    "Unlocated international incident headline": "WORLD",
    "A train incident in an unspecified location": "WORLD",
}

for title, expected in cases.items():
    actual = detect({"title": title, "summary": ""})
    if actual != expected:
        raise SystemExit(f"Country detection failed: {title!r}: expected {expected}, got {actual}")

print(f"Passed {len(cases)} country-detection regression tests.")

# Country filter regression: WORLD is included only in the all-countries view.
INDEX = SOURCE.parents[2] / "index.html"
index_text = INDEX.read_text(encoding="utf-8")
match = re.search(r"function matches\(x\)\{([^}]+)\}", index_text)
if not match:
    raise SystemExit("Could not locate the country/language filter.")
filter_body = match.group(1)
if "country==='ALL'||c===country" not in filter_body or "c==='WORLD'" in filter_body:
    raise SystemExit("Country-specific feeds must not include unassigned WORLD stories.")
print("Passed country filter regression test.")
