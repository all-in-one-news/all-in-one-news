import json, re, os, time, html, http.cookiejar, urllib.request, urllib.parse, urllib.error, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
GENERIC_IMAGE_URL='https://lh3.googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc=s0-w300'

now = datetime.now(timezone.utc)
SPECIAL_RETENTION_CATEGORIES = {'fire','missing','abuse','accident','casualty'}
regular_cutoff = now - timedelta(days=30)
special_cutoff = now - timedelta(days=365)
search_after_regular = 'after:' + regular_cutoff.date().isoformat()
search_after_special = 'after:' + special_cutoff.date().isoformat()
def cutoff_for_category(category):
    return special_cutoff if str(category or '').lower() in SPECIAL_RETENTION_CATEGORIES else regular_cutoff
def search_after_for_category(category):
    return search_after_special if str(category or '').lower() in SPECIAL_RETENTION_CATEGORIES else search_after_regular

countries = [
    'AF','AL','DZ','AD','AO','AG','AR','AM','AU','AT','AZ','BS','BH','BD','BB','BY','BE','BZ','BJ','BT','BO','BA','BW','BR','BN','BG','BF','BI','CV','KH','CM','CA','CF','TD','CL','CN','CO','KM','CG','CR','HK','MO',
    'CI','HR','CU','CY','CZ','CD','DK','DJ','DM','DO','EC','EG','SV','GQ','ER','EE','SZ','ET','FJ','FI','FR','GA','GM','GE','DE','GH','GR','GD','GT','GN','GW','GY','HT','HN','HU','IS','IN','ID','IR','IQ',
    'IE','IL','IT','JM','JP','JO','KZ','KE','KI','KP','KR','KW','KG','LA','LV','LB','LS','LR','LY','LI','LT','LU','MG','MW','MY','MV','ML','MT','MH','MR','MU','MX','FM','MD','MC','MN','ME','MA','MZ','MM',
    'NA','NR','NP','NL','NZ','NI','NE','NG','MK','NO','OM','PK','PW','PA','PG','PY','PE','PH','PL','PT','QA','RO','RU','RW','KN','LC','VC','WS','SM','ST','SA','SN','RS','SC','SL','SG','SK','SI','SB','SO',
    'ZA','SS','ES','LK','SD','SR','SE','CH','SY','TJ','TZ','TH','TL','TG','TO','TT','TN','TR','TM','TV','UG','UA','AE','GB','US','UY','UZ','VU','VA','VE','VN','YE','ZM','ZW','PS','TW','XK',
]
categories = {
    'fire': 'fire OR blaze OR wildfire OR "building fire"',
    'missing': '"missing child" OR "child missing" OR "abducted child"',
    'abuse': 'rape OR "sexual assault" OR "sexual violence"',
    'accident': 'accident OR crash OR collision OR derailment OR shipwreck',
    'casualty': '"death toll" OR fatalities OR "people killed" OR casualties',
    'reserve': '"foreign exchange reserves" OR "forex reserves" OR "foreign reserves"'
}
bangla = {
    'fire':'আগুন OR অগ্নিকাণ্ড',
    'missing':'নিখোঁজ শিশু OR শিশু নিখোঁজ',
    'abuse':'ধর্ষণ OR যৌন নির্যাতন',
    'accident':'দুর্ঘটনা OR সড়ক দুর্ঘটনা OR নৌকাডুবি',
    'casualty':'নিহত OR প্রাণহানি OR হতাহত',
    'reserve':'বৈদেশিক মুদ্রার রিজার্ভ'
}

def local(tag):
    return tag.split('}')[-1].lower()

def clean_feed_text(value, limit=None):
    """Normalize RSS text and decode entities before publishing headlines."""
    cleaned = html.unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:limit] if limit is not None else cleaned

def text_of(node, names):
    for child in node.iter():
        if child is node: continue
        if local(child.tag) in names:
            value = ''.join(child.itertext()).strip()
            if value: return value
    return ''

def parse_date(value):
    if not value: return None
    try: dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        try: dt = parsedate_to_datetime(value)
        except Exception: return None
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

feeds=[]

# Direct RSS/Atom feeds for the first five Bangladesh publishers.
# These bypass Google News indexing for these sources.
direct_publisher_feeds = (
    ('Prothom Alo', 'prothomalo.com', 'https://www.prothomalo.com/feed/'),
    ('The Daily Star', 'thedailystar.net', 'https://www.thedailystar.net/frontpage/rss.xml'),
    ('bdnews24.com', 'bdnews24.com', 'https://bdnews24.com/?widgetName=rssfeed&widgetId=1150&getXmlFeed=true'),
    ('The Business Standard', 'tbsnews.net', 'https://www.tbsnews.net/top-news/rss.xml'),
    ('Jamuna TV', 'jamuna.tv', 'https://www.youtube.com/feeds/videos.xml?channel_id=UCN6sm8iHiPd0cnoUardDAnw'),
)
for publisher_name, publisher_domain, feed_url in direct_publisher_feeds:
    feeds.append(('BD', 'publisher', feed_url))

# Broad global desks are collected separately to avoid multiplying every
# country/category feed. Country is inferred from the reported location.
global_desk_queries = {
    'politics': ('election OR vote OR polling OR parliament OR government OR minister OR president OR prime minister OR opposition OR cabinet OR ruling party OR political party OR politics',
                 'নির্বাচন OR ভোট OR ভোটগ্রহণ OR সংসদ OR সরকার OR মন্ত্রী OR রাষ্ট্রপতি OR প্রধানমন্ত্রী OR বিরোধী দল OR মন্ত্রিসভা OR ক্ষমতাসীন দল OR রাজনৈতিক দল OR রাজনীতি'),
    'economy': ('economy OR inflation OR GDP OR budget OR trade OR exports OR imports OR central bank OR banking OR jobs OR employment OR remittance OR tax OR business OR industry OR wages',
                'অর্থনীতি OR মূল্যস্ফীতি OR জিডিপি OR বাজেট OR বাণিজ্য OR রপ্তানি OR আমদানি OR কেন্দ্রীয় ব্যাংক OR ব্যাংকিং OR কর্মসংস্থান OR চাকরি OR রেমিট্যান্স OR কর OR ব্যবসা OR শিল্প OR মজুরি'),
    'sports': ('sports OR football OR cricket OR tennis OR basketball OR tournament OR world cup OR league OR match OR player OR coach OR goal OR wicket OR Olympics OR FIFA OR ICC OR BPL OR IPL',
               'খেলাধুলা OR ফুটবল OR ক্রিকেট OR টেনিস OR বাস্কেটবল OR টুর্নামেন্ট OR বিশ্বকাপ OR লিগ OR ম্যাচ OR খেলোয়াড় OR কোচ OR গোল OR উইকেট OR অলিম্পিক OR ফিফা OR আইসিসি'),
    'technology': ('technology OR tech OR artificial intelligence OR AI OR software OR smartphone OR mobile phone OR app OR internet OR cybersecurity OR chip OR gadget OR startup',
                   'প্রযুক্তি OR প্রযুক্তিপণ্য OR কৃত্রিম বুদ্ধিমত্তা OR এআই OR সফটওয়্যার OR স্মার্টফোন OR মোবাইল OR অ্যাপ OR ইন্টারনেট OR সাইবার নিরাপত্তা OR চিপ OR গ্যাজেট OR স্টার্টআপ'),
    'entertainment': ('movie OR film OR cinema OR anime OR television series OR web series OR streaming OR actor OR actress OR celebrity OR singer OR music OR album OR drama OR Netflix OR concert OR box office',
                      'সিনেমা OR চলচ্চিত্র OR অ্যানিমে OR টিভি সিরিজ OR ওয়েব সিরিজ OR অভিনেতা OR অভিনেত্রী OR তারকা OR সংগীত OR গান OR অ্যালবাম OR নাটক OR কনসার্ট OR বক্স অফিস'),
    'market': ('stock market OR share market OR stock exchange OR share price OR shares OR stocks OR DSE OR Dhaka Stock Exchange OR Nasdaq OR Dow Jones OR trading session',
               'শেয়ার বাজার OR শেয়ারবাজার OR পুঁজিবাজার OR স্টক এক্সচেঞ্জ OR শেয়ারদর OR শেয়ারের দাম OR ডিএসই OR ঢাকা স্টক এক্সচেঞ্জ OR শেয়ার OR সূচক')
}
for desk, (english_query, bangla_query) in global_desk_queries.items():
    for desk_language, query, gl, ceid in (
        ('en', english_query, 'US', 'US:en'),
        ('bn', bangla_query, 'BD', 'BD:bn')
    ):
        params = urllib.parse.urlencode({
            'q': '(' + query + ') ' + search_after_regular,
            'hl': 'bn' if desk_language == 'bn' else 'en-US',
            'gl': gl,
            'ceid': ceid
        })
        feeds.append(('WORLD', desk, 'https://news.google.com/rss/search?' + params))

