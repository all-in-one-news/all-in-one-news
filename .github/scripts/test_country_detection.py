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
    "দক্ষিণ কোরিয়ায় ৩২টি যানবাহনকে আঘাত যাত্রীবাহী বাসের": "KR",
    "জাপানের টোকিওতে ভূমিকম্প": "JP",
    "ধামরাইয়ে বসতঘরে অগ্নিকাণ্ড": "BD",
    "বোদা উপজেলায় মোটরসাইকেল দুর্ঘটনায় দুই শিক্ষার্থী নিহত": "BD",
    "বোদা উপজেলায় মোটরসাইকেল দুর্ঘটনায় ২ মাদ্রাসা শিক্ষার্থী নিহত - এইমাত্র": "BD",
    "পঞ্চগড়ের বোদায় সড়ক দুর্ঘটনা": "BD",
    "গাবতলীতে বাস চাপায় দুই নারীর মর্মান্তিক মৃত্যু": "BD",
    "জন্ম-মৃত্যু নিবন্ধনে বিভাগীয় পর্যায়ে ২য় কালাইয়ের ইউএনও": "BD",
    "অক্টোবরে ডিএসই থেকে ১৭৫ কোটি টাকা তুলে নিয়েছেন বিদেশি বিনিয়োগকারীরা": "BD",
    "জুলাই গণঅভ্যুত্থানে আহত হয়েও গেজেটভুক্ত নন": "BD",
    "৪২০টির বেশি শিক্ষামূলক খেলা যোগ হচ্ছে প্রাথমিকের নতুন পাঠ্যক্রমে": "BD",
    "Dhaka Stock Exchange reports record turnover": "BD",
    "DSE reports record turnover in the Indian market": "IN",
    "আখাউড়ায় ট্রেনে আগুন": "BD",
    "রাঙ্গুনিয়ায় মোটরসাইকেল দুর্ঘটনা": "BD",
    "Markapuram: Four Injured In Tractor-Car Collision": "IN",
    "Deepavali fire in Mysuru": "IN",
    "চীনের সাংহাইয়ে ভারী বৃষ্টি": "CN",
    "পাকিস্তানের করাচিতে বিস্ফোরণ": "PK",
    "মালয়েশিয়ার কুয়ালালামপুরে দুর্ঘটনা": "MY",
    "ইরানের তেহরানে আগুন": "IR",
    "সৌদি আরবের রিয়াদে সড়ক দুর্ঘটনা": "SA",
    "সংযুক্ত আরব আমিরাতের দুবাইয়ে আগুন": "AE",
    "Fire reported in London": "GB",
    "Unlocated international incident headline": "WORLD",
    "A train incident in an unspecified location": "WORLD",
}

for title, expected in cases.items():
    actual = detect({"title": title, "summary": ""})
    if actual != expected:
        raise SystemExit(f"Country detection failed: {title!r}: expected {expected}, got {actual}")

print(f"Passed {len(cases)} country-detection regression tests.")

# Bangladesh must receive a reserved share of each image-recovery batch.
collector_text = SOURCE.read_text(encoding="utf-8")
if "take=min(15,limit,len(groups['BD']))" not in collector_text:
    raise SystemExit("Bangladesh image-recovery reservation must be 15 candidates per batch.")
if "groups['BD'].sort(key=" not in collector_text or "str(x.get('category','')).lower()=='missing'" not in collector_text:
    raise SystemExit("Bangladesh image-recovery priority for missing-child alerts must remain enabled.")
print("Passed Bangladesh image-recovery quota and priority regression test.")

# RSS headline and summary text must be readable after markup/entity cleanup.
cleaner_node = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "clean_feed_text"), None)
if cleaner_node is None:
    raise SystemExit("RSS text normalization helper is missing.")
