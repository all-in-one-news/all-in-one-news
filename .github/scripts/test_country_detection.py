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
if "if(!isRefresh&&!$('from').value)$('from').value=retentionStart;" not in index_text:
    raise SystemExit("Manual refresh must preserve the selected start date.")
print("Passed date filter persistence regression test.")

# Theme preference regression: dark mode must persist across page reloads.
if 'localStorage.setItem(\'ain_theme\',next)' not in index_text:
    raise SystemExit("Theme toggle must save the visitor's selected theme.")
if 'applyTheme(localStorage.getItem(\'ain_theme\')||\'light\')' not in index_text:
    raise SystemExit("Saved theme preference must be restored on page load.")
if 'onclick="toggleTheme()"' not in index_text:
    raise SystemExit("Theme button must use the persistent theme toggle.")
print("Passed dark mode preference persistence regression test.")

# Avoid a light-theme flash before the page body is parsed.
if "localStorage.getItem('ain_theme')==='dark'" not in index_text:
    raise SystemExit("Saved dark mode must be applied from the document head.")
if "html.dark-preload body{" not in index_text:
    raise SystemExit("Early dark-mode CSS variables are missing.")
if "document.documentElement.classList.toggle('dark-preload',dark)" not in index_text:
    raise SystemExit("Theme changes must synchronize the early-loading theme class.")
print("Passed dark mode first-paint regression test.")

# Accessible names for key controls (screen readers and assistive technology).
for control in ('country', 'language', 'q', 'sort', 'from', 'to'):
    if not re.search(r'<(?:input|select)\b[^>]*id="' + re.escape(control) + r'"[^>]*aria-label="[^"]+"', index_text):
        raise SystemExit(f"Control {control!r} is missing an accessible label.")
if 'aria-label="খবর আবার লোড করুন"' not in index_text:
    raise SystemExit("The reload button is missing an accessible label.")
print("Passed accessible control label regression test.")

# Reject invalid date ranges instead of silently showing an empty feed.
if "if($('to').value&&$('to').value<$('from').value)" not in index_text:
    raise SystemExit("The date filter must reject an end date earlier than its start date.")
if 'শেষ তারিখ শুরুর তারিখের আগে হতে পারবে না' not in index_text:
    raise SystemExit("The invalid date range must show a clear Bengali explanation.")
print("Passed invalid date range validation regression test.")

# Keep the automated collection cadence at the agreed 10-minute interval.
WORKFLOW = SOURCE.parents[1] / "workflows" / "update-news.yml"
workflow_text = WORKFLOW.read_text(encoding="utf-8")
if "cron: '*/10 * * * *'" not in workflow_text:
    raise SystemExit("News collection must be scheduled every 10 minutes.")
print("Passed automated news collection schedule regression test.")

# Global editorial desks must be discoverable in both English and Bangla.
collector_text = SOURCE.read_text(encoding="utf-8")
for desk in ("politics", "economy", "sports", "technology", "entertainment", "market"):
    if "'" + desk + "': (" not in collector_text:
        raise SystemExit(f"Missing global news collection query for {desk}.")
    if "('WORLD', desk," not in collector_text:
        raise SystemExit(f"Global {desk} query is not added to the collector feed list.")
print("Passed six global news desk feed configuration checks.")

# Exercise the collector's real headline classifier for the new desks.
classifier_nodes = [
    node for node in tree.body
    if (isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "patterns"
        for target in node.targets
    )) or (isinstance(node, ast.FunctionDef) and node.name == "classify")
]
classifier_ns = {"re": re}
exec(compile(ast.Module(body=classifier_nodes, type_ignores=[]), str(SOURCE), "exec"), classifier_ns)
classify = classifier_ns["classify"]
desk_cases = {
    "Election commission announces national vote schedule": "politics",
    "Inflation rises as central bank changes interest rate": "economy",
    "Bangladesh cricket team wins the final match": "sports",
    "New artificial intelligence chip unveiled by researchers": "technology",
    "Popular anime film breaks box office record": "entertainment",
    "Stock market shares rise after trading session": "market",
}
for title, expected in desk_cases.items():
    actual = classify({"title": title, "summary": "", "category": "WORLD"})
    if actual != expected:
        raise SystemExit(f"News desk classification failed: {title!r}: expected {expected}, got {actual}")
print(f"Passed {len(desk_cases)} global news desk classification tests.")

# Every new desk must have a visible homepage filter and matching count.
for desk in ("politics", "economy", "sports", "technology", "entertainment", "market"):
    if 'data-cat="' + desk + '"' not in index_text or 'id="n-' + desk + '"' not in index_text:
        raise SystemExit(f"Homepage is missing the {desk} news desk filter/count.")
    if desk + ":/" not in index_text:
        raise SystemExit(f"Homepage headline matching is missing for {desk}.")
print("Passed six homepage news desk filter checks.")

# Feed registry must exist before global desk feeds are appended.
if collector_text.index("feeds=[]") > collector_text.index("for desk, (english_query, bangla_query)"):
    raise SystemExit("Global desk feeds are appended before the feed registry is initialized.")
print("Passed global feed initialization order regression test.")

# Homepage should expose more records per page without changing feed retention.
if "const PAGE_SIZE=40;" not in index_text:
    raise SystemExit("Homepage pagination must show 40 stories per page.")
if "shown.slice((page-1)*PAGE_SIZE,page*PAGE_SIZE)" not in index_text:
    raise SystemExit("Homepage story slicing must use the shared page size.")
if "Math.ceil(shown.length/PAGE_SIZE)" not in index_text:
    raise SystemExit("Homepage page count must use the shared page size.")
print("Passed 40-story pagination regression test.")