# Add a second discovery path focused on established Bangladesh publishers.
# These are Google News RSS searches, not direct publisher/API integrations.
bangladesh_publisher_domains = (
    # 200 Bangladesh publisher discovery targets. Availability and registration vary;
    # Google News RSS returns stories only for domains with indexed coverage.
    'bdnews24.com',
    'thedailystar.net',
    'prothomalo.com',
    'tbsnews.net',
    'dhakatribune.com',
    'bssnews.net',
    'dhakapost.com',
    'jagonews24.com',
    'banglanews24.com',
    'samakal.com',
    'jamuna.tv',
    'somoynews.tv',
    'ekattor.tv',
    'channel24bd.tv',
    'ntvbd.com',
    'rtvonline.com',
    'jugantor.com',
    'kalerkantho.com',
    'ittefaq.com.bd',
    'dailyinqilab.com',
    'banglatribune.com',
    'risingbd.com',
    'sarabangla.net',
    'thefinancialexpress.com.bd',
    'dhakatimes24.com',
    'protidinersangbad.com',
    'vodbangla.com',
    'dailyobserverbd.com',
    'newagebd.net',
    'daily-sun.com',
    'bonikbarta.net',
    'dailyjanakantha.com',
    'manabzamin.net',
    'bangladeshpost.net',
    'theindependentbd.com',
    'businesspostbd.com',
    'daily-sangram.com',
    'ajkerpatrika.com',
    'deshrupantor.com',
    'channelionline.com',
    'newsbangla24.com',
    'dainikamadershomoy.com',
    'dainikazadi.net',
    'dainikpurbokone.net',
    'purbanchal.com',
    'ctgpratidin.com',
    'gramerkagoj.com',
    'sylheterdak.com.bd',
    'dailynayadiganta.com',
    'bd-pratidin.com',
    'jaijaidinbd.com',
    'amadershomoy.com',
    'priyo.com',
    'campustimes.press',
    'shikshabarta.com',
    'news24bd.tv',
    'sangbadprotidin24.com',
    'ournewsbd.com',
    'somoyerchitra.com',
    'newsjournal24.com',
    'hotnews24.com',
    'jugobarta.com',
    'thereport24.com',
    'bangladesh24online.com',
    'dhakadiplomat.com',
    'themailbd.com',
    'bbarta24.net',
    'nirapadnews24.com',
    'currentnews.com.bd',
    'timebanglanews.com',
    'greenwatchbd.com',
    'unitednews24.com',
    'zoombangla.com',
    'bartabazar.com',
    'ep-bd.com',
    'womencye24.com',
    'bdlive24.com',
    'abnews24bd.com',
    'ournews24.com',
    'ut71news.com',
    'newsvoice.com',
    'latestbdnews.com',
    'sharenews24.com',
    'lalsobuzerkotha.com',
    'bd24live.com',
    'banglainsider.com',
    'vnewsbd.com',
    'muktinew24.com',
    'daily-bangladesh.com',
    'gonews24.com',
    'unb.com.bd',
    'amardeshonline.com',
    'dmpnews.org',
    'thefinancialexpress.com',
    'somoyerkonthosor.com',
    'arthosuchak.com',
    'sunbd24.com',
    'orthosongbad.com',
    'ajkersottasangbad24.com',
    'onenewsbd.com',
    'deshnews.net',
    'deshersangbad.com',
    'lastnewsbd.com',
    'bangladaily24.com',
    'protikhon.com',
    'bartabangla.com',
    'snn24.com',
    'alertnews24.com',
    'khoborprotidin24.com',
    'bbc24news.com',
    'dhakaprotidin.com',
    'eibela.com',
    'pbd.news',
    'techshohor.com',
    'techzoom.tv',
    'coxsbazarnews.com',
    'ukhiyanews.com',
    'khulnanews.com',
    'mathabhanga.com',
    'rajshahinews24.com',
    'chattogramnews.com',
    'dailykhowai.com',
    'karatoa.com.bd',
    'dailycoxsbazar.com',
    'uttorpurbo.com',
    'ajkerjamalpur.com',
    'amaderbarisal.com',
    'surmatimes.com',
    'dailysylhet.com',
    'chandpurtimes.com',
    'muktokhobor24.com',
    'bograsangbad.com',
    'rajshahirsomoy.com',
    'sylhetexpress.com',
    'lakshmipur24.com',
    'prothom-feni.com',
    'amarnoakhali.com',
    'chakarianews.com',
    'khulnanchal.com',
    'suprobhat.com',
    'shyamalsylhet.net',
    'newsdesk24.com',
    'dailycampus.com.bd',
    'bdcrictime.com',
    'probashirdiganta.com',
    'asiaone.com.bd',
    'dhakaprokash24.com',
    'ourislam24.com',
    'sonalinews.com',
    'dhakatoday.com',
    'newsflash71.com',
    'deshprothikhon.com',
    'businesshour24.com',
    'sharebazarnews.com',
    'sharebiz.net',
    'dailysharebazar.com',
    'sharebusiness24.com',
    'sharemarketbd.com',
    'sharebarta24.com',
    'arthobanijjo.com',
    'banglaoutlook.org',
    'bangladeshjournal.com',
    'alokito-bangladesh.com',
    'sangbad.net.bd',
    'manobkantha.com',
    'bhorerkagoj.com',
    'shomoyeralo.com',
    'dainikbangla.com.bd',
    'khaborerkagoj.com',
    'amar-sangbad.com',
    'deshkalnews.com',
    'dailyshomoy.com',
    'dailysangbad.com',
    'janobani.com',
    'dailysavvataralo.com',
    'dailyeaibangla.com',
    'dailybangladeshupdate.com',
    'businessbangladesh.com',
    'notunkotha.news',
    'abcnationalnews42.com',
    'nnn.media',
    'therisingcampus.com',
    'satyakantho.com',
    'banglarjanata.com',
    'chatganews.com',
    'deshsangbad.com',
    'nantvbd.com',
    'newsforjustice.com',
    'unnayanebangladesh.com',
    'thebangladeshtoday.com',
    'dailyasianage.com',
    'asianage.com.bd',
    'dailytribunal24.com',
    'dailycountrytodaybd.com',
    'dailyasiabd.com',
    'dailyindustrybd.com',
    'dailyfrontier.news',
    'dailyvob.com',
    'dailybangladesh.com',
    'dailyprothomkhobor.com',
)
publisher_site_queries = [
    ' OR '.join('site:' + domain for domain in bangladesh_publisher_domains[i:i+40])
    for i in range(0, len(bangladesh_publisher_domains), 40)
]

# Independent all-topic feed for every publisher domain. This complements
# grouped desk searches so a publisher's new upload is discoverable even when
# its topic is not among the predefined desks.
for publisher_domain in bangladesh_publisher_domains:
    params = urllib.parse.urlencode({
        'q': 'site:' + publisher_domain + ' ' + search_after_regular,
        'hl': 'bn',
        'gl': 'BD',
        'ceid': 'BD:bn'
    })
    feeds.append(('BD', 'publisher', 'https://news.google.com/rss/search?' + params))

# Incident and public-safety desks also get Bangladesh publisher-focused
# discovery in Bangla and English, not just the six global editorial desks.
for category, english_query in categories.items():
    bangla_query = bangla[category]
    for desk_language, query, ceid in (
        ('en', english_query, 'BD:en'),
        ('bn', bangla_query, 'BD:bn')
    ):
        for publisher_site_query in publisher_site_queries:
            targeted_query = '(' + query + ') (' + publisher_site_query + ') ' + search_after_for_category(category)
            params = urllib.parse.urlencode({
                'q': targeted_query,
                'hl': 'bn' if desk_language == 'bn' else 'en',
                'gl': 'BD',
                'ceid': ceid
            })
            feeds.append(('BD', category, 'https://news.google.com/rss/search?' + params))

for desk, (english_query, bangla_query) in global_desk_queries.items():
    for desk_language, query, ceid in (
        ('en', english_query, 'BD:en'),
        ('bn', bangla_query, 'BD:bn')
    ):
        for publisher_site_query in publisher_site_queries:
            targeted_query = '(' + query + ') (' + publisher_site_query + ') ' + search_after_regular
            params = urllib.parse.urlencode({
                'q': targeted_query,
                'hl': 'bn' if desk_language == 'bn' else 'en',
                'gl': 'BD',
                'ceid': ceid
            })
            feeds.append(('BD', desk, 'https://news.google.com/rss/search?' + params))

for country in countries:
    for category, query in categories.items():
        q = query
        lang='en'
        if country == 'BD':
            q = '(' + query + ') OR (' + bangla[category] + ')'
            lang='bn'
        params = urllib.parse.urlencode({
            'q': q + ' ' + search_after_for_category(category),
            'hl': 'bn' if lang=='bn' else 'en-US',
            'gl': country,
            'ceid': country + ':' + lang
        })
        feeds.append((country, category,
            'https://news.google.com/rss/search?' + params))

# A separate Bangla-language global feed means language preference does not
# depend on the visitor's IP country.
bangla_global_queries={
    'fire':'আগুন OR অগ্নিকাণ্ড OR দাবানল OR বিস্ফোরণ',
    'missing':'নিখোঁজ শিশু OR শিশু নিখোঁজ OR হারিয়ে যাওয়া শিশু OR অপহৃত শিশু',
    'abuse':'ধর্ষণ OR যৌন নির্যাতন OR যৌন সহিংসতা',
    'accident':'সড়ক দুর্ঘটনা OR ট্রেন দুর্ঘটনা OR নৌ দুর্ঘটনা OR দুর্ঘটনা',
    'casualty':'নিহত OR মৃত্যু OR হতাহত OR আহত',
    'reserve':'বৈদেশিক মুদ্রার রিজার্ভ OR বৈদেশিক মুদ্রা রিজার্ভ'
}
for category, query in bangla_global_queries.items():
    params=urllib.parse.urlencode({
        'q':'('+query+') ' + search_after_for_category(category),
        'hl':'bn','gl':'BD','ceid':'BD:bn'
    })
    feeds.append(('WORLD',category,'https://news.google.com/rss/search?'+params))


# Dedicated Bangladesh official missing-child alert discovery.
mun_q=urllib.parse.urlencode({
    'q':'site:munalert.org/active-cases OR site:munalert.org "MUN-"',
    'hl':'bn','gl':'BD','ceid':'BD:bn'
})
feeds.append(('BD','missing',
    'https://news.google.com/rss/search?'+mun_q))

# Public social-media discovery feeds for Bangladesh missing-child reports.
social_queries = [
    ('Facebook public posts', 'site:facebook.com ("নিখোঁজ শিশু" OR "শিশু নিখোঁজ" OR "missing child" OR "MUN Alert")'),
    ('YouTube public videos', 'site:youtube.com/watch ("নিখোঁজ শিশু" OR "শিশু নিখোঁজ" OR "missing child" OR "MUN Alert")')
]
for social_source, social_query in social_queries:
    social_params=urllib.parse.urlencode({
        'q':social_query+' ' + search_after_special,
        'hl':'bn','gl':'BD','ceid':'BD:bn'
    })
    feeds.append(('BD','missing',
        'https://news.google.com/rss/search?'+social_params))

