import json, re, os, time, urllib.request, urllib.parse, urllib.error, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

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
            for sub in node.iter():
                if local(sub.tag) in ('thumbnail','content','enclosure'):
                    candidate=(sub.attrib.get('url') or sub.attrib.get('src') or sub.attrib.get('href') or '').strip()
                    if candidate.startswith('https://') or candidate.startswith('http://'):
                        image=candidate; break
            if not image:
                image_match=re.search(r"<img[^>]+(?:src|data-src)=[\"'](https?://[^\"']+)",summary,re.I)
                if image_match: image=image_match.group(1)
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
GENERIC_IMAGE_URL='https://lh3.googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc=s0-w300'
def enrich_article_image(item):
    # Google News sometimes repeats one generic thumbnail for unrelated stories.
    if item.get('image') and item.get('image') != GENERIC_IMAGE_URL:
        return item
    item['image']=''
    if not str(item.get('link','')).startswith(('https://','http://')):
        return item
    try:
        req=urllib.request.Request(item['link'],headers={
            'User-Agent':'Mozilla/5.0 (compatible; AllInOneNews/1.0)',
            'Accept':'text/html,application/xhtml+xml'
        })
        with urllib.request.urlopen(req,timeout=8) as response:
            final_url=response.geturl()
            raw=response.read(900000).decode('utf-8','ignore')
        # Prefer publisher-selected social preview images.
        for tag in re.findall(r'<meta\b[^>]*>',raw,re.I):
            attrs={k.lower():html.unescape(v) for k,v in re.findall(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']',tag)}
            key=(attrs.get('property') or attrs.get('name') or attrs.get('itemprop') or '').lower()
            candidate=attrs.get('content','').strip()
            if key in ('og:image','og:image:secure_url','twitter:image','twitter:image:src','image') and candidate.startswith(('https://','http://','/')):
                item['image']=urljoin(final_url,candidate)
                break
        if final_url and not final_url.startswith('https://news.google.com/'):
            item['link']=final_url
    except Exception:
        pass
    return item

# Share image-recovery capacity fairly across countries instead of letting
# the newest few countries consume the entire global enrichment limit.
def fair_image_candidates(items, limit=1000):
    groups={}
    for item in sorted(items,key=lambda x:x.get('published',''),reverse=True):
        code=str(item.get('country') or 'WORLD').upper()
        groups.setdefault(code,[]).append(item)
    selected=[]
    country_codes=sorted(groups)
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

image_candidates=fair_image_candidates(
    (x for x in fresh if not x.get('image') or x.get('image') == GENERIC_IMAGE_URL),
    limit=1000
)
print('Fresh image candidates selected fairly by country:',len(image_candidates))
with ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(enrich_article_image,image_candidates))

patterns={
  'fire':r'\bfire\b|\bblaze\b|wildfire|আগুন|অগ্নিকাণ্ড',
  'abuse':r'rape|sexual assault|sexual violence|molest|ধর্ষণ|যৌন নির্যাতন|যৌন হয়রানি',
  'missing':r'missing child|child missing|missing (?:boy|girl|minor)|abducted child|নিখোঁজ শিশু|শিশু নিখোঁজ|নিখোঁজ কিশোরী|নিখোঁজ কিশোর|নিখোঁজ বালক|নিখোঁজ বালিকা',
  'accident':r'accident|crash|collision|derailment|shipwreck|দুর্ঘটনা|সংঘর্ষ|নৌকাডুবি',
  'casualty':r'death toll|fatalities|people killed|casualties|নিহত|প্রাণহানি|হতাহত',
  'reserve':r'foreign exchange reserves|forex reserves|foreign reserves|বৈদেশিক মুদ্রার রিজার্ভ|রিজার্ভ'
}
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
    (x for x in previous if not x.get('image') or x.get('image') == GENERIC_IMAGE_URL),
    limit=1000
)
print('Previous image candidates selected fairly by country:',len(previous_image_candidates))
with ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(enrich_article_image,previous_image_candidates))

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
    item['country']=str(item.get('country') or 'WORLD').upper()
    item.setdefault('summary',item.get('description',''))
    item.setdefault('verification_status','source_reported')
    old_item=by_link.get(link)
    if old_item is None or (not old_item.get('image') and item.get('image')):
        by_link[link]=item

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
]
print('Stories held back because no image was found:',len(incidents)-len(incidents_with_images))
news=sorted(incidents_with_images,key=lambda x:x['published'],reverse=True)[:12000]
# Never replace a healthy feed with an unexpectedly empty or drastically smaller run.
minimum_safe_count=max(10, int(len(previous)*0.20))
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
