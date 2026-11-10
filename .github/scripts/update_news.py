import json, re, os, time, http.cookiejar, urllib.request, urllib.parse, urllib.error, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
GENERIC_IMAGE_URL='https://lh3.googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc=s0-w300'

now = datetime.now(timezone.utc)
cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
countries = [
    'AF','AL','DZ','AD','AO','AG','AR','AM','AU','AT','AZ','BS','BH','BD','BB','BY','BE','BZ','BJ','BT','BO','BA','BW','BR','BN','BG','BF','BI','CV','KH','CM','CA','CF','TD','CL','CN','CO','KM','CG','CR',
    'CI','HR','CU','CY','CZ','CD','DK','DJ','DM','DO','EC','EG','SV','GQ','ER','EE','SZ','ET','FJ','FI','FR','GA','GM','GE','DE','GH','GR','GD','GT','GN','GW','GY','HT','HN','HU','IS','IN','ID','IR','IQ',
    'IE','IL','IT','JM','JP','JO','KZ','KE','KI','KP','KR','KW','KG','LA','LV','LB','LS','LR','LY','LI','LT','LU','MG','MW','MY','MV','ML','MT','MH','MR','MU','MX','FM','MD','MC','MN','ME','MA','MZ','MM',
    'NA','NR','NP','NL','NZ','NI','NE','NG','MK','NO','OM','PK','PW','PA','PG','PY','PE','PH','PL','PT','QA','RO','RU','RW','KN','LC','VC','WS','SM','ST','SA','SN','RS','SC','SL','SG','SK','SI','SB','SO',
    'ZA','SS','ES','LK','SD','SR','SE','CH','SY','TJ','TZ','TH','TL','TG','TO','TT','TN','TR','TM','TV','UG','UA','AE','GB','US','UY','UZ','VU','VA','VE','VN','YE','ZM','ZW','PS',
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
for country in countries:
    for category, query in categories.items():
        q = query
        lang='en'
        if country == 'BD':
            q = '(' + query + ') OR (' + bangla[category] + ')'
            lang='bn'
        params = urllib.parse.urlencode({
            'q': q + ' after:2025-12-31',
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
        'q':'('+query+') after:2025-12-31',
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
        'q':social_query+' after:2025-12-31',
        'hl':'bn','gl':'BD','ceid':'BD:bn'
    })
    feeds.append(('BD','missing',
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
        'q':trusted_query+' after:2025-12-31',
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
            if not title or not link or not published or published<cutoff or published>now+timedelta(hours=2): continue
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
            for sub in node.iter():
                if local(sub.tag)=='source' and ''.join(sub.itertext()).strip():
                    source=''.join(sub.itertext()).strip(); break
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
                'title':re.sub(r'\\s+',' ',title),
                'summary':re.sub(r'<[^>]+>',' ',summary)[:1200],
                'link':link,'source':source,'published':published.isoformat(),
                'image':image,'media_embed':media_embed,'media_type':media_type,'country':country,'category':category,
                'language':'bn' if re.search('[ঀ-৿]',title+' '+summary) else 'en',
                'verification_status':'official_source' if ('mun alert' in source.lower() or 'munalert.org' in link.lower() or 'police.gov.bd' in link.lower()) else 'source_reported'
            })
        print(country,category,len(items))
        return items[:40]
    except Exception as e:
        print('Feed error',country,category,str(e)[:180])
        return []

with ThreadPoolExecutor(max_workers=8) as pool:
    batches=list(pool.map(fetch,feeds))
fresh=[x for batch in batches for x in batch]

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
        take=min(3,limit,len(groups['BD']))
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
    limit=50
)
print('Fresh image candidates selected fairly by country:',len(image_candidates))
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(enrich_article_image,image_candidates))
print('Fresh candidate images recovered:',sum(1 for x in image_candidates if x.get('image') and x.get('image') != GENERIC_IMAGE_URL))
print('Fresh Google News links resolved:',sum(1 for x in image_candidates if 'news.google.com/' not in str(x.get('link',''))))