# Public Facebook and YouTube news discovery beyond missing-child alerts.
# Results enter the normal classifier; country is inferred from the story text.
social_news_queries = {
    'fire': 'আগুন OR অগ্নিকাণ্ড OR দাবানল',
    'accident': 'দুর্ঘটনা OR সড়ক দুর্ঘটনা OR ট্রেন দুর্ঘটনা',
    'casualty': 'নিহত OR মৃত্যু OR হতাহত OR আহত',
    'politics': 'নির্বাচন OR সংসদ OR সরকার OR রাজনীতি',
    'economy': 'অর্থনীতি OR মূল্যস্ফীতি OR রেমিট্যান্স OR বাজেট',
    'sports': 'ক্রিকেট OR ফুটবল OR খেলাধুলা OR বিশ্বকাপ'
}
social_platform_query = '(site:facebook.com OR site:youtube.com)'
for social_category, social_terms in social_news_queries.items():
    social_params=urllib.parse.urlencode({
        'q':social_platform_query+' ('+social_terms+') (বাংলাদেশ OR বাংলাদেশি OR ঢাকা) '+search_after_for_category(social_category),
        'hl':'bn','gl':'BD','ceid':'BD:bn'
    })
    feeds.append(('WORLD',social_category,
        'https://news.google.com/rss/search?'+social_params))

# Targeted discovery from official Bangladesh Police/CID and established newsrooms.
trusted_missing_queries = [
    ('Bangladesh Police', 'site:police.gov.bd ("নিখোঁজ শিশু" OR "শিশু নিখোঁজ" OR "missing child" OR "abducted child")'),
    ('Police portal CID', 'site:police.portal.gov.bd ("নিখোঁজ শিশু" OR "শিশু নিখোঁজ" OR "missing child")'),
    ('BSS', 'site:bssnews.net ("নিখোঁজ শিশু" OR "শিশু নিখোঁজ" OR "missing child" OR "MUN Alert")'),
    ('The Daily Star', 'site:thedailystar.net ("নিখোঁজ শিশু" OR "missing child" OR "MUN Alert")'),
    ('The Business Standard', 'site:tbsnews.net ("নিখোঁজ শিশু" OR "missing child" OR "MUN Alert")'),
    ('Prothom Alo', 'site:prothomalo.com ("নিখোঁজ শিশু" OR "শিশু নিখোঁজ" OR "MUN Alert")')
]
for trusted_source, trusted_query in trusted_missing_queries:
    trusted_params=urllib.parse.urlencode({
        'q':trusted_query+' ' + search_after_special,
        'hl':'bn','gl':'BD','ceid':'BD:bn'
    })
    feeds.append(('BD','missing',
        'https://news.google.com/rss/search?'+trusted_params))


def fetch(feed):
    country, category, url = feed
    try:
        # Google News can rate-limit bursts. Retry transient failures per feed.
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AllInOneNews/1.0'})
                with urllib.request.urlopen(req,timeout=20) as response:
                    root=ET.fromstring(response.read())
                break
            except urllib.error.HTTPError as error:
                if error.code not in (429,500,502,503,504) or attempt==2:
                    raise
                delay=(attempt+1)*4
                print('Transient HTTP',error.code,'retrying',country,category,'after',delay,'seconds')
                time.sleep(delay)
            except (urllib.error.URLError,TimeoutError) as error:
                if attempt==2:
                    raise
                delay=(attempt+1)*3
                print('Transient network error retrying',country,category,'after',delay,'seconds')
                time.sleep(delay)
        items=[]
        for node in root.iter():
            if local(node.tag) not in ('item','entry'): continue
            title=text_of(node,('title',))
            link=''
            for child in node:
                if local(child.tag)=='link':
                    link=(child.attrib.get('href') or child.text or '').strip()
                    if link: break
            if not link: link=text_of(node,('link',))
            published=parse_date(text_of(node,('pubdate','published','updated','date')))
            if not title or not link or not published or published<cutoff_for_category(category) or published>now+timedelta(hours=2): continue
            summary=text_of(node,('description','summary','content'))
            image=''
            rss_image_candidates=[]
            for sub in node.iter():
                if local(sub.tag) in ('thumbnail','content','enclosure'):
                    candidate=(sub.attrib.get('url') or sub.attrib.get('src') or sub.attrib.get('href') or '').strip()
                    if candidate.startswith(('https://','http://')) and candidate != GENERIC_IMAGE_URL:
                        rss_image_candidates.append(candidate)
            # Google News can place a generic placeholder first and a publisher
            # image later in the same RSS item; inspect every candidate.
            for candidate in rss_image_candidates:
                if candidate != GENERIC_IMAGE_URL:
                    image=candidate
                    break
            if not image:
                image_matches=re.findall(r"<img[^>]+(?:src|data-src)=[\"'](https?://[^\"']+)",summary,re.I)
                for candidate in image_matches:
                    if candidate != GENERIC_IMAGE_URL:
                        image=candidate
                        break
            source='MUN Alert' if 'munalert.org' in link.lower() else country
            publisher_domain=''
            for sub in node.iter():
                if local(sub.tag)=='source':
                    if ''.join(sub.itertext()).strip():
                        source=''.join(sub.itertext()).strip()
                    source_url=(sub.attrib.get('url') or '').strip()
                    if source_url:
                        publisher_domain=(urllib.parse.urlparse(source_url).hostname or '').lower()
                        if publisher_domain.startswith('www.'):
                            publisher_domain=publisher_domain[4:]
                    break
            media_embed=''
            media_type=''
            yt=re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{6,})',link,re.I)
            if yt:
                media_embed='https://www.youtube-nocookie.com/embed/'+yt.group(1)
                media_type='youtube'
            elif 'facebook.com' in link.lower():
                encoded=urllib.parse.quote(link,safe='')
                if '/videos/' in link.lower() or 'watch' in link.lower():
                    media_embed='https://www.facebook.com/plugins/video.php?href='+encoded+'&show_text=true&width=560'
                    media_type='facebook'
                elif '/posts/' in link.lower() or '/permalink/' in link.lower():
                    media_embed='https://www.facebook.com/plugins/post.php?href='+encoded+'&show_text=true&width=560'
                    media_type='facebook'
            items.append({
                'title':clean_feed_text(title),
                'summary':clean_feed_text(summary,1200),
                'link':link,'source':source,'published':published.isoformat(),
                'image':image,'image_candidates':list(dict.fromkeys(rss_image_candidates))[:8],'media_embed':media_embed,'media_type':media_type,'publisher_domain':publisher_domain,'country':country,'category':category,
                'language':'bn' if re.search('[ঀ-৿]',title+' '+summary) else 'en',
                'verification_status':'official_source' if ('mun alert' in source.lower() or 'munalert.org' in link.lower() or 'police.gov.bd' in link.lower()) else 'source_reported'
            })
        for publisher_name, publisher_domain, direct_url in direct_publisher_feeds:
            if url == direct_url:
                source = publisher_name
                if not any(item.get('publisher_domain') for item in items):
                    for item in items:
                        item['source'] = publisher_name
                        item['publisher_domain'] = publisher_domain
                break
        print(country,category,len(items))
        return items[:200]
    except Exception as e:
        print('Feed error',country,category,str(e)[:180])
        return []

with ThreadPoolExecutor(max_workers=8) as pool:
    batches=list(pool.map(fetch,feeds))
fresh=[x for batch in batches for x in batch]

# Track which configured publisher domains actually appeared in Google News RSS.
# Not seen in one run does not prove a website is offline.
publisher_counts={}
publisher_samples={}
for story in fresh:
    domain=str(story.get('publisher_domain','') or '').lower()
    if domain.startswith('www.'):
        domain=domain[4:]
    if domain in bangladesh_publisher_domains:
        publisher_counts[domain]=publisher_counts.get(domain,0)+1
        publisher_samples.setdefault(domain,[])
        if len(publisher_samples[domain])<3:
            publisher_samples[domain].append({
                'title':story.get('title',''),
                'link':story.get('link',''),
                'published':story.get('published','')
            })
publisher_audit={
    'checked_at':now.isoformat(),
    'configured_total':len(bangladesh_publisher_domains),
    'observed_in_rss_total':len(publisher_counts),
    'not_observed_total':len(bangladesh_publisher_domains)-len(publisher_counts),
    'note':'Not observed means no matching publisher source appeared in this run; it does not prove the website is offline.',
    'publishers':[
        {'domain':domain,'status':'seen_in_rss' if domain in publisher_counts else 'not_seen_in_latest_fetch',
         'article_count':publisher_counts.get(domain,0),'sample_articles':publisher_samples.get(domain,[])}
        for domain in bangladesh_publisher_domains
    ]
}
with open('publisher_audit.json','w',encoding='utf-8') as audit_file:
    json.dump(publisher_audit,audit_file,ensure_ascii=False,indent=2)
print('Bangladesh publisher audit:',publisher_audit['observed_in_rss_total'],'observed of',publisher_audit['configured_total'])


# Recover article-page thumbnails when an RSS item has no image.
# Google News RSS often exposes a redirect URL and omits the publisher's
# Open Graph image, so follow the redirect and inspect page metadata.
import html
from urllib.parse import urljoin
enrichment_errors=[]
CHROME_UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'

