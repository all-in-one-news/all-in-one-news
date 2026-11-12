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
    "যুক্তরাষ্ট্রে নিযুক্ত রাশিয়ার রাষ্ট্রদূতের মৃত্যু": "US",
    "গাজার নাসের হাসপাতালে চিকিৎসকসহ নিহত ৬": "PS",
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

# Country and date selectors are intentionally removed; retention is category-based.
INDEX = SOURCE.parents[2] / "index.html"
index_text = INDEX.read_text(encoding="utf-8")
if 'id="country"' in index_text or 'id="from"' in index_text or 'id="to"' in index_text:
    raise SystemExit("Country and date selection controls must not appear on the homepage.")
match = re.search(r"function matches\(x\)\{([^}]+)\}", index_text)
if not match or "visitorCountry!=='BD'||c==='BD'" not in match.group(1) or "l===language" not in match.group(1):
    raise SystemExit("The language filter must combine with automatic Bangladesh country detection.")
if "SPECIAL_RETENTION_CATEGORIES=new Set(['fire','missing','abuse','accident','casualty'])" not in index_text or "keepByRetention(x)" not in index_text:
    raise SystemExit("The homepage must apply one-year retention to special incident categories.")
if "regular_cutoff = now - timedelta(days=30)" not in collector_text or "special_cutoff = now - timedelta(days=365)" not in collector_text:
    raise SystemExit("The collector must retain regular news for 30 days and special incident news for 365 days.")
if "published<cutoff_for_category(category)" not in collector_text or "published<cutoff_for_category(item.get('category'))" not in collector_text:
    raise SystemExit("Collector and SEO article generation must use category-specific retention.")
print("Passed category-based 30-day/365-day retention regression checks.")

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
for control in ('language', 'q', 'sort'):
    if not re.search(r'<(?:input|select)\b[^>]*id="' + re.escape(control) + r'"[^>]*aria-label="[^"]+"', index_text):
        raise SystemExit(f"Control {control!r} is missing an accessible label.")
if 'aria-label="খবর আবার লোড করুন"' not in index_text:
    raise SystemExit("The reload button is missing an accessible label.")
print("Passed accessible control label regression test.")

# Date selection is removed; category retention is tested above.

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
if "language=readPref('ain_language'" not in index_text or "writePref('ain_language',language)" not in index_text:
    raise SystemExit("The language preference must use safe reads and writes; country preference is removed.")
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

# The latest-news ticker must follow the selected language and desk.
if "const tickerStory=rows.find(x=>matches(x)&&(!cat||cat==='all'||kind(x)===cat));" not in index_text:
    raise SystemExit("The latest-news ticker must use the selected language and desk.")
if "$('latest').textContent=tickerStory?clean(tickerStory.title):'এই ভাষায় এখনো খবর নেই';" not in index_text:
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
    "dailyobserverbd.com", "newagebd.net", "daily-sun.com",
    "bonikbarta.net", "dailyjanakantha.com", "manabzamin.net",
    "bangladeshpost.net", "theindependentbd.com", "businesspostbd.com",
    "daily-sangram.com",
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
if "targeted_query = '(' + query + ') (' + publisher_site_query + ') ' + search_after_for_category(category)" not in collector_text:
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


# Image recovery must retain alternate RSS thumbnails when duplicate feed
# editions or near-identical reports are merged, so the verifier can fall back.
for required in (
    "old_item['image_candidates']=candidates[:12]",
    "match['image_candidates']=candidates[:12]",
    "for candidate in [item.get('image','')]+list(item.get('image_candidates') or []):",
    "for image_url in candidates:",
):
    if required not in collector_text:
        raise SystemExit(f"Image recovery fallback is missing: {required}")
print("Passed alternate-image preservation and fallback regression checks.")

# Duplicate stories must merge by canonical link and conservative headline
# similarity, while re-used thumbnails must not merge unrelated stories.
for required in (
    "canonical=str(item.get('link','')).strip().split('#',1)[0].rstrip('/')",
    "difflib.SequenceMatcher(None,title,other_title).ratio()",
    "if ratio>=0.90 or overlap>=0.88:",
    "Do not deduplicate stories by thumbnail URL",
):
    if required not in collector_text:
        raise SystemExit(f"Duplicate-news protection is missing: {required}")
print("Passed canonical-link, headline-similarity, and image-reuse deduplication checks.")