cleaner_ns = {"re": re, "html": __import__("html")}
exec(compile(ast.Module(body=[cleaner_node], type_ignores=[]), str(SOURCE), "exec"), cleaner_ns)
clean_feed_text = cleaner_ns["clean_feed_text"]
if clean_feed_text("  <b>Breaking&nbsp;News</b>  &amp;   Updates ") != "Breaking News & Updates":
    raise SystemExit("RSS text normalization failed to remove markup, decode entities, or collapse whitespace.")
if clean_feed_text("<p>First</p><p>Second</p>", 8) != "First Se":
    raise SystemExit("RSS summary normalization must enforce the requested length limit.")
print("Passed RSS headline and summary normalization regression tests.")

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
if "writePref('ain_theme',next)" not in index_text:
    raise SystemExit("Theme toggle must save the visitor's selected theme through safe storage.")
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
    "Cabinet approves new policy after parliamentary debate": "politics",
    "Inflation rises as central bank changes interest rate": "economy",
    "Remittance inflows and employment rise this quarter": "economy",
    "Bangladesh cricket team wins the final match": "sports",
    "Bangladesh Premier League match ends with a last-ball goal": "sports",
    "New artificial intelligence chip unveiled by researchers": "technology",
    "New mobile app and smartphone technology announced": "technology",
    "Popular anime film breaks box office record": "entertainment",
    "Singer releases a new music album before concert": "entertainment",
    "Stock market shares rise after trading session": "market",
    "DSE share prices rise during Dhaka Stock Exchange trading": "market",
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
if "const PAGE_SIZE=60;" not in index_text:
    raise SystemExit("Homepage pagination must show 60 stories per page.")
if "shown.slice((page-1)*PAGE_SIZE,page*PAGE_SIZE)" not in index_text:
    raise SystemExit("Homepage story slicing must use the shared page size.")
if "Math.ceil(shown.length/PAGE_SIZE)" not in index_text:
    raise SystemExit("Homepage page count must use the shared page size.")
print("Passed 60-story pagination regression test.")

# Browser storage can be unavailable in private/restricted contexts; feed preferences must still work.
if "function readPref(key,fallback)" not in index_text or "function writePref(key,value)" not in index_text:
    raise SystemExit("Safe browser preference helpers are missing.")
if "language=readPref('ain_language'" not in index_text or "country=readPref('ain_country','BD')" not in index_text:
    raise SystemExit("Language and country preferences must use safe reads.")
if "writePref('ain_language',language)" not in index_text or "writePref('ain_country',country)" not in index_text:
    raise SystemExit("Language and country preferences must use safe writes.")
print("Passed restricted browser storage preference regression test.")

# Keyboard users must be able to skip directly to the main news content.
if 'href="#main-content"' not in index_text or 'id="main-content" tabindex="-1"' not in index_text:
    raise SystemExit("The keyboard skip link or its focusable main target is missing.")
if ".skip-link:focus" not in index_text:
    raise SystemExit("The skip link must become visible when keyboard-focused.")
print("Passed keyboard skip navigation regression test.")

# Theme toggle must remain usable when browser storage is unavailable.
if "function toggleTheme(){const next=document.body.classList.contains('dark')?'light':'dark';writePref('ain_theme',next);applyTheme(next)}" not in index_text:
    raise SystemExit("Theme toggle must apply the theme even when preference storage fails.")
print("Passed restricted browser storage theme regression test.")

# Dynamic news updates should be announced politely to assistive technology.
if 'id="status" role="status" aria-live="polite" aria-atomic="true"' not in index_text:
    raise SystemExit("Feed status must be announced to screen readers.")
if 'class="ticker" role="status" aria-live="polite" aria-atomic="true"' not in index_text:
    raise SystemExit("The latest-news ticker must expose a polite live status.")
print("Passed live news announcement accessibility test.")

# Pagination controls need meaningful accessible names and a current-page indicator.
if 'aria-label="আগের পৃষ্ঠা"' not in index_text or 'aria-label="পরের পৃষ্ঠা"' not in index_text:
    raise SystemExit("Pagination buttons must have accessible names.")
if 'aria-current="page" aria-live="polite"' not in index_text:
    raise SystemExit("The current pagination position must be announced.")