def decode_google_news_url(link):
    if 'news.google.com/' not in str(link):
        return link
    article_id=urllib.parse.urlparse(link).path.rstrip('/').rsplit('/',1)[-1]
    if not article_id:
        return link
    cookies=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    page_html=''
    signature=''
    timestamp=''
    for path in ('/rss/articles/','/articles/'):
        page_url='https://news.google.com'+path+article_id
        headers={
            'User-Agent':CHROME_UA,
            'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language':'en-US,en;q=0.9',
            'Cookie':'CONSENT=PENDING+987',
            'Upgrade-Insecure-Requests':'1',
            'Sec-Fetch-Dest':'document','Sec-Fetch-Mode':'navigate','Sec-Fetch-Site':'none','Sec-Fetch-User':'?1'
        }
        request=urllib.request.Request(page_url,headers=headers)
        with opener.open(request,timeout=12) as response:
            page_html=response.read(1200000).decode('utf-8','ignore')
        sg=re.search(r'data-n-a-sg="([^"]+)"',page_html)
        ts=re.search(r'data-n-a-ts="([^"]+)"',page_html)
        if sg and ts:
            signature=sg.group(1)
            timestamp=int(ts.group(1))
            break
    if not signature or not timestamp:
        raise ValueError('Google News signature/timestamp missing; possible consent page or rate limit')
    inner=[
        'garturlreq',
        [['X','X',['X','X'],None,None,1,1,'US:en',None,1,None,None,None,None,None,0,1],
         'X','X',1,[1,1,1],1,1,None,0,0,None,0],
        article_id,timestamp,signature
    ]
    inner_json=json.dumps(inner,separators=(',',':'))
    outer_json=json.dumps([[['Fbv4je',inner_json]]],separators=(',',':'))
    body=urllib.parse.urlencode({'f.req':outer_json}).encode('utf-8')
    post_headers={
        'User-Agent':CHROME_UA,
        'Accept':'*/*',
        'Accept-Language':'en-US,en;q=0.9',
        'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8',
        'Origin':'https://news.google.com',
        'Referer':'https://news.google.com/',
        'Cookie':'CONSENT=PENDING+987',
        'Sec-Fetch-Dest':'empty','Sec-Fetch-Mode':'cors','Sec-Fetch-Site':'same-origin',
        'X-Same-Domain':'1'
    }
    post=urllib.request.Request(
        'https://news.google.com/_/DotsSplashUi/data/batchexecute',
        data=body,headers=post_headers,method='POST'
    )
    with opener.open(post,timeout=12) as response:
        raw=response.read(500000).decode('utf-8','ignore')
    parts=raw.split(chr(10)+chr(10),1)
    payload_text=parts[1] if len(parts)==2 else raw.lstrip(")]}'")
    frames=json.loads(payload_text)
    frame=next((x for x in frames if isinstance(x,list) and len(x)>2 and x[0]=='wrb.fr' and x[1]=='Fbv4je'),None)
    if not frame or not frame[2]:
        raise ValueError('Google News batchexecute returned no article URL')
    result=json.loads(frame[2])
    if isinstance(result,list) and len(result)>1 and result[0]=='garturlres' and str(result[1]).startswith(('https://','http://')):
        return result[1]
    raise ValueError('Google News decoder returned an unexpected payload')

def enrich_article_image(item):
    # Decode Google News' JS-mediated redirect before inspecting publisher metadata.
    link=str(item.get('link',''))
    if 'news.google.com/' in link:
        item['google_news_url']=link
        try:
            decoded=decode_google_news_url(link)
            if decoded and decoded!=link:
                item['link']=decoded
                link=decoded
        except Exception as error:
            if len(enrichment_errors)<40:
                enrichment_errors.append((item.get('country'),item.get('category'),'decode_'+type(error).__name__,str(error)[:160]))
            return item
    resolved=str(item.get('link',''))
    yt=re.search(r'(?:youtube[.]com/watch[?]v=|youtu[.]be/|youtube[.]com/shorts/)([A-Za-z0-9_-]{6,})',resolved,re.I)
    if yt:
        item['media_embed']='https://www.youtube-nocookie.com/embed/'+yt.group(1)
        item['media_type']='youtube'
    elif 'facebook.com' in resolved.lower():
        encoded=urllib.parse.quote(resolved,safe='')
        if any(path in resolved.lower() for path in ('/videos/','/reel/','/watch')):
            item['media_embed']='https://www.facebook.com/plugins/video.php?href='+encoded+'&show_text=true&width=560'
            item['media_type']='facebook'
        elif '/posts/' in resolved.lower() or '/permalink/' in resolved.lower():
            item['media_embed']='https://www.facebook.com/plugins/post.php?href='+encoded+'&show_text=true&width=560'
            item['media_type']='facebook'
    needs_image=not item.get('image') or item.get('image') == GENERIC_IMAGE_URL
    needs_summary=not str(item.get('summary','')).strip()
    if not needs_image and not needs_summary:
        return item
    if item.get('image') == GENERIC_IMAGE_URL:
        item['image']=''
    if not link.startswith(('https://','http://')) or 'news.google.com/' in link:
        return item
    try:
        req=urllib.request.Request(link,headers={
            'User-Agent':CHROME_UA,
            'Accept':'text/html,application/xhtml+xml',
            'Accept-Language':'en-US,en;q=0.9'
        })
        with urllib.request.urlopen(req,timeout=8) as response:
            final_url=response.geturl()
            raw=response.read(200000).decode('utf-8','ignore')
        if final_url and final_url.startswith(('https://','http://')):
            item['link']=final_url
        for tag in re.findall(r'<meta[^>]*>',raw,re.I):
            attrs={k.lower():html.unescape(v) for k,v in re.findall(r"""([\w:-]+)\s*=\s*["']([^"']*)["']""",tag)}
            key=(attrs.get('property') or attrs.get('name') or attrs.get('itemprop') or '').lower()
            candidate=attrs.get('content','').strip()
            if not item.get('image') and key in ('og:image','og:image:secure_url','twitter:image','twitter:image:src','image') and candidate.startswith(('https://','http://','/')):
                item['image']=urljoin(final_url,candidate)
            if not str(item.get('summary','')).strip() and key in ('description','og:description','twitter:description'):
                item['summary']=html.unescape(re.sub(r'<[^>]+>',' ',candidate))[:1200]

        # Some publishers omit Open Graph tags but expose the article image in
        # JSON-LD, a link[rel=image_src], or lazy-loaded image attributes.
        if not item.get('image'):
            for tag in re.findall(r'<link[^>]*>',raw,re.I):
                attrs={k.lower():html.unescape(v) for k,v in re.findall(r"""([\w:-]+)\s*=\s*["']([^"']*)["']""",tag)}
                if 'image_src' in attrs.get('rel','').lower():
                    candidate=urljoin(final_url,attrs.get('href','').strip())
                    if candidate.startswith(('https://','http://')):
                        item['image']=candidate
                        break
        if not item.get('image'):
            for script in re.findall(r"""<script[^>]*type=["']application/ld\+json["'][^>]*>(.*?)</script>""",raw,re.I|re.S):
                try:
                    data=json.loads(html.unescape(script.strip()))
                except Exception:
                    continue
                stack=data if isinstance(data,list) else [data]
                while stack and not item.get('image'):
                    node=stack.pop(0)
                    if isinstance(node,dict):
                        candidate=node.get('image') or node.get('thumbnailUrl')
                        if isinstance(candidate,dict):
                            candidate=candidate.get('url') or candidate.get('contentUrl')
                        elif isinstance(candidate,list):
                            candidate=next((v.get('url') if isinstance(v,dict) else v for v in candidate if v), '')
                        if isinstance(candidate,str) and candidate.strip():
                            candidate=urljoin(final_url,candidate.strip())
                            if candidate.startswith(('https://','http://')):
                                item['image']=candidate
                                break
                        graph=node.get('@graph')
                        if isinstance(graph,list): stack.extend(graph)
        if not item.get('image'):
            for tag in re.findall(r'<img[^>]*>',raw,re.I):
                attrs={k.lower():html.unescape(v) for k,v in re.findall(r"""([\w:-]+)\s*=\s*["']([^"']*)["']""",tag)}
                candidate=next((attrs.get(k,'') for k in ('data-src','data-original','data-lazy-src','src') if attrs.get(k)), '')
                if not candidate and attrs.get('srcset'):
                    candidate=attrs['srcset'].split(',')[-1].strip().split(' ')[0]
                candidate=urljoin(final_url,candidate.strip())
                if candidate.startswith(('https://','http://')) and not any(x in candidate.lower() for x in ('logo','icon','avatar','pixel','spacer')):
                    item['image']=candidate
                    break
        resolved=str(item.get('link',''))
        item['media_embed']=''
        item['media_type']=''
        yt=re.search(r'(?:youtube[.]com/watch[?]v=|youtu[.]be/|youtube[.]com/shorts/)([A-Za-z0-9_-]{6,})',resolved,re.I)
        if yt:
            item['media_embed']='https://www.youtube-nocookie.com/embed/'+yt.group(1)
            item['media_type']='youtube'
        elif 'facebook.com' in resolved.lower():
            encoded=urllib.parse.quote(resolved,safe='')
            if any(path in resolved.lower() for path in ('/videos/','/reel/','/watch')):
                item['media_embed']='https://www.facebook.com/plugins/video.php?href='+encoded+'&show_text=true&width=560'
                item['media_type']='facebook'
            elif '/posts/' in resolved.lower() or '/permalink/' in resolved.lower():
                item['media_embed']='https://www.facebook.com/plugins/post.php?href='+encoded+'&show_text=true&width=560'
                item['media_type']='facebook'
    except Exception as error:
        if len(enrichment_errors)<40:
            enrichment_errors.append((item.get('country'),item.get('category'),'publisher_'+type(error).__name__,str(error)[:160]))
    return item

# Share image-recovery capacity fairly across countries instead of letting