patterns={
  'fire':r'\bfire\b|\bblaze\b|wildfire|আগুন|অগ্নিকাণ্ড',
  'abuse':r'rape|sexual assault|sexual violence|molest|ধর্ষণ|যৌন নির্যাতন|যৌন হয়রানি',
  'missing':r'missing child|child missing|missing (?:boy|girl|minor)|abducted child|নিখোঁজ শিশু|শিশু নিখোঁজ|নিখোঁজ কিশোরী|নিখোঁজ কিশোর|নিখোঁজ বালক|নিখোঁজ বালিকা',
  'accident':r'accident|crash|collision|derailment|shipwreck|দুর্ঘটনা|সংঘর্ষ|নৌকাডুবি',
  'casualty':r'death toll|fatalities|people killed|casualties|নিহত|প্রাণহানি|হতাহত',
  'reserve':r'foreign exchange reserves|forex reserves|foreign reserves|বৈদেশিক মুদ্রার রিজার্ভ|রিজার্ভ'
}
# Country labels must describe the reported incident, not the Google News
# edition used to discover it. Use only explicit location evidence; otherwise
# keep the story in WORLD rather than publishing a guessed country.
INCIDENT_LOCATION_ALIASES = {
    'BD': ('bangladesh','bangladeshi','dhaka','chattogram','chittagong','sylhet','rajshahi','khulna','barishal','rangpur','mymensingh',"cox's bazar"),
    'US': ('united states','u.s.','usa','american','new york city','new york','chicago','los angeles','san francisco','washington dc','washington, d.c.','florida','texas','ohio','california','naples','springfield','bethel township','auburn gresham','athens, georgia'),
    'GB': ('united kingdom','britain','british','england','scotland','wales','london','kent','maidstone','liverpool','bathgate','west lothian','dundee','glasgow'),
    'IN': ('india','indian','delhi','new delhi','mumbai','kolkata','chennai','bengaluru','bangalore','hyderabad'),
    'ID': ('indonesia','indonesian','jakarta','bali','surabaya'),
    'UA': ('ukraine','ukrainian','kyiv','khmelnytskyi','odesa','kharkiv','donetsk'),
    'EG': ('egypt','egyptian','cairo','alexandria'),
    'FR': ('france','french','paris','lyon','marseille'),
    'DE': ('germany','german','berlin','munich','hamburg'),
    'PL': ('poland','polish','krakow','kraków','warsaw'),
    'PS': ('gaza','west bank','palestine','palestinian'),
    'IL': ('israel','israeli','tel aviv','jerusalem'),
    'CA': ('canada','canadian','ontario','quebec','toronto','sudbury','vancouver'),
    'AU': ('australia','australian','sydney','melbourne','brisbane'),
    'NZ': ('new zealand','auckland','wellington'),
    'PK': ('pakistan','pakistani','islamabad','karachi','lahore'),
    'MY': ('malaysia','malaysian','kuala lumpur'),
    'SG': ('singapore','singaporean'),
    'ZA': ('south africa','south african','johannesburg','cape town'),
    'KE': ('kenya','kenyan','nairobi'),
    'NG': ('nigeria','nigerian','lagos','abuja'),
    'RU': ('russia','russian','moscow'),
    'TR': ('turkey','türkiye','turkish','ankara','istanbul'),
    'IR': ('iran','iranian','tehran'),
    'SA': ('saudi arabia','saudi','riyadh'),
    'AE': ('united arab emirates','uae','dubai','abu dhabi'),
    'JP': ('japan','japanese','tokyo','osaka'),
    'CN': ('china','chinese','beijing','shanghai'),
    'KR': ('south korea','south korean','seoul'),
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
}
def incident_country(item):
    story=' '+(str(item.get('title',''))+' '+str(item.get('summary',''))).lower()+' '
    # Specific places are checked before demonyms/country names so that,
    # for example, a city in Ukraine wins over a headline mentioning Russia.
    priority = ('BD','US','GB','IN','ID','UA','EG','FR','DE','PL','PS','IL','CA','AU','NZ','PK','MY','SG','ZA','KE','NG','RU','TR','IR','SA','AE','JP','CN','KR','TH','VN','BR','MX','AR','ES','IT','NL','BE','CH','SE','NO','DK','IE','GR','CZ','RO','ET','TZ','UG','ZW','AF')
    for code in priority:
        for alias in INCIDENT_LOCATION_ALIASES.get(code, ()):
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
    for key in ('abuse','missing','fire','accident','casualty','reserve'):
        if re.search(patterns[key],s,re.I): return key
    # Keep the source feed category only when the text gives no contrary signal.
    return item.get('category','') if item.get('category') in patterns else ''

try:
    with open('news.json',encoding='utf-8') as file:
        old=json.load(file)
        previous=old.get('news',[]) if isinstance(old,dict) else old
except Exception: previous=[]

# Backfill older stored stories too; otherwise the site keeps showing
# the old no-image placeholder even after the collector is improved.
previous_image_candidates=fair_image_candidates(
    (x for x in previous if not x.get('image') or x.get('image') == GENERIC_IMAGE_URL or 'news.google.com/' in str(x.get('link','')) or not str(x.get('summary','')).strip()),
    limit=1000
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
    if not link or not published or published<cutoff or published>now+timedelta(hours=2): continue
    category=classify(item)
    if not category: continue
    item['link']=link
    item['published']=published.isoformat()
    item['category']=category
    item['country']=incident_country(item)
    item.setdefault('summary',item.get('description',''))
    item.setdefault('verification_status','source_reported')
    old_item=by_link.get(link)
    if old_item is None:
        by_link[link]=item
    else:
        if not old_item.get('image') and item.get('image'):
            old_item['image']=item['image']
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
    image_url=str(item.get('image','')).strip()
    if not image_url.startswith('https://') or image_url==GENERIC_IMAGE_URL:
        return item,False,'invalid-url'
    verified_at=item.get('image_verified_at')
    if verified_at:
        try:
            verified_dt=datetime.fromisoformat(str(verified_at).replace('Z','+00:00'))
            if verified_dt.tzinfo is None:
                verified_dt=verified_dt.replace(tzinfo=now.tzinfo)
            if (now-verified_dt).total_seconds()<7*24*60*60:
                return item,True,'cached'
        except Exception:
            pass
    host=urllib.parse.urlsplit(image_url).netloc
    headers={
        'User-Agent':CHROME_UA,
        'Accept':'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Range':'bytes=0-2047',
        'Referer':'https://all-in-one-news.github.io/all-in-one-news/'
    }
    try:
        req=Request(image_url,headers=headers)
        with urlopen(req,timeout=8) as response:
            content_type=str(response.headers.get('Content-Type','')).split(';',1)[0].lower()
            sample=response.read(32)
        valid=content_type.startswith('image/') or sample.startswith((
            bytes.fromhex('ffd8ff'),bytes.fromhex('89504e470d0a1a0a'),b'GIF87a',b'GIF89a'
        )) or (sample[:4]==b'RIFF' and sample[8:12]==b'WEBP')
        if valid:
            item['image_verified_at']=now.isoformat()
        return item,valid,host
    except Exception as error:
        return item,False,host+':'+type(error).__name__

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
seo_cutoff=now-timedelta(days=30)
for item in news:
    published=parse_date(item.get('published',''))
    if not published or published<seo_cutoff:
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
<meta property="og:description" content="'''+summary[:300]+'''"><meta property="og:url" content="'''+url+'''">
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