print("Passed accessible pagination regression test.")

# The latest-news ticker must follow the selected country, language, and desk.
if "const tickerStory=rows.find(x=>matches(x)&&(!cat||cat==='all'||kind(x)===cat));" not in index_text:
    raise SystemExit("The latest-news ticker must use the selected country/language and desk.")
if "$('latest').textContent=tickerStory?clean(tickerStory.title):'এই দেশ ও ভাষায় এখনো খবর নেই';" not in index_text:
    raise SystemExit("The ticker must show a clear empty state when the selected feed has no stories.")
print("Passed selected-feed latest ticker regression test.")

# Bangladesh publisher-focused discovery must cover every global desk in both languages.
publisher_domains = (
    "bdnews24.com",
    "thedailystar.net",
    "prothomalo.com",
    "tbsnews.net",
    "dhakatribune.com",
    "bssnews.net",
    "dhakapost.com",
    "jagonews24.com",
    "banglanews24.com",
    "samakal.com",
    "banglatribune.com",
    "risingbd.com",
    "sarabangla.net",
    "thefinancialexpress.com.bd",
    "dhakatimes24.com",
    "protidinersangbad.com",
    "vodbangla.com",
)
if "bangladesh_publisher_domains = (" not in collector_text:
    raise SystemExit("Bangladesh publisher domain registry is missing.")
for domain in publisher_domains:
    if "'" + domain + "'" not in collector_text:
        raise SystemExit(f"Publisher-focused discovery is missing {domain}.")
if "publisher_site_query = ' OR '.join('site:' + domain for domain in bangladesh_publisher_domains)" not in collector_text:
    raise SystemExit("Publisher domains must be combined into a site-scoped RSS query.")
if "targeted_query = '(' + query + ') (' + publisher_site_query + ') ' + search_after" not in collector_text:
    raise SystemExit("Publisher RSS discovery must retain desk keywords and the 30-day date window.")
if "('en', english_query, 'BD:en')" not in collector_text or "('bn', bangla_query, 'BD:bn')" not in collector_text:
    raise SystemExit("Publisher-focused feeds must be collected in both English and Bangla.")
if "feeds.append(('WORLD', desk, 'https://news.google.com/rss/search?' + params))" not in collector_text:
    raise SystemExit("Publisher-focused results must enter the normal classifier pipeline.")
print("Passed Bangladesh publisher-focused discovery regression test.")

# Bangladesh incident desks must also use the publisher-focused RSS search.
if "for category, english_query in categories.items():" not in collector_text:
    raise SystemExit("Publisher-focused incident discovery loop is missing.")
if "bangla_query = bangla[category]" not in collector_text:
    raise SystemExit("Publisher-focused incident feeds must include Bangla query terms.")
if "feeds.append(('BD', category, 'https://news.google.com/rss/search?' + params))" not in collector_text:
    raise SystemExit("Publisher-focused incident results must be assigned to Bangladesh and their incident desk.")
print("Passed Bangladesh publisher-focused incident feed regression test.")


# Project documentation must describe real collection limits and maintenance paths.
README = SOURCE.parents[2] / "README.md"
readme_text = README.read_text(encoding="utf-8")
for required in (
    "https://all-in-one-news.github.io/all-in-one-news/",
    "every 10 minutes",
    "every 60 seconds",
    "30 days",
    "it is not a direct Facebook or YouTube API ingestion service",
    "`.github/scripts/update_news.py`",
    "`news-backup.json`",
):
    if required not in readme_text:
        raise SystemExit(f"README is missing required project detail: {required}")
print("Passed project documentation accuracy regression test.")

# Bangladesh TV news channel shortcuts must link to their official broadcaster websites.
channel_index = index_text.find('<section class="channels"')
if channel_index < 0 or 'aria-labelledby="channel-heading"' not in index_text:
    raise SystemExit("The Bangladesh TV channel shortcut section is missing or inaccessible.")