# Share image-recovery capacity fairly across countries instead of letting
# the newest few countries consume the entire global enrichment limit.
def fair_image_candidates(items, limit=100):
    groups={}
    for item in sorted(items,key=lambda x:x.get('published',''),reverse=True):
        code=str(item.get('country') or 'WORLD').upper()
        groups.setdefault(code,[]).append(item)
    selected=[]
    slot=int(os.environ.get('GITHUB_RUN_NUMBER') or (now.timestamp()//1800))

    # Always give Bangladesh local reports and global Bangla reports a place
    # in each batch; prioritize public missing-child/social alerts in BD.
    if groups.get('BD'):
        groups['BD'].sort(key=lambda x:(
            str(x.get('category','')).lower()=='missing' and any(
                token in str(x.get('source','')).lower() for token in ('facebook','youtube')
            ),
            str(x.get('category','')).lower()=='missing',
            x.get('published','')
        ),reverse=True)
        take=min(15,limit,len(groups['BD']))
        selected.extend(groups['BD'][:take])
        groups['BD']=groups['BD'][take:]
    if len(selected)<limit and groups.get('WORLD'):
        groups['WORLD'].sort(key=lambda x:(
            str(x.get('language',''))=='bn',x.get('published','')
        ),reverse=True)
        take=min(2,limit-len(selected),len(groups['WORLD']))
        selected.extend(groups['WORLD'][:take])
        groups['WORLD']=groups['WORLD'][take:]

    country_codes=sorted(code for code,group in groups.items() if group and code not in ('BD','WORLD'))
    if country_codes:
        for code in country_codes:
            offset=slot%len(groups[code])
            groups[code]=groups[code][offset:]+groups[code][:offset]
        start=(slot*limit)%len(country_codes)
        country_codes=country_codes[start:]+country_codes[:start]
    while len(selected)<limit:
        added=False
        for code in country_codes:
            if groups[code]:
                selected.append(groups[code].pop(0))
                added=True
                if len(selected)>=limit:
                    break
        if not added:
            break
    return selected

try:
    with open('news.json',encoding='utf-8') as cache_file:
        cache_data=json.load(cache_file)
    cache_stories=cache_data.get('news',[]) if isinstance(cache_data,dict) else cache_data
    previous_google_urls={str(x.get('google_news_url')) for x in cache_stories if x.get('google_news_url')}
except Exception:
    previous_google_urls=set()

image_candidates=fair_image_candidates(
    (x for x in fresh if (not x.get('image') or x.get('image') == GENERIC_IMAGE_URL or 'news.google.com/' in str(x.get('link',''))) and str(x.get('link','')) not in previous_google_urls),
    limit=500
)
print('Fresh image candidates selected fairly by country:',len(image_candidates))
with ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(enrich_article_image,image_candidates))
print('Fresh candidate images recovered:',sum(1 for x in image_candidates if x.get('image') and x.get('image') != GENERIC_IMAGE_URL))
print('Fresh Google News links resolved:',sum(1 for x in image_candidates if 'news.google.com/' not in str(x.get('link',''))))

patterns={
  'fire':r'\bfire\b|\bblaze\b|wildfire|আগুন|অগ্নিকাণ্ড',
  'abuse':r'rape|sexual assault|sexual violence|molest|ধর্ষণ|যৌন নির্যাতন|যৌন হয়রানি',
  'missing':r'missing child|child missing|missing (?:boy|girl|minor)|abducted child|নিখোঁজ শিশু|শিশু নিখোঁজ|নিখোঁজ কিশোরী|নিখোঁজ কিশোর|নিখোঁজ বালক|নিখোঁজ বালিকা',
  'accident':r'accident|crash|collision|derailment|shipwreck|দুর্ঘটনা|সংঘর্ষ|নৌকাডুবি',
  'casualty':r'death toll|fatalities|people killed|casualties|নিহত|প্রাণহানি|হতাহত',
  'reserve':r'foreign exchange reserves|forex reserves|foreign reserves|বৈদেশিক মুদ্রার রিজার্ভ|রিজার্ভ',
  'politics':r'election|vote|polling|parliament|government|minister|president|prime minister|opposition|cabinet|ruling party|political party|politics|নির্বাচন|ভোট|ভোটগ্রহণ|সংসদ|সরকার|মন্ত্রী|রাষ্ট্রপতি|প্রধানমন্ত্রী|বিরোধী দল|মন্ত্রিসভা|ক্ষমতাসীন দল|রাজনৈতিক দল|রাজনীতি',
  'economy':r'economy|inflation|GDP|budget|trade|exports|imports|central bank|banking|employment|remittance|tax|business|industry|wages|অর্থনীতি|মূল্যস্ফীতি|জিডিপি|বাজেট|বাণিজ্য|রপ্তানি|আমদানি|কেন্দ্রীয় ব্যাংক|ব্যাংকিং|কর্মসংস্থান|চাকরি|রেমিট্যান্স|কর|ব্যবসা|শিল্প|মজুরি',
  'sports':r'sports|football|cricket|tennis|basketball|tournament|world cup|league|match|player|coach|goal|wicket|olympics|FIFA|ICC|BPL|IPL|খেলাধুলা|ফুটবল|ক্রিকেট|টেনিস|বাস্কেটবল|টুর্নামেন্ট|বিশ্বকাপ|লিগ|ম্যাচ|খেলোয়াড়|কোচ|গোল|উইকেট|অলিম্পিক',
  'technology':r'technology|tech|artificial intelligence|cybersecurity|smartphone|mobile phone|software|internet|app|chip|gadget|startup|\bAI\b|প্রযুক্তি|প্রযুক্তিপণ্য|কৃত্রিম বুদ্ধিমত্তা|এআই|সফটওয়্যার|স্মার্টফোন|মোবাইল|অ্যাপ|ইন্টারনেট|সাইবার নিরাপত্তা|চিপ|গ্যাজেট|স্টার্টআপ',
  'entertainment':r'movie|film|cinema|anime|television series|web series|streaming|actor|actress|celebrity|singer|music|album|drama|Netflix|concert|box office|তারকা|সংগীত|গান|অ্যালবাম|নাটক|কনসার্ট|বক্স অফিস|সিনেমা|চলচ্চিত্র|অ্যানিমে|টিভি সিরিজ|ওয়েব সিরিজ|অভিনেতা|অভিনেত্রী',
  'market':r'stock market|share market|stock exchange|share price|shares|stocks|DSE|Dhaka Stock Exchange|Nasdaq|Dow Jones|trading session|শেয়ার বাজার|শেয়ারবাজার|পুঁজিবাজার|স্টক এক্সচেঞ্জ|শেয়ারদর|শেয়ারের দাম|ডিএসই|ঢাকা স্টক এক্সচেঞ্জ|শেয়ার|সূচক'
}
# Country labels must describe the reported incident, not the Google News
# edition used to discover it. Use only explicit location evidence; otherwise
# keep the story in WORLD rather than publishing a guessed country.
INCIDENT_LOCATION_ALIASES = {
    'BD': ('bangladesh','bangladeshi','dhaka','chattogram','chittagong','sylhet','rajshahi','khulna','barishal','rangpur','mymensingh',"cox's bazar",'fatullah','fatulla','pallabi','gopalganj','madhabpur','narayanganj','brahmanbaria','bogura','bogra','cumilla','comilla','feni','noakhali','pabna','kushtia','jashore','jessore','satkhira','bagerhat','patuakhali','bhola','habiganj','moulvibazar','sunamganj','netrokona','jamalpur','sherpur','tangail','manikganj','munshiganj','narsingdi','gazipur','faridpur','madaripur','shariatpur','chandpur','lakshmipur','rangamati','bandarban','khagrachhari','dinajpur','thakurgaon','panchagarh','nilphamari','lalmonirhat','kurigram','gaibandha','joypurhat','naogaon','natore','chapainawabganj','sirajganj','meherpur','chuadanga','jhenaidah','magura','narail','jhalokathi','barguna','dhamrai','akhaura','rangunia','boda','বোদা','বোদা উপজেলায়','বোদা উপজেলায়','subarnachar','সুবর্ণচর','সুবর্ণচরে','সুবর্ণচরের','gabtoli','গাবতলী','kalai','কালাই','ঢাকা স্টক এক্সচেঞ্জ','ডিএসই','জুলাই গণঅভ্যুত্থান','প্রাথমিকের নতুন পাঠ্যক্রম','ধামরাই','ধামরাইয়ে','ধামরাইয়ে','আখাউড়া','আখাউড়ায়','আখাউড়ায়','রাঙ্গুনিয়া','রাঙ্গুনিয়ায়','রাঙ্গুনিয়া','রাঙ্গুনিয়ায়','বাংলাদেশ','ঢাকা','চট্টগ্রাম','চাটগাঁ','সিলেট','রাজশাহী','খুলনা','বরিশাল','রংপুর','ময়মনসিংহ','ময়মনসিংহ','কক্সবাজার','ফতুল্লা','ফতুল্লায়','পল্লবী','পল্লবীতে','গোপালগঞ্জ','গোপালগঞ্জে','মাধবপুর','মাধবপুরে','নারায়ণগঞ্জ','নারায়ণগঞ্জ','ব্রাহ্মণবাড়িয়া','ব্রাহ্মণবাড়িয়া','বগুড়া','বগুড়া','কুমিল্লা','কুমিল্লায়','কুমিল্লায়','ফেনী','নোয়াখালী','নোয়াখালী','পাবনা','কুষ্টিয়া','কুষ্টিয়া','যশোর','সাতক্ষীরা','বাগেরহাট','পটুয়াখালী','পটুয়াখালী','ভোলা','হবিগঞ্জ','মৌলভীবাজার','সুনামগঞ্জ','নেত্রকোনা','জামালপুর','শেরপুর','টাঙ্গাইল','মানিকগঞ্জ','মুন্সিগঞ্জ','নরসিংদী','গাজীপুর','ফরিদপুর','মাদারীপুর','শরীয়তপুর','শরিয়তপুর','চাঁদপুর','লক্ষ্মীপুর','রাঙামাটি','রাঙ্গামাটি','বান্দরবান','খাগড়াছড়ি','খাগড়াছড়ি','দিনাজপুর','ঠাকুরগাঁও','পঞ্চগড়','পঞ্চগড়','নীলফামারী','লালমনিরহাট','কুড়িগ্রাম','কুড়িগ্রাম','গাইবান্ধা','জয়পুরহাট','জয়পুরহাট','নওগাঁ','নাটোর','চাঁপাইনবাবগঞ্জ','সিরাজগঞ্জ','মেহেরপুর','চুয়াডাঙ্গা','চুয়াডাঙ্গা','ঝিনাইদহ','মাগুরা','নড়াইল','নড়াইল','ঝালকাঠি','বরগুনা'),
    'US': ('united states','u.s.','usa','american','new york city','new york','chicago','los angeles','san francisco','washington dc','washington, d.c.','florida','texas','ohio','california','naples','springfield','bethel township','auburn gresham','athens, georgia','brooklyn','যুক্তরাষ্ট্রে নিযুক্ত'),
    'GB': ('united kingdom','britain','british','england','scotland','wales','london','kent','maidstone','liverpool','bathgate','west lothian','dundee','glasgow'),
    'IN': ('india','indian','delhi','new delhi','mumbai','kolkata','chennai','bengaluru','bangalore','hyderabad','assam','assamese','guwahati','markapuram','mysuru','jammu and kashmir','j&k','আসাম','আসামে','গুয়াহাটি','গুৱাহাটী'),
    'ID': ('indonesia','indonesian','jakarta','bali','surabaya'),
    'UA': ('ukraine','ukrainian','kyiv','khmelnytskyi','odesa','kharkiv','donetsk'),
    'EG': ('egypt','egyptian','cairo','alexandria'),
    'FR': ('france','french','paris','lyon','marseille'),
    'DE': ('germany','german','berlin','munich','hamburg'),
    'PL': ('poland','polish','krakow','kraków','warsaw'),
    'PS': ('gaza','west bank','palestine','palestinian','গাজা','গাজায়','গাজায়','গাজার','পশ্চিম তীর'),
    'IL': ('israel','israeli','tel aviv','jerusalem'),
    'CA': ('canada','canadian','ontario','quebec','toronto','sudbury','vancouver'),
    'AU': ('australia','australian','sydney','melbourne','brisbane'),
    'NZ': ('new zealand','auckland','wellington'),
    'PK': ('pakistan','pakistani','islamabad','karachi','lahore','পাকিস্তান','ইসলামাবাদ','করাচি','লাহোর'),
    'MY': ('malaysia','malaysian','kuala lumpur','মালয়েশিয়া','মালয়েশিয়া','কুয়ালালামপুর','কুয়ালালামপুর'),
    'SG': ('singapore','singaporean'),
    'ZA': ('south africa','south african','johannesburg','cape town'),
    'KE': ('kenya','kenyan','nairobi'),
    'NG': ('nigeria','nigerian','lagos','abuja'),
    'RU': ('russia','russian','moscow'),
    'TR': ('turkey','türkiye','turkish','ankara','istanbul'),
    'IR': ('iran','iranian','tehran','ইরান','তেহরান'),
    'SA': ('saudi arabia','saudi','riyadh','সৌদি আরব','রিয়াদ','রিয়াদ'),
    'AE': ('united arab emirates','uae','emirates','dubai','abu dhabi','আমিরাত','আমিরাতে','আমিরাতের','সংযুক্ত আরব আমিরাত','দুবাই','আবুধাবি'),
    'JP': ('japan','japanese','tokyo','osaka','জাপান','টোকিও','ওসাকা'),
    'CN': ('china','chinese','beijing','shanghai','চীন','বেইজিং','সাংহাই'),
    'KR': ('south korea','south korean','seoul','দক্ষিণ কোরিয়া','দক্ষিণ কোরিয়া','সিউল'),
    'TH': ('thailand','thai','bangkok'),
    'VN': ('vietnam','vietnamese','hanoi','ho chi minh city'),
    'BR': ('brazil','brazilian','rio de janeiro','sao paulo'),
    'MX': ('mexico','mexican','mexico city'),
    'AR': ('argentina','argentinian','buenos aires'),
    'ES': ('spain','spanish','madrid','barcelona'),
    'IT': ('italy','italian','rome','milan'),
    'NL': ('netherlands','dutch','amsterdam'),
    'BE': ('belgium','belgian','brussels'),
    'CH': ('switzerland','swiss','zurich','geneva'),
    'SE': ('sweden','swedish','stockholm'),
    'NO': ('norway','norwegian','oslo'),
    'DK': ('denmark','danish','copenhagen'),
    'IE': ('ireland','irish','dublin'),
    'GR': ('greece','greek','athens'),
    'CZ': ('czech republic','czechia','prague'),
    'RO': ('romania','romanian','bucharest'),
    'ET': ('ethiopia','ethiopian','addis ababa'),
    'TZ': ('tanzania','tanzanian','dar es salaam'),
    'UG': ('uganda','ugandan','kampala'),
    'ZW': ('zimbabwe','zimbabwean','harare'),
    'AF': ('afghanistan','afghan','kabul'),
    'HK': ('hong kong','hong konger'),
    'MO': ('macau','macao','macanese'),
    'TW': ('taiwan','taiwanese','taipei','kaohsiung','tainan'),
    'XK': ('kosovo','kosovar','pristina','prishtina'),
}
INCIDENT_PLACE_ALIASES = {
    'BD': ('dhaka','chattogram','chittagong','sylhet','rajshahi','khulna','barishal','rangpur','mymensingh',"cox's bazar",'fatullah','fatulla','pallabi','gopalganj','madhabpur','narayanganj','brahmanbaria','bogura','bogra','cumilla','comilla','feni','noakhali','pabna','kushtia','jashore','jessore','satkhira','bagerhat','patuakhali','bhola','habiganj','moulvibazar','sunamganj','netrokona','jamalpur','sherpur','tangail','manikganj','munshiganj','narsingdi','gazipur','faridpur','madaripur','shariatpur','chandpur','lakshmipur','rangamati','bandarban','khagrachhari','dinajpur','thakurgaon','panchagarh','nilphamari','lalmonirhat','kurigram','gaibandha','joypurhat','naogaon','natore','chapainawabganj','sirajganj','meherpur','chuadanga','jhenaidah','magura','narail','jhalokathi','barguna','dhamrai','akhaura','rangunia','gabtoli','kalai','ঢাকা স্টক এক্সচেঞ্জ','ডিএসই','জুলাই গণঅভ্যুত্থান','প্রাথমিকের নতুন পাঠ্যক্রম','ধামরাই','ধামরাইয়ে','ধামরাইয়ে','আখাউড়া','আখাউড়ায়','আখাউড়ায়','রাঙ্গুনিয়া','রাঙ্গুনিয়ায়','রাঙ্গুনিয়া','রাঙ্গুনিয়ায়','বাংলাদেশ','ঢাকা','চট্টগ্রাম','চাটগাঁ','সিলেট','রাজশাহী','খুলনা','বরিশাল','রংপুর','ময়মনসিংহ','ময়মনসিংহ','কক্সবাজার','ফতুল্লা','ফতুল্লায়','পল্লবী','পল্লবীতে','গোপালগঞ্জ','গোপালগঞ্জে','মাধবপুর','মাধবপুরে','নারায়ণগঞ্জ','নারায়ণগঞ্জ','ব্রাহ্মণবাড়িয়া','ব্রাহ্মণবাড়িয়া','বগুড়া','বগুড়া','কুমিল্লা','কুমিল্লায়','কুমিল্লায়','ফেনী','নোয়াখালী','নোয়াখালী','পাবনা','কুষ্টিয়া','কুষ্টিয়া','যশোর','সাতক্ষীরা','বাগেরহাট','পটুয়াখালী','পটুয়াখালী','ভোলা','হবিগঞ্জ','মৌলভীবাজার','সুনামগঞ্জ','নেত্রকোনা','জামালপুর','শেরপুর','টাঙ্গাইল','মানিকগঞ্জ','মুন্সিগঞ্জ','নরসিংদী','গাজীপুর','ফরিদপুর','মাদারীপুর','শরীয়তপুর','শরিয়তপুর','চাঁদপুর','লক্ষ্মীপুর','রাঙামাটি','রাঙ্গামাটি','বান্দরবান','খাগড়াছড়ি','খাগড়াছড়ি','দিনাজপুর','ঠাকুরগাঁও','পঞ্চগড়','পঞ্চগড়','নীলফামারী','লালমনিরহাট','কুড়িগ্রাম','কুড়িগ্রাম','গাইবান্ধা','জয়পুরহাট','জয়পুরহাট','নওগাঁ','নাটোর','চাঁপাইনবাবগঞ্জ','সিরাজগঞ্জ','মেহেরপুর','চুয়াডাঙ্গা','চুয়াডাঙ্গা','ঝিনাইদহ','মাগুরা','নড়াইল','নড়াইল','ঝালকাঠি','বরগুনা'),
    'US': ('new york city','new york','chicago','los angeles','san francisco','washington dc','washington, d.c.','florida','texas','ohio','california','naples','springfield','bethel township','auburn gresham','athens, georgia','brooklyn'),
    'GB': ('london','kent','maidstone','liverpool','bathgate','west lothian','dundee','glasgow'),
    'IN': ('delhi','new delhi','mumbai','kolkata','chennai','bengaluru','bangalore','hyderabad','assam','guwahati','markapuram','mysuru','jammu and kashmir','j&k','আসাম','আসামে','গুয়াহাটি','গুৱাহাটী'),
    'ID': ('jakarta','bali','surabaya'),
    'UA': ('kyiv','khmelnytskyi','odesa','kharkiv','donetsk'),
    'EG': ('cairo','alexandria'),
    'FR': ('paris','lyon','marseille'),
    'DE': ('berlin','munich','hamburg'),
    'PL': ('krakow','kraków','warsaw'),
    'PS': ('gaza','west bank'),
    'IL': ('tel aviv','jerusalem'),
    'CA': ('ontario','quebec','toronto','sudbury','vancouver'),
    'AU': ('sydney','melbourne','brisbane'),
    'NZ': ('auckland','wellington'),
    'PK': ('islamabad','karachi','lahore','ইসলামাবাদ','করাচি','লাহোর'),
    'MY': ('kuala lumpur','কুয়ালালামপুর','কুয়ালালামপুর'),
    'ZA': ('johannesburg','cape town'),
    'KE': ('nairobi',),
    'NG': ('lagos','abuja'),
    'RU': ('moscow',),
    'TR': ('ankara','istanbul'),
    'IR': ('tehran','তেহরান'),
    'SA': ('riyadh','রিয়াদ','রিয়াদ'),
    'AE': ('dubai','abu dhabi','দুবাই','আবুধাবি'),
    'JP': ('tokyo','osaka','টোকিও','ওসাকা'),
    'CN': ('beijing','shanghai','বেইজিং','সাংহাই'),
    'KR': ('seoul','সিউল'),
    'TH': ('bangkok',),
    'VN': ('hanoi','ho chi minh city'),
    'BR': ('rio de janeiro','sao paulo'),
    'MX': ('mexico city',),
    'AR': ('buenos aires',),
    'ES': ('madrid','barcelona'),
    'IT': ('rome','milan'),
    'NL': ('amsterdam',),
    'BE': ('brussels',),
    'CH': ('zurich','geneva'),
    'SE': ('stockholm',),
    'NO': ('oslo',),
    'DK': ('copenhagen',),
    'IE': ('dublin',),
    'GR': ('athens',),
    'CZ': ('prague',),
    'RO': ('bucharest',),
    'ET': ('addis ababa',),
    'TZ': ('dar es salaam',),
    'UG': ('kampala',),
    'ZW': ('harare',),
    'AF': ('kabul',),
    'HK': ('hong kong',),
    'MO': ('macau','macao'),
    'TW': ('taipei','kaohsiung','tainan'),
    'XK': ('pristina','prishtina'),
}
def incident_country(item):
    story=' '+(str(item.get('title',''))+' '+str(item.get('summary',''))).lower()+' '
    # Specific places are checked before demonyms/country names so that,
    # for example, a city in Ukraine wins over a headline mentioning Russia.
    priority = ('BD','US','GB','IN','ID','UA','EG','FR','DE','PL','PS','IL','CA','AU','NZ','PK','MY','SG','ZA','KE','NG','RU','TR','IR','SA','AE','JP','CN','KR','TH','VN','BR','MX','AR','ES','IT','NL','BE','CH','SE','NO','DK','IE','GR','CZ','RO','ET','TZ','UG','ZW','AF','HK','MO','TW','XK')
    for aliases in (INCIDENT_PLACE_ALIASES, INCIDENT_LOCATION_ALIASES):
        for code in priority:
            for alias in aliases.get(code, ()):
                if re.search(r'(?<![a-z])'+re.escape(alias)+r'(?![a-z])',story,re.I):
                    return code
    return 'WORLD'

def classify(item):
    s=(item.get('title','')+' '+item.get('summary','')).lower()
    # A recovered/found-child notice must never be shown as an active missing-child alert.
    if re.search(r'found child|child found|reunited|recovered child|খুঁজে পাওয়া শিশু|খুঁজে পাওয়া গেছে|উদ্ধার হওয়া শিশু|পরিবারে ফিরেছে',s,re.I):
        return ''
    if 'munalert.org' in str(item.get('link','')).lower() or 'mun alert' in str(item.get('source','')).lower(): return 'missing'
    # Classify from the actual headline/summary first; feed query labels can be wrong.
    for key in ('abuse','missing','fire','accident','casualty','reserve','politics','economy','sports','technology','entertainment','market'):
        if re.search(patterns[key],s,re.I): return key
    # Never trust a feed's fire label by itself: broad feeds can match sports,
    # ceasefire and other unrelated stories. A real fire incident must match
    # the headline/summary fire pattern above.
    fallback=item.get('category','')
    return fallback if fallback in patterns and fallback!='fire' else ''

try:
    with open('news.json',encoding='utf-8') as file:
        old=json.load(file)
        previous=old.get('news',[]) if isinstance(old,dict) else old
except Exception: previous=[]

# Backfill older stored stories too; otherwise the site keeps showing
# the old no-image placeholder even after the collector is improved.
previous_image_candidates=fair_image_candidates(
    (x for x in previous if not x.get('image') or x.get('image') == GENERIC_IMAGE_URL or 'news.google.com/' in str(x.get('link','')) or not str(x.get('summary','')).strip()),
    # Process a rotating batch each run so thousands of old stories do not
    # monopolize the 35-minute workflow or delay fresh news collection.
    limit=200
)
print('Previous image candidates selected fairly by country:',len(previous_image_candidates))
with ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(enrich_article_image,previous_image_candidates))
print('Previous candidate images recovered:',sum(1 for x in previous_image_candidates if x.get('image') and x.get('image') != GENERIC_IMAGE_URL))
print('Previous Google News links resolved:',sum(1 for x in previous_image_candidates if 'news.google.com/' not in str(x.get('link',''))))
print('Image/link enrichment errors sampled:',len(enrichment_errors))
for error in enrichment_errors[:20]:
    print('Enrichment error sample:',error)