# Public social discovery should cover multiple Bangladesh news desks, not
# only missing-child notices, and must leave country classification to text.
for required in (
    "social_news_queries = {",
    "'fire': 'আগুন OR অগ্নিকাণ্ড OR দাবানল'",
    "'accident': 'দুর্ঘটনা OR সড়ক দুর্ঘটনা OR ট্রেন দুর্ঘটনা'",
    "'casualty': 'নিহত OR মৃত্যু OR হতাহত OR আহত'",
    "'politics': 'নির্বাচন OR সংসদ OR সরকার OR রাজনীতি'",
    "'economy': 'অর্থনীতি OR মূল্যস্ফীতি OR রেমিট্যান্স OR বাজেট'",
    "'sports': 'ক্রিকেট OR ফুটবল OR খেলাধুলা OR বিশ্বকাপ'",
    "social_platform_query = '(site:facebook.com OR site:youtube.com)'",
    "feeds.append(('WORLD',social_category,",
):
    if required not in collector_text:
        raise SystemExit(f"Social-news discovery is missing: {required}")
print("Passed Facebook and YouTube multi-category discovery regression checks.")


# Country selector is removed; Bangladesh visitors are automatically filtered to BD news.
if 'id="country"' in index_text or 'id="language"' not in index_text:
    raise SystemExit("Homepage must omit country selection and preserve language selection.")
if "visitorCountry!=='BD'||c==='BD'" not in index_text:
    raise SystemExit("Visitors detected in Bangladesh must see only BD-tagged news.")
if "readPref('ain_language',visitorCountry==='BD'?'bn'" not in index_text:
    raise SystemExit("Bangladesh visitors must default to Bangla unless they previously chose another language.")
if "fetch('https://ipapi.co/json/')" not in index_text or "timeZone==='Asia/Dhaka'" not in index_text:
    raise SystemExit("Visitor country detection must use IP geolocation with a Dhaka-timezone fallback.")
if "if(!locationResolved){await detectVisitorCountry();locationResolved=true}" not in index_text:
    raise SystemExit("Visitor country must be detected before the first news render.")
print("Passed automatic Bangladesh visitor news-filter regression checks.")

# All twelve news categories must be represented in the UI and classifier.
for category in (
    "fire","missing","abuse","accident","casualty","reserve",
    "politics","economy","sports","technology","entertainment","market"
):
    if f'data-cat="{category}"' not in index_text or f'id="n-{category}"' not in index_text:
        raise SystemExit(f"Category card or count is missing: {category}")
    if not re.search(r'\b'+re.escape(category)+r':/', index_text):
        raise SystemExit(f"Category classifier is missing: {category}")
print("Passed all twelve category UI and classifier regression checks.")

# Mobile layout should keep the remaining language/search controls touch-friendly
# and use a compact two-column category grid.
for required in (
    "@media(max-width:560px)",
    ".language{gap:6px}",
    ".language select{min-height:42px}",
    ".stats{grid-template-columns:repeat(2,minmax(0,1fr))",
    ".filters{grid-template-columns:minmax(0,1fr);",
    ".filters input,.filters select{width:100%;min-height:43px}",
    ".pages button{min-width:38px;min-height:38px}",
):
    if required not in index_text:
        raise SystemExit(f"Mobile responsive layout is missing: {required}")
print("Passed mobile responsive layout regression checks.")


# Performance safeguards: defer off-screen card rendering and decode images asynchronously.
for required in (
    "content-visibility:auto",
    "contain-intrinsic-size:auto 430px",
    'loading="lazy" decoding="async"',
):
    if required not in index_text:
        raise SystemExit(f"Frontend performance optimization is missing: {required}")
print("Passed frontend rendering and image-decoding performance checks.")

# Core search-engine metadata and generated article schema must remain available.
for required in (
    '<html lang="bn">',
    '<meta name="description"',
    '<meta name="robots" content="index,follow',
    '<link rel="canonical"',
    'property="og:title"',
    'name="twitter:card"',
    '"@type":"WebSite"',
):
    if required not in index_text:
        raise SystemExit(f"Homepage SEO metadata is missing: {required}")
if "Sitemap: https://all-in-one-news.github.io/all-in-one-news/sitemap.xml" not in (INDEX.parents[0] / "robots.txt").read_text(encoding="utf-8"):
    raise SystemExit("robots.txt must advertise the canonical sitemap URL.")
print("Passed homepage SEO metadata and robots sitemap checks.")