channel_section = index_text[channel_index:index_text.find('</section>', channel_index) + len('</section>')]
for domain in (
    "jamuna.tv", "somoynews.tv", "ekattor.tv", "channel24bd.tv", "ntvbd.com",
    "rtvonline.com", "dbcnews.tv", "independent24.com", "news24bd.tv", "atnnewstv.com",
):
    if 'https://www.' + domain + '/' not in channel_section and 'https://' + domain + '/' not in channel_section:
        raise SystemExit(f"TV channel shortcut is missing the official website for {domain}.")
if "google.com/s2/favicons?domain=" not in channel_section or "nextElementSibling.style.display='grid'" not in channel_section:
    raise SystemExit("TV channel logos must have a visible fallback when a favicon cannot load.")
if "overflow-x:auto" not in index_text or ".channel-link:focus-visible" not in index_text:
    raise SystemExit("TV channel shortcuts must scroll horizontally and remain keyboard accessible.")
print("Passed 10 Bangladesh TV channel shortcut, logo fallback, and accessibility checks.")


# Facebook and YouTube shortcuts must point to the named Bangladesh TV channels.
social_index = index_text.find('<section class="channels" aria-labelledby="social-heading"')
if social_index < 0:
    raise SystemExit("The Facebook and YouTube shortcut section is missing.")
social_end = index_text.find('</section>', social_index)
if social_end < 0:
    raise SystemExit("The Facebook and YouTube shortcut section is not closed.")
social_section = index_text[social_index:social_end]
social_accounts = {
    "Jamuna TV YouTube": "https://www.youtube.com/@jamunatvbd",
    "Somoy TV YouTube": "https://www.youtube.com/@somoynews360",
    "Ekattor TV YouTube": "https://www.youtube.com/@EkattorTelevision",
    "Channel 24 YouTube": "https://www.youtube.com/@channel24digital",
    "NTV YouTube": "https://www.youtube.com/@ntvlatestnews",
    "RTV YouTube": "https://www.youtube.com/@rtvnews",
    "DBC News YouTube": "https://www.youtube.com/@dbcnewstv",
    "Independent TV YouTube": "https://www.youtube.com/@independenttelevision",
    "News24 YouTube": "https://www.youtube.com/@news24tv",
    "ATN News YouTube": "https://www.youtube.com/@atnnewsltd",
    "Jamuna TV Facebook": "https://www.facebook.com/JamunaTelevision",
    "Somoy TV Facebook": "https://www.facebook.com/somoynews.tv",
    "Ekattor TV Facebook": "https://www.facebook.com/EkattorTV",
    "Channel 24 Facebook": "https://www.facebook.com/channel24bd",
    "NTV Facebook": "https://www.facebook.com/ntvdigital",
    "RTV Facebook": "https://www.facebook.com/rtvonline",
    "DBC News Facebook": "https://www.facebook.com/dbcnews.tv",
    "Independent TV Facebook": "https://www.facebook.com/itvbdofficial",
    "News24 Facebook": "https://www.facebook.com/news24bd.tv",
    "ATN News Facebook": "https://www.facebook.com/ATNNews",
}
for label, url in social_accounts.items():
    if 'href="' + url + '"' not in social_section:
        raise SystemExit(f"Social shortcut is missing {label}: {url}")
if 'aria-label="YouTube চ্যানেল লিংক"' not in social_section or 'aria-label="Facebook পেজ লিংক"' not in social_section:
    raise SystemExit("Social shortcut rows must be clearly identified without claiming unverified official status.")
if social_section.count('class="social-link"') != 20:
    raise SystemExit("Exactly 20 social shortcuts (10 YouTube and 10 Facebook) must be present.")
if ".social-row{" not in index_text or "overflow-x:auto" not in index_text or ".social-link:focus-visible" not in index_text:
    raise SystemExit("Social shortcuts must scroll horizontally and remain keyboard accessible.")
print("Passed 20 Bangladesh TV Facebook and YouTube shortcut regression checks.")