# Never allow the known generic Google thumbnail through merely because it
# still has an HTTPS URL after a candidate was not enriched.
for item in previous+fresh:
    if item.get('image') == GENERIC_IMAGE_URL:
        item['image']=''

import difflib, hashlib
by_link={}
for item in previous+fresh:
    link=item.get('link') or item.get('url','')
    published=parse_date(item.get('published') or item.get('pubDate') or item.get('date',''))
    if not link or not published or published>now+timedelta(hours=2): continue
    category=classify(item)
    if not category: continue
    # Apply the retention window only after identifying this story's real category.
    if published<cutoff_for_category(category): continue
    item['link']=link
    item['published']=published.isoformat()
    item['category']=category
    detected_country=incident_country(item)
    # Bangladesh-publisher discovery feeds are explicitly scoped to trusted BD outlets.
    # Preserve an explicit foreign location, but use the BD feed scope when the
    # headline itself does not name a country or city.
    if detected_country=='WORLD' and str(item.get('country','')).upper()=='BD':
        detected_country='BD'
    item['country']=detected_country
    item.setdefault('summary',item.get('description',''))
    item.setdefault('verification_status','source_reported')
    old_item=by_link.get(link)
    if old_item is None:
        by_link[link]=item
    else:
        if not old_item.get('image') and item.get('image'):
            old_item['image']=item['image']
        # Preserve alternative RSS thumbnails across duplicate feed editions.
        candidates=list(old_item.get('image_candidates') or [])
        for candidate in [item.get('image','')]+list(item.get('image_candidates') or []):
            candidate=str(candidate or '').strip()
            if candidate.startswith(('https://','http://')) and candidate!=GENERIC_IMAGE_URL and candidate not in candidates:
                candidates.append(candidate)
        if candidates:
            old_item['image_candidates']=candidates[:12]
        if not str(old_item.get('summary','')).strip() and str(item.get('summary','')).strip():
            old_item['summary']=item['summary']
        if not old_item.get('media_embed') and item.get('media_embed'):
            old_item['media_embed']=item['media_embed']
            old_item['media_type']=item.get('media_type','')
        if not old_item.get('google_news_url') and item.get('google_news_url'):
            old_item['google_news_url']=item['google_news_url']

# Conservative incident grouping: same country/category/date and near-identical headlines.
# Keep one visible record, but preserve the other publishers as related sources.
buckets={}
incidents=[]
for item in sorted(by_link.values(),key=lambda x:x['published'],reverse=True):
    title=re.sub(r'[^\w\u0980-\u09ff]+',' ',item.get('title','').lower()).strip()
    title=re.sub(r'\b(?:breaking|update|latest)\b',' ',title)
    tokens=set(title.split())
    day=parse_date(item['published']).date().isoformat()
    bucket=(item['country'],item['category'],day)
    match=None
    for idx in buckets.get(bucket,[]):
        other=incidents[idx]
        other_title=other.get('_normalized_title','')
        other_tokens=set(other_title.split())
        ratio=difflib.SequenceMatcher(None,title,other_title).ratio()
        union=tokens|other_tokens
        overlap=len(tokens&other_tokens)/len(union) if union else 0
        if ratio>=0.90 or overlap>=0.88:
            match=other
            break
    source={'name':item.get('source','সংবাদসূত্র'),'link':item['link']}
    if match is not None:
        sources=match.setdefault('related_sources',[])
        if not any(s.get('link')==source['link'] for s in sources):
            sources.append(source)
        match['source_count']=len(sources)+1
        if not match.get('image') and item.get('image'):
            match['image']=item['image']
        # Keep alternative thumbnails across near-identical reports too.
        candidates=list(match.get('image_candidates') or [])
        for candidate in [item.get('image','')]+list(item.get('image_candidates') or []):
            candidate=str(candidate or '').strip()
            if candidate.startswith(('https://','http://')) and candidate!=GENERIC_IMAGE_URL and candidate not in candidates:
                candidates.append(candidate)
        if candidates:
            match['image_candidates']=candidates[:12]
    else:
        item['_normalized_title']=title
        item['incident_id']=hashlib.sha1((item['country']+'|'+item['category']+'|'+day+'|'+title).encode('utf-8')).hexdigest()[:16]
        item['related_sources']=[]
        item['source_count']=1
        idx=len(incidents)
        incidents.append(item)
        buckets.setdefault(bucket,[]).append(idx)

for item in incidents:
    item.pop('_normalized_title',None)
# Strict image rule: never publish a text-only news card.
# If no real publisher/RSS thumbnail could be recovered, hold the story back.
incidents_with_images=[
    item for item in incidents
    if str(item.get('image','')).startswith(('https://','http://'))
    and item.get('image') != GENERIC_IMAGE_URL
]
print('Stories held back because no image was found:',len(incidents)-len(incidents_with_images))
news=sorted(incidents_with_images,key=lambda x:x['published'],reverse=True)[:12000]

# Final canonical-link deduplication catches duplicate items that arrived
# through different Google News country editions.
unique_news={}
for item in news:
    canonical=str(item.get('link','')).strip().split('#',1)[0].rstrip('/')
    if not canonical:
        continue
    old=unique_news.get(canonical)
    if old is None:
        unique_news[canonical]=item
    else:
        sources=old.setdefault('related_sources',[])
        candidate_source={'name':item.get('source','সংবাদসূত্র'),'link':item.get('link','')}
        if candidate_source['link'] and not any(x.get('link')==candidate_source['link'] for x in sources):
            sources.append(candidate_source)
        old['source_count']=max(int(old.get('source_count',1)),int(item.get('source_count',1)),len(sources)+1)
        if not old.get('image') and item.get('image'):
            old['image']=item['image']
        if not str(old.get('summary','')).strip() and str(item.get('summary','')).strip():
            old['summary']=item['summary']
news=list(unique_news.values())

# Normalize language on legacy records as well as newly collected records.
def anonymize_sensitive_story(item):
    category=str(item.get('category','')).lower()
    language=item.get('language') or ('bn' if re.search('[ঀ-৿]',str(item.get('title',''))+' '+str(item.get('summary',''))) else 'en')
    country=str(item.get('country','')).upper()
    if category=='missing':
        if language=='bn':
            item['title']='নিখোঁজ শিশুর সতর্কতা — '+country
            item['summary']='শিশুর নাম, বয়স ও ব্যক্তিগত পরিচয় এখানে পুনরায় প্রকাশ করা হচ্ছে না। যাচাইকৃত তথ্য ও যোগাযোগের নির্দেশনা দেখতে মূল সংবাদসূত্র খুলুন।'
        else:
            item['title']='Missing-child alert — '+country
            item['summary']='The child’s name, age and personal details are withheld. Open the original source for verified information and contact instructions.'
    elif category=='abuse':
        if language=='bn':
            item['title']='যৌন সহিংসতার অভিযোগের প্রতিবেদন — '+country
            item['summary']='ভুক্তভোগীর পরিচয় ও ব্যক্তিগত তথ্য গোপন রাখা হয়েছে। বিস্তারিত জানতে মূল সংবাদসূত্র খুলুন।'
        else:
            item['title']='Sexual-violence report — '+country
            item['summary']='The survivor’s identity and personal details are withheld. Open the original source for verified reporting.'
    item['language']=language
    return item

for item in news:
    if not item.get('language'):
        item['language']='bn' if re.search('[ঀ-৿]',str(item.get('title',''))+' '+str(item.get('summary',''))) else 'en'
    anonymize_sensitive_story(item)

# Verify that newly published image URLs really return image data, not an
# HTML error page. Successful checks are cached for seven days.
def verify_image_url(item):
    # Try every distinct RSS thumbnail, not just the first one: publishers
    # sometimes include stale tracking images before the actual article photo.
    candidates=[]
    for candidate in [item.get('image','')]+list(item.get('image_candidates') or []):
        candidate=str(candidate or '').strip()
        if candidate.startswith('https://') and candidate!=GENERIC_IMAGE_URL and candidate not in candidates:
            candidates.append(candidate)
    verified_at=item.get('image_verified_at')
    if verified_at and candidates and item.get('image')==candidates[0]:
        try:
            verified_dt=datetime.fromisoformat(str(verified_at).replace('Z','+00:00'))
            if verified_dt.tzinfo is None:
                verified_dt=verified_dt.replace(tzinfo=now.tzinfo)
            if (now-verified_dt).total_seconds()<7*24*60*60:
                return item,True,'cached'
        except Exception:
            pass
    headers={
        'User-Agent':CHROME_UA,
        'Accept':'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Range':'bytes=0-2047',
        'Referer':'https://all-in-one-news.github.io/all-in-one-news/'
    }
    last_error='no-image-candidate'
    for image_url in candidates:
        host=urllib.parse.urlsplit(image_url).netloc
        try:
            req=urllib.request.Request(image_url,headers=headers)
            with urllib.request.urlopen(req,timeout=8) as response:
                content_type=str(response.headers.get('Content-Type','')).split(';',1)[0].lower()
                sample=response.read(32)
            valid=content_type.startswith('image/') or sample.startswith((
                bytes.fromhex('ffd8ff'),bytes.fromhex('89504e470d0a'),b'GIF87a',b'GIF89a'
            )) or (sample[:4]==b'RIFF' and sample[8:12]==b'WEBP')
            if valid:
                item['image']=image_url
                item['image_verified_at']=now.isoformat()
                item.pop('image_candidates',None)
                return item,True,host
            last_error=host+':not-image'
        except Exception as error:
            last_error=host+':'+type(error).__name__
    return item,False,last_error

with ThreadPoolExecutor(max_workers=6) as pool:
    image_checks=list(pool.map(verify_image_url,news))
verified_news=[]
failed_image_hosts=[]
for checked_item,is_valid,detail in image_checks:
    if is_valid:
        verified_news.append(checked_item)
    else:
        failed_image_hosts.append(detail)
print('Image URL checks:',len(image_checks),'verified:',len(verified_news),'rejected:',len(failed_image_hosts))
if failed_image_hosts:
    print('Rejected image hosts:',failed_image_hosts[:20])
news=verified_news

# Do not deduplicate stories by thumbnail URL: publishers may reuse the
# same image for separate articles. Canonical-link and incident-level
# deduplication above already remove duplicate coverage safely.

# Sanitize the last-good snapshot too, so the frontend fallback does not
# re-expose personal details from an older version.
backup_candidate='news-backup.candidate.json'
if os.path.isfile(backup_candidate):
    try:
        with open(backup_candidate,encoding='utf-8') as backup_file:
            backup_data=json.load(backup_file)
        backup_stories=backup_data.get('news',[]) if isinstance(backup_data,dict) else backup_data
        for backup_item in backup_stories:
            anonymize_sensitive_story(backup_item)
        with open(backup_candidate,'w',encoding='utf-8') as backup_file:
            json.dump(backup_data,backup_file,ensure_ascii=False,separators=(',',':'))
    except Exception as error:
        raise RuntimeError('Could not sanitize last-good backup: '+str(error))

# Never replace a healthy feed with an unexpectedly empty or drastically smaller run.
previous_good_count=sum(1 for x in previous if str(x.get('image','')).startswith(('https://','http://')) and x.get('image') != GENERIC_IMAGE_URL)
minimum_safe_count=max(10, int(previous_good_count*0.50))
if len(news)<minimum_safe_count:
    raise SystemExit(
        f"Safety stop: collected {len(news)} image-backed stories; "
        f"minimum safe count is {minimum_safe_count}. Existing news.json is preserved."
    )
# Validate the candidate before atomically replacing the published data file.
news_tmp='news.json.tmp'
with open(news_tmp,'w',encoding='utf-8') as file:
    json.dump({'updated_at':now.isoformat(),'news':news},file,ensure_ascii=False,indent=2)
with open(news_tmp,encoding='utf-8') as file:
    candidate=json.load(file)
if not isinstance(candidate,dict) or not isinstance(candidate.get('news'),list):
    raise SystemExit("Safety stop: generated news JSON has an invalid structure.")
if not candidate['news'] or any(not str(x.get('image','')).startswith(('https://','http://')) for x in candidate['news']):
    raise SystemExit("Safety stop: generated news JSON is empty or contains a story without an image.")
os.replace(news_tmp,'news.json')
# Build crawlable article pages automatically for recent stories.
import html, os
from urllib.parse import quote
base='https://all-in-one-news.github.io/all-in-one-news'
sitemap_urls=[base+'/']

for item in news:
    published=parse_date(item.get('published',''))
    if not published or published<cutoff_for_category(item.get('category')):
        continue
    article_id=re.sub(r'[^a-f0-9]','',str(item.get('incident_id') or hashlib.sha1(item['link'].encode()).hexdigest()))[:20]
    if not article_id:
        continue
    folder=os.path.join('articles',article_id)
    os.makedirs(folder,exist_ok=True)
    url=base+'/articles/'+article_id+'/'
    title=html.escape(str(item.get('title','News') or 'News'))
    summary=html.escape(re.sub(r'<[^>]+>',' ',str(item.get('summary','') or ''))[:1000])
    source=html.escape(str(item.get('source','News source') or 'News source'))
    link=html.escape(str(item.get('link','')),quote=True)
    image=str(item.get('image','') or '')
    image_tag=''
    image_json=''
    if image.startswith(('https://','http://')):
        image_tag='<img src="'+html.escape(image,quote=True)+'" alt="'+title+'" style="max-width:100%;height:auto">'
        image_json='"image":'+json.dumps(image,ensure_ascii=False)+','
    date=published.isoformat()
    page='''<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>'''+title+''' | All In One News</title>
<meta name="description" content="'''+summary[:300]+'''">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="'''+url+'''">
<meta property="og:type" content="article"><meta property="og:title" content="'''+title+'''">
<meta property="og:description" content="'''+summary[:300]+'''"><meta property="og:url" content="'''+url+'''">\n<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="'''+title+'''"><meta name="twitter:description" content="'''+summary[:300]+'''">
'''+('<meta property="og:image" content="'+html.escape(image,quote=True)+'">' if image_tag else '')+'''
<script type="application/ld+json">'''+json.dumps({"@context":"https://schema.org","@type":"NewsArticle","headline":str(item.get('title','News')),"datePublished":date,"dateModified":date,"mainEntityOfPage":url,"publisher":{"@type":"Organization","name":"All In One News"},"author":{"@type":"Organization","name":source},"description":str(item.get('summary','') or '')[:1000],**({"image":[image]} if image_tag else {})},ensure_ascii=False).replace('</','<\\/')+'''</script></head><body style="font-family:system-ui;max-width:760px;margin:32px auto;padding:0 16px;line-height:1.7">
<p><a href="../../">All In One News</a> · '''+source+'''</p><h1>'''+title+'''</h1><time datetime="'''+date+'''">'''+date+'''</time>'''+image_tag+'''<p>'''+summary+'''</p><p>মূল সংবাদ: <a href="'''+link+'''" rel="nofollow noopener" target="_blank">'''+source+'''</a></p></body></html>'''
    with open(os.path.join(folder,'index.html'),'w',encoding='utf-8') as out:
        out.write(page)
    sitemap_urls.append(url)
with open('sitemap.xml','w',encoding='utf-8') as out:
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    for url in sitemap_urls:
        out.write('  <url><loc>'+html.escape(url)+'</loc><lastmod>'+now.date().isoformat()+'</lastmod></url>\n')
    out.write('</urlset>\n')
print('SEO article pages generated:',len(sitemap_urls)-1)
print('Country/category feeds:',len(feeds))
print('Dedicated Bangladesh MUN Alert discovery feed: enabled')
print('Public Facebook and YouTube discovery feeds: enabled')
print('Bangladesh Police/CID and trusted newsroom discovery feeds: enabled')
print('Unique countries in published news:',len({x.get('country') for x in news}))
print('Countries represented:',','.join(sorted({x.get('country','') for x in news})))
print('Categorized records since 2026-01-01:',len(news))
