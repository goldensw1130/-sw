# -*- coding: utf-8 -*-
"""숏폼 나침반 로컬 도우미. 공개 검색엔진 결과에서 색인된 TikTok 영상 링크만 추출합니다.
공식 TikTok API나 로그인 쿠키를 사용하지 않으며, 차단 우회/캡차 우회는 하지 않습니다.
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote_plus, urlparse as parse_url, parse_qs as parse_query, urljoin
from html.parser import HTMLParser
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from pathlib import Path
import json, re, time, threading, html, socket, datetime, os, hashlib, zipfile, shutil, tempfile, io, base64

ROOT = Path(__file__).resolve().parent
LAST_SEARCH = 0.0
SEARCH_LOCK = threading.Lock()
# Short-lived cache prevents repeated clicks from hammering public search providers.
SEARCH_CACHE = {}
SEARCH_CACHE_TTL = 180
SEARCH_CACHE_MAX = 100
MIN_INTERVAL = 2.5
MAX_QUERY = 180
APP_VERSION = '2.45'
# Replaced inside release ZIPs by Prepare_Release.py with the real public feed URL.
DEFAULT_UPDATE_MANIFEST_URL = "https://github.com/goldensw1130/-sw/releases/latest/download/update_manifest.json"
MAX_UPDATE_MANIFEST_BYTES = 262144
MAX_UPDATE_ARCHIVE_BYTES = 150 * 1024 * 1024
MAX_UPDATE_UNPACKED_BYTES = 120 * 1024 * 1024
MAX_AI_BODY_BYTES = 18 * 1024 * 1024
USER_DATA_ROOT = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_DATA_HOME') or (Path.home() / '.local' / 'share')) / 'ShortCompass'
UPDATE_SETTINGS_PATH = USER_DATA_ROOT / 'update_settings.json'
UPDATE_STATE_PATH = USER_DATA_ROOT / 'update_state.json'
AI_MODELS_PATH = USER_DATA_ROOT / 'ai_models.json'
UPDATE_STAGE_PATH = USER_DATA_ROOT / 'updates' / 'verified-update.zip'
UPDATE_DOWNLOAD_LOCK = threading.Lock()
SESSION_AI_KEYS = {'openai': '', 'gemini': '', 'anthropic': ''}
AI_LAST_REQUEST = 0.0
AI_REQUEST_LOCK = threading.Lock()
AI_PROVIDER_ENDPOINTS = {'openai': 'https://api.openai.com/v1/responses', 'gemini': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', 'anthropic': 'https://api.anthropic.com/v1/messages'}
AI_DEFAULT_MODELS = {'openai': 'gpt-6-astra', 'gemini': 'gemini-4-argon', 'anthropic': 'claude-opus-5'}
AI_MODEL_LIST_ENDPOINTS = {
    'openai': 'https://api.openai.com/v1/models?limit=200',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=100',
    'anthropic': 'https://api.anthropic.com/v1/models?limit=100',
}
AI_MODEL_CATALOGS = {}
AI_TASK_ROUTING_PRIORITY = {
    # These are starting heuristics, not claims of universal benchmark superiority.
    'plan': ['openai', 'gemini', 'anthropic'],
    'script': ['anthropic', 'openai', 'gemini'],
    'packaging': ['openai', 'anthropic', 'gemini'],
    'review': ['anthropic', 'openai', 'gemini'],
    'research': ['gemini', 'openai', 'anthropic'],
    'seo': ['openai', 'gemini', 'anthropic'],
}
UPDATE_ALLOWED_HOSTS = {'github.com', 'api.github.com', 'raw.githubusercontent.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com', 'github-releases.githubusercontent.com'}
AI_ALLOWED_HOSTS = {'openai':'api.openai.com','gemini':'generativelanguage.googleapis.com','anthropic':'api.anthropic.com'}

class _GitHubRedirectGuard(HTTPRedirectHandler):
    """Validate every redirect hop, not merely the final URL, for update feeds/packages."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target=urljoin(req.full_url,newurl)
        parsed=parse_url(target)
        if parsed.scheme!='https' or (parsed.hostname or '').lower() not in UPDATE_ALLOWED_HOSTS or parsed.username or parsed.password:
            raise HTTPError(req.full_url,code,'Blocked redirect outside trusted GitHub HTTPS hosts',headers,fp)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class _NoRedirectForSecretAPI(HTTPRedirectHandler):
    """Do not forward credentialed AI requests or provider keys to a redirect target."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url,code,'Credentialed AI API redirects are disabled for key safety',headers,fp)

def _open_github_url(req, timeout):
    return build_opener(_GitHubRedirectGuard()).open(req,timeout=timeout)

def _open_provider_url(req, timeout, provider):
    expected=AI_ALLOWED_HOSTS.get(str(provider or '').lower())
    parsed=parse_url(req.full_url)
    if parsed.scheme!='https' or (parsed.hostname or '').lower()!=expected:
        raise ValueError('AI 요청 주소가 해당 제공자의 공식 HTTPS 호스트와 일치하지 않습니다.')
    return build_opener(_NoRedirectForSecretAPI()).open(req,timeout=timeout)
UPDATE_ALLOWED_FILES = {'ShortsCompass.html','ShortCompassServer.py','Start_ShortCompass.bat','Start_Here_KO.txt','Changes_KO.txt','Test_KO.txt','Test_ShortCompass.py','Test_ABReliability.js','Test_OpportunityLearning.js','Test_YouTubeRanking.js','Test_UpdateAndAI.py','Test_UpdateUI.js','Test_FullDiagnosticsUI.js','Test_ReleaseTools.py','Test_GitHubBootstrap.py','Prepare_Release.py','RELEASE_PUBLISHING_GUIDE_KO.md','RELEASE_NOTES_CURRENT_KO.txt','release_workflow_template.yml','release_config.example.json','DEVELOPMENT_STANDARD_KO.md','ROADMAP_KO.md','AI_SETUP_KO.txt','update_manifest.example.json','Setup_GitHub_AutoRelease.ps1','Setup_GitHub_AutoRelease.bat','GITHUB_AUTORELEASE_SETUP_KO.md'}
MAX_POST_BYTES = 65536
DIAGNOSTIC_HOSTS = {
    'TikTok': 'www.tiktok.com',
    'Google 검색': 'www.google.com',
    'Bing 검색': 'www.bing.com',
    'DuckDuckGo 검색': 'html.duckduckgo.com',
    'TikTok Creative Center': 'ads.tiktok.com',
}

class SearchParser(HTMLParser):
    """Extract ordinary result anchors from DuckDuckGo/Bing HTML without executing scripts."""
    VOID_TAGS = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self, provider='duckduckgo'):
        super().__init__(); self.provider=provider; self.results=[]; self.current=None
        self.capture_title=False; self.in_b_algo=0; self.anchor_depth=0; self.tag_stack=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); classes=a.get('class','').split()
        is_result=(tag in ('li','div') and self.provider=='bing' and 'b_algo' in classes)
        if is_result: self.in_b_algo += 1
        if tag=='a':
            href=a.get('href','')
            use=(self.provider=='duckduckgo' and ('result__a' in classes or 'result-link' in classes))
            use=(use or self.provider=='bing' and self.in_b_algo>0 and bool(href) and not href.startswith('#'))
            if use and self.current is None:
                self.current={'title':'','url':href}; self.capture_title=True; self.anchor_depth=1
            elif self.current is not None:
                self.anchor_depth += 1
        if tag not in self.VOID_TAGS:
            self.tag_stack.append((tag, is_result))
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS: self.handle_endtag(tag)
    def handle_data(self, data):
        if self.capture_title and self.current is not None: self.current['title'] += data
    def handle_endtag(self, tag):
        if tag=='a' and self.current is not None:
            self.anchor_depth -= 1
            if self.anchor_depth<=0:
                self.current['title']=re.sub(r'\s+',' ',self.current['title']).strip()
                if self.current['title'] and self.current['url']: self.results.append(self.current)
                self.current=None; self.capture_title=False; self.anchor_depth=0
        # Pop through the matching opening tag so nested div/li endings do not
        # accidentally close a Bing result container too early.
        match=None
        for i in range(len(self.tag_stack)-1, -1, -1):
            if self.tag_stack[i][0]==tag:
                match=i; break
        if match is not None:
            removed=self.tag_stack[match:]
            self.tag_stack=self.tag_stack[:match]
            self.in_b_algo=max(0,self.in_b_algo-sum(1 for _, marked in removed if marked))

def unwrap_url(raw):
    raw=html.unescape(raw)
    try:
        u=parse_url(raw); host=(u.hostname or '').lower()
        if 'duckduckgo.com' in host:
            raw=parse_query(u.query).get('uddg',[raw])[0]
        elif host.endswith('bing.com'):
            params=parse_query(u.query)
            if params.get('url'): raw=params['url'][0]
            elif params.get('u'):
                value=params['u'][0]
                # Bing's /ck/a links encode destination as a base64-like u=a1... value.
                if value.startswith('a1'):
                    import base64
                    try: raw=base64.urlsafe_b64decode(value[2:]+'===').decode('utf-8','ignore')
                    except Exception: pass
    except Exception: pass
    return raw

def canonical_tiktok_url(url):
    """Canonical key for a TikTok video URL; remove tracking query/fragment and normalize host."""
    try:
        u=parse_url(html.unescape(str(url or '')).strip())
        host=(u.hostname or '').lower().split(':')[0]
        if not (host=='tiktok.com' or host.endswith('.tiktok.com')):
            return ''
        path=re.sub(r'/+', '/', u.path or '/').rstrip('/') or '/'
        # Short links are case-sensitive opaque path tokens; preserve path casing.
        return 'https://' + host + path
    except Exception:
        return ''

def same_tiktok_creator(url_a, url_b):
    try:
        a=parse_url(url_a).path.strip('/').split('/')
        b=parse_url(url_b).path.strip('/').split('/')
        return bool(a and b and a[0].startswith('@') and a[0].casefold()==b[0].casefold())
    except Exception:
        return False

def normalize_search_title(title):
    """Normalize titles for conservative duplicate detection without deleting meaningful words."""
    value=html.unescape(str(title or '')).casefold()
    value=re.sub(r'\s*[|–—-]\s*(?:tiktok|틱톡)(?:\s+.*)?$', '', value, flags=re.I)
    value=re.sub(r'https?://\S+', ' ', value)
    value=re.sub(r'[^\w가-힣]+', ' ', value, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', value).strip()

def is_tiktok_video(url):
    try:
        u=parse_url(url); host=(u.hostname or '').lower().split(':')[0]
        if u.scheme not in ('http','https') or not (host=='tiktok.com' or host.endswith('.tiktok.com')): return False
        return bool(re.search(r'/video/\d+',u.path) or host in ('vm.tiktok.com','vt.tiktok.com'))
    except Exception: return False

def _fetch_search_provider(provider, q):
    if provider=='duckduckgo':
        url='https://html.duckduckgo.com/html/?q='+quote_plus(q)
        host='html.duckduckgo.com'
        parser_name='duckduckgo'
    else:
        url='https://www.bing.com/search?q='+quote_plus(q)+'&count=30'
        host='www.bing.com'
        parser_name='bing'
    req=Request(url, headers={
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language':'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    })
    try:
        with urlopen(req, timeout=10) as resp:
            status=getattr(resp,'status',200)
            if status!=200: return {'provider':provider,'error':f'HTTP_{status}','message':f'{provider} 응답 HTTP {status}','results':[]}
            raw=resp.read(2_500_000).decode('utf-8','replace')
    except HTTPError as e:
        return {'provider':provider,'error':'BLOCKED' if e.code in (403,429,503) else f'HTTP_{e.code}', 'message':f'{provider} 응답 HTTP {e.code}','results':[]}
    except (URLError, TimeoutError, OSError) as e:
        return {'provider':provider,'error':'NETWORK','message':f'{provider} 연결 실패: {str(e)[:140]}','results':[]}
    parser=SearchParser(parser_name); parser.feed(raw)
    results=[]; seen_urls=set(); seen_titles=set(); duplicate_count=0
    for item in parser.results:
        link=unwrap_url(item.get('url',''))
        if not is_tiktok_video(link): continue
        canonical=canonical_tiktok_url(link)
        if not canonical: continue
        title=(item.get('title') or '제목 없음(검색엔진 색인)').strip()
        title_key=normalize_search_title(title)
        # URL is authoritative. Title-only dedupe is a fallback for weak/opaque short links.
        if canonical in seen_urls or (title_key and title_key in seen_titles and any(normalize_search_title(old.get('title'))==title_key and same_tiktok_creator(old.get('url',''),canonical) for old in results)):
            duplicate_count += 1
            continue
        seen_urls.add(canonical)
        if title_key: seen_titles.add(title_key)
        results.append({'title':title,'url':canonical,
                        'source':('DuckDuckGo' if provider=='duckduckgo' else 'Bing')+' 공개 웹 색인','metrics':None})
        if len(results)>=20: break
    return {'provider':provider,'error':None if results else 'NO_RESULTS','message':'','results':results,'duplicateCount':duplicate_count}

def search_recovery_advice(error):
    """Return a short, actionable recovery guide without bypassing provider restrictions."""
    guides = {
        'EMPTY_QUERY': ('검색어가 비어 있습니다.', ['주제나 핵심 단어를 입력하세요.', '분야별 검색을 실행했다면 검색어 생성 결과를 확인하세요.'], False),
        'QUERY_TOO_LONG': ('검색어가 너무 깁니다.', [f'검색어를 {MAX_QUERY}자 이내로 줄이세요.', '핵심 주제와 필요하면 한두 개의 구체어만 남기세요.'], False),
        'NETWORK': ('공개 검색엔진 연결에 실패했습니다.', ['외부 연결 진단에서 DNS와 HTTPS 상태를 확인하세요.', 'Start_ShortCompass.bat으로 앱을 실행했고 로컬 서버가 켜져 있는지 확인하세요.', '외부 검색 링크를 열어 브라우저에서는 검색 가능한지 별도로 확인하세요.'], True),
        'SEARCH_BLOCKED': ('검색엔진이 자동 검색 요청을 제한했습니다.', ['자동 재시도를 반복하지 마세요. 차단 또는 CAPTCHA를 우회하지 않습니다.', 'TikTok·Google·Bing 직접 검색 링크를 사용하거나 잠시 후 다시 확인하세요.', '조회수가 필요한 경우 승인된 공식 API 또는 직접 확인한 값만 사용하세요.'], False),
        'NO_RESULTS': ('공개 웹 색인에서 일치하는 영상 링크를 찾지 못했습니다.', ['검색어를 짧고 구체적으로 바꾸거나 해시태그를 제거해 보세요.', '검색엔진 색인에 없는 영상은 여기서 검색되지 않을 수 있습니다.', 'TikTok 직접 검색 및 일반 웹 검색 링크를 이용하세요.'], True),
        'LOCAL_SERVER': ('앱의 로컬 검색 서버에 연결되지 않았습니다.', ['Start_ShortCompass.bat으로 실행하고 콘솔 창이 열려 있는지 확인하세요.', '포트 8765가 다른 프로그램에서 사용 중인지 확인하세요.', '브라우저에서 직접 외부 검색을 열어 외부 서비스와 로컬 앱 문제를 구분하세요.'], True),
    }
    title, steps, retry = guides.get(str(error or 'NO_RESULTS'), guides['NO_RESULTS'])
    return {'code': str(error or 'NO_RESULTS'), 'title': title, 'steps': steps,
            'manualRetryUseful': retry, 'automaticBypass': False}


def search_public_index(query):
    """Try two public indexes in sequence; cache briefly and never fabricate results."""
    global LAST_SEARCH
    query=re.sub(r'\s+', ' ', str(query or '')).strip()
    if not query:
        return {'ok':False,'error':'EMPTY_QUERY','message':'검색어를 입력하세요.','results':[],'recovery':search_recovery_advice('EMPTY_QUERY')}
    cache_key=query.casefold()
    now=time.monotonic()
    cached=SEARCH_CACHE.get(cache_key)
    if cached and now-cached[0] < SEARCH_CACHE_TTL:
        result=json.loads(json.dumps(cached[1], ensure_ascii=False))
        result['cached']=True
        result['servedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['message']=(result.get('message','')+' (최근 검색 결과 캐시)').strip()
        return result
    # Search across both public indexes; strict TikTok video URL validation happens after parsing.
    q=('site:tiktok.com ' + query).strip()
    with SEARCH_LOCK:
        wait=MIN_INTERVAL-(time.monotonic()-LAST_SEARCH)
        if wait>0: time.sleep(wait)
        LAST_SEARCH=time.monotonic()
    diagnostics=[]; combined=[]; seen=set(); used=[]
    # Providers are fallbacks, not concurrent scraping. A provider block is respected.
    for provider in ('duckduckgo','bing'):
        provider_started=time.monotonic()
        result=_fetch_search_provider(provider,q)
        elapsed_ms=max(0,round((time.monotonic()-provider_started)*1000))
        diagnostics.append({'provider':provider,'status':result.get('error') or 'OK','message':result.get('message',''),'resultCount':len(result.get('results',[])),'duplicateCount':int(result.get('duplicateCount',0)),'elapsedMs':elapsed_ms})
        title_keys={normalize_search_title(x.get('title')) for x in combined}
        for item in result.get('results',[]):
            key=canonical_tiktok_url(item.get('url',''))
            title_key=normalize_search_title(item.get('title'))
            if key and key not in seen and not (title_key and title_key in title_keys and any(normalize_search_title(old.get('title'))==title_key and same_tiktok_creator(old.get('url',''),key) for old in combined)):
                seen.add(key); combined.append(item); used.append(item['source'])
                if title_key: title_keys.add(title_key)
        if combined: break
        # If a provider blocks the request, do not retry it; move to the independent public index.
    if combined:
        source=' + '.join(dict.fromkeys(used))
        collected_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        result={'ok':True,'error':None,'message':f'{len(combined)}개 영상 링크를 공개 웹 색인에서 찾았습니다. 실제 통계는 수집하지 않았습니다.',
                'results':combined,'source':source,'providers':diagnostics,'cached':False,'collectedAt':collected_at,'servedAt':collected_at,'sourceType':'public-web-index',
                'quality':{'validResults':len(combined),'duplicateCount':sum(int(x.get('duplicateCount',0)) for x in diagnostics),'providerCount':sum(1 for x in diagnostics if x.get('status')=='OK')}}
        _cache_search_result(cache_key, result)
        return result
    blocked=any(x['status']=='BLOCKED' for x in diagnostics)
    network=all(x['status']=='NETWORK' for x in diagnostics)
    if network:
        code='NETWORK'; msg='두 공개 검색엔진 모두 연결되지 않았습니다. DNS, 프록시, 방화벽 또는 인터넷 연결을 확인하세요.'
    elif blocked:
        code='SEARCH_BLOCKED'; msg='공개 검색엔진이 요청을 제한했습니다. 자동 우회는 하지 않았습니다. 잠시 후 재시도하거나 외부 검색 링크를 사용하세요.'
    else:
        code='NO_RESULTS'; msg='시도한 공개 검색 색인에서 일치하는 TikTok 영상 URL을 찾지 못했습니다. 색인 범위와 검색어에 따라 결과가 없을 수 있습니다.'
    collected_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    result={'ok':False if code in ('NETWORK','SEARCH_BLOCKED') else True,'error':code,'message':msg,'results':[],'providers':diagnostics,'cached':False,'collectedAt':collected_at,'servedAt':collected_at,'sourceType':'public-web-index','quality':{'validResults':0,'duplicateCount':sum(int(x.get('duplicateCount',0)) for x in diagnostics),'providerCount':sum(1 for x in diagnostics if x.get('status')=='OK')},'recovery':search_recovery_advice(code)}
    if code == 'NO_RESULTS':
        _cache_search_result(cache_key, result)
    return result

def _cache_search_result(key, result):
    now=time.monotonic()
    # Remove expired entries first; keep memory use bounded for a long-running desktop session.
    for old_key, (created, _) in list(SEARCH_CACHE.items()):
        if now-created >= SEARCH_CACHE_TTL:
            SEARCH_CACHE.pop(old_key, None)
    if len(SEARCH_CACHE) >= SEARCH_CACHE_MAX:
        oldest=min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k][0])
        SEARCH_CACHE.pop(oldest, None)
    SEARCH_CACHE[key]=(now, json.loads(json.dumps(result, ensure_ascii=False)))

def _numeric_metric(value):
    """Normalize official API metric values without treating missing values as zero."""
    if value is None or isinstance(value, bool):
        return -1
    try:
        number=float(str(value).replace(',', '').strip())
        return number if number >= 0 else -1
    except (TypeError, ValueError):
        return -1

def _research_api_error_message(code, message=''):
    code = str(code or '').lower()
    msg = str(message or '')[:300]
    if code in ('access_token_invalid', 'invalid_access_token', 'invalid_client', 'invalid_client_key', 'invalid_client_secret'):
        return '인증 실패: Client Key/Secret 또는 프로젝트 승인 상태를 확인하세요.'
    if code in ('scope_not_authorized', 'scope_not_authorized_for_client', 'unauthorized'):
        return '권한 부족: 승인된 Research API 프로젝트와 research.data.basic 권한이 필요합니다.'
    if code in ('rate_limit_exceeded', 'rate_limit_exceeded_global'):
        return 'TikTok API 요청 한도에 도달했습니다. 잠시 후 다시 시도하세요.'
    if msg:
        return msg
    return 'TikTok Research API 요청에 실패했습니다. 개발자 포털의 프로젝트 승인과 권한을 확인하세요.'

def run_tiktok_research_search(payload):
    """Call TikTok's official Research API only with user-supplied approved credentials.
    Credentials are not written to disk or included in logs/responses.
    """
    key = str(payload.get('client_key') or '').strip()
    secret = str(payload.get('client_secret') or '').strip()
    query = str(payload.get('query') or '').strip()
    region = str(payload.get('region') or 'KR').upper().strip()
    start_date = str(payload.get('start_date') or '').strip()
    end_date = str(payload.get('end_date') or '').strip()
    try:
        requested_max = int(payload.get('max_results') or 100)
    except (TypeError, ValueError):
        requested_max = 100
    if requested_max not in (100, 200, 300, 400, 500):
        return 400, {'ok':False,'error':'INVALID_MAX_RESULTS','message':'최대 결과 수는 100, 200, 300, 400, 500 중 하나를 선택하세요.'}
    if not key or not secret:
        return 400, {'ok':False,'error':'MISSING_CREDENTIALS','message':'승인된 Research API 프로젝트의 Client Key와 Client Secret을 입력하세요.'}
    if len(key)>512 or len(secret)>512:
        return 400, {'ok':False,'error':'INVALID_CREDENTIALS','message':'인증 정보 형식이 올바르지 않습니다.'}
    if not query:
        return 400, {'ok':False,'error':'EMPTY_QUERY','message':'검색어를 입력하세요.'}
    if len(query)>MAX_QUERY:
        return 400, {'ok':False,'error':'QUERY_TOO_LONG','message':f'검색어는 {MAX_QUERY}자 이내로 입력하세요.'}
    if not re.fullmatch(r'[A-Z]{2}', region):
        return 400, {'ok':False,'error':'INVALID_REGION','message':'지역 코드는 KR, US, JP 등 2자리 국가 코드여야 합니다.'}
    try:
        start = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        today = datetime.datetime.now(datetime.timezone.utc).date()
    except ValueError:
        return 400, {'ok':False,'error':'INVALID_DATE','message':'시작일과 종료일을 올바르게 입력하세요.'}
    if start > end:
        return 400, {'ok':False,'error':'INVALID_DATE_RANGE','message':'시작일은 종료일보다 늦을 수 없습니다.'}
    if (end-start).days > 30:
        return 400, {'ok':False,'error':'DATE_RANGE_TOO_LONG','message':'TikTok Research API는 한 번의 검색에서 시작일과 종료일 간격을 최대 30일로 제한합니다.'}
    if end > today:
        return 400, {'ok':False,'error':'FUTURE_DATE','message':'종료일은 오늘(UTC)보다 늦을 수 없습니다.'}
    # Obtain a client access token in memory only; no credential/token persistence.
    # TikTok token endpoint expects form-encoded values.
    from urllib.parse import urlencode
    token_req = Request('https://open.tiktokapis.com/v2/oauth/token/', data=urlencode({'client_key':key,'client_secret':secret,'grant_type':'client_credentials'}).encode('utf-8'), headers={'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json','User-Agent':'ShortsCompass/2.22'}, method='POST')
    try:
        with urlopen(token_req, timeout=15) as response:
            token_data=json.loads(response.read(500_000).decode('utf-8','replace'))
    except HTTPError as e:
        detail=''
        try: detail=e.read(2000).decode('utf-8','replace')
        except Exception: pass
        return 502, {'ok':False,'error':'TOKEN_HTTP_ERROR','message':f'TikTok 인증 서버 응답 HTTP {e.code}. Client Key/Secret 및 프로젝트 승인을 확인하세요.'}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        return 502, {'ok':False,'error':'TOKEN_NETWORK_ERROR','message':'TikTok 인증 서버에 연결하지 못했습니다. 인터넷/방화벽을 확인하세요. 상세: '+str(e)[:160]}
    token = token_data.get('access_token')
    if not token:
        error=token_data.get('error') or token_data.get('error_description') or token_data.get('message')
        return 502, {'ok':False,'error':'TOKEN_FAILED','message':_research_api_error_message(error, token_data.get('error_description') or token_data.get('message') or error)}
    fields='id,video_description,create_time,region_code,share_count,view_count,like_count,comment_count,username,hashtag_names'
    api_url='https://open.tiktokapis.com/v2/research/video/query/?fields='+quote_plus(fields)
    cursor=0; results=[]; seen_ids=set(); has_more=False; pages_fetched=0
    while len(results)<requested_max and pages_fetched < requested_max//100:
        body={'query':{'and':[{'operation':'EQ','field_name':'keyword','field_values':[query]},{'operation':'IN','field_name':'region_code','field_values':[region]}]},'start_date':start.strftime('%Y%m%d'),'end_date':end.strftime('%Y%m%d'),'max_count':100,'cursor':cursor,'is_random':False}
        req=Request(api_url,data=json.dumps(body).encode('utf-8'),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json','User-Agent':'ShortsCompass/2.22'},method='POST')
        try:
            with urlopen(req, timeout=20) as response:
                data=json.loads(response.read(2_000_000).decode('utf-8','replace'))
        except HTTPError as e:
            try: errdata=json.loads(e.read(500_000).decode('utf-8','replace'))
            except Exception: errdata={}
            err=errdata.get('error') or {}
            return 502, {'ok':False,'error':'RESEARCH_API_HTTP_ERROR','message':f'TikTok Research API HTTP {e.code}: '+_research_api_error_message(err.get('code'),err.get('message'))}
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            return 502, {'ok':False,'error':'RESEARCH_API_NETWORK_ERROR','message':'TikTok Research API 연결/응답 오류: '+str(e)[:180]}
        err=data.get('error') or {}
        if err and str(err.get('code','ok')).lower() not in ('ok','0',''):
            return 502, {'ok':False,'error':'RESEARCH_API_ERROR','message':_research_api_error_message(err.get('code'),err.get('message'))}
        page_data=data.get('data') or {}; videos=page_data.get('videos') or []
        pages_fetched += 1; has_more=bool(page_data.get('has_more'))
        for v in videos:
            vid=str(v.get('id') or '').strip()
            if vid and vid not in seen_ids:
                seen_ids.add(vid); results.append(v)
        if not has_more or len(results)>=requested_max: break
        next_cursor=page_data.get('cursor')
        if next_cursor is None or str(next_cursor)==str(cursor): break
        cursor=next_cursor
        # A short pause between pages helps avoid bursting the provider.
        time.sleep(0.25)
    videos=results[:requested_max]
    results=[]
    for v in videos:
        vid=str(v.get('id') or '').strip()
        username=str(v.get('username') or '').strip().lstrip('@')
        if not vid.isdigit(): continue
        url=f'https://www.tiktok.com/@{username}/video/{vid}' if username and re.fullmatch(r'[A-Za-z0-9._]{1,24}',username) else f'https://www.tiktok.com/video/{vid}'
        try: created=time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(int(v.get('create_time') or 0)))
        except Exception: created=''
        results.append({'id':vid,'title':str(v.get('video_description') or '').strip() or '(제목/설명 없음)','url':url,'username':username,'region':v.get('region_code') or region,'created':created,'views':v.get('view_count'),'likes':v.get('like_count'),'comments':v.get('comment_count'),'shares':v.get('share_count'),'hashtags':v.get('hashtag_names') or [],'source':'TikTok Research API'})
    results.sort(key=lambda x: _numeric_metric(x.get('views')), reverse=True)
    collected_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    return 200, {'ok':True,'source':'TikTok Research API','sourceType':'official-api','collectedAt':collected_at,'query':query,'region':region,'startDate':start_date,'endDate':end_date,'count':len(results),'results':results,'hasMore':bool(has_more and len(results)>=requested_max),'pagesFetched':pages_fetched,'requestedMax':requested_max,'scope':{'region':region,'startDateUTC':start_date,'endDateUTC':end_date,'requestedMax':requested_max,'pagesFetched':pages_fetched,'hasMore':bool(has_more and len(results)>=requested_max)},'note':f'공식 Research API에서 {pages_fetched}페이지를 조회해 조회수 내림차순으로 정렬했습니다. 수집 시각(UTC): {collected_at}. 최대 결과 수 요청: {requested_max}. 이 API는 승인된 연구 목적의 프로젝트에만 제공되며, 결과는 공개 영상 표본/기간/지역 조건에 한정됩니다. 인증 정보는 저장하지 않았습니다.'}

def run_search_engine_diagnostics():
    """Perform a small real search request to distinguish HTTPS reachability from search availability."""
    global LAST_SEARCH
    rows=[]
    probe_query='site:tiktok.com/video'
    for provider in ('duckduckgo','bing'):
        with SEARCH_LOCK:
            wait=MIN_INTERVAL-(time.monotonic()-LAST_SEARCH)
            if wait>0: time.sleep(wait)
            LAST_SEARCH=time.monotonic()
        provider_started=time.monotonic()
        result=_fetch_search_provider(provider, probe_query)
        elapsed_ms=max(0,round((time.monotonic()-provider_started)*1000))
        error=result.get('error')
        rows.append({
            'provider':provider,
            'status':'OK' if result.get('results') else (error or 'UNKNOWN'),
            'resultCount':len(result.get('results',[])),
            'elapsedMs':elapsed_ms,
            'message':result.get('message') or ('유효한 TikTok 영상 링크 확인' if result.get('results') else '검색 요청은 처리됐지만 유효한 TikTok 영상 링크를 찾지 못함')
        })
    reachable=sum(1 for r in rows if r['status'] in ('OK','NO_RESULTS'))
    return {'ok':True,'checkedAt':time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary':f'검색 요청 결과: {reachable}/{len(rows)}개 검색엔진에서 연결 또는 검색 응답을 확인했습니다.',
            'results':rows,
            'note':'이 검사는 짧은 실제 검색 요청을 보냅니다. 유효한 영상 링크가 없어도 검색엔진 연결 자체는 성공했을 수 있습니다. 차단·로그인·CAPTCHA를 우회하지 않습니다.'}

def run_network_diagnostics():
    """Check DNS and HTTPS reachability from the user's Windows PC; do not bypass blocks."""
    rows=[]
    for label, host in DIAGNOSTIC_HOSTS.items():
        row={'name':label,'host':host,'dns':'unknown','https':'not_tested','status':None,'detail':''}
        try:
            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            row['dns']='ok'
        except socket.gaierror as e:
            row['dns']='failed'; row['detail']='DNS 조회 실패: '+str(e)[:120]
            rows.append(row); continue
        except OSError as e:
            row['dns']='failed'; row['detail']='주소 조회 오류: '+str(e)[:120]
            rows.append(row); continue
        # HEAD may be rejected by some sites, so use a tiny GET and read no body.
        try:
            req=Request('https://'+host+'/', headers={'User-Agent':'Mozilla/5.0 (compatible; ShortsCompass-Diagnostics/2.19)','Range':'bytes=0-0'})
            with urlopen(req, timeout=5) as resp:
                row['https']='ok'; row['status']=int(resp.status); row['detail']='HTTPS 연결 가능'
        except HTTPError as e:
            # An HTTP response, including 403/429, proves DNS and TLS connectivity.
            row['https']='ok' if e.code in (401,403,404,405,429) else 'http_error'
            row['status']=int(e.code); row['detail']=f'서버 응답 HTTP {e.code}; 네트워크는 연결되었으나 서비스가 요청을 제한했을 수 있음'
        except (URLError, TimeoutError, OSError) as e:
            row['https']='failed'; row['detail']='HTTPS 연결 실패: '+str(e)[:120]
        rows.append(row)
    ok=sum(1 for r in rows if r['dns']=='ok' and r['https']=='ok')
    return {'ok':True,'checkedAt':time.strftime('%Y-%m-%d %H:%M:%S'),'summary':f'{ok}/{len(rows)}개 사이트에서 DNS 및 HTTPS 응답을 확인했습니다.','results':rows,
            'note':'이 검사는 이 PC의 DNS/HTTPS 연결만 확인합니다. 검색 결과 제공 여부, 로그인 요구, CAPTCHA 또는 서비스의 자동 요청 제한을 해제하지 않습니다.'}


def run_full_diagnostics():
    """Build a shareable local health report. Never return API keys or full private paths."""
    checks=[]
    def add(code, title, status, message, detail=None):
        row={'code':code,'title':title,'status':status,'message':message}
        if detail is not None: row['detail']=detail
        checks.append(row)

    # Environment and core-file consistency.
    py_ok = tuple(__import__('sys').version_info[:2]) >= (3,8)
    add('python-version','Python 버전','PASS' if py_ok else 'WARN',
        'Python '+__import__('platform').python_version() + (' 사용 가능' if py_ok else '은 지원 최소 버전(3.8)보다 낮습니다.'))
    required={'ShortCompassServer.py','ShortsCompass.html','Start_ShortCompass.bat'}
    missing=sorted(n for n in required if not (ROOT/n).is_file())
    add('core-files','핵심 파일','PASS' if not missing else 'FAIL',
        '필수 파일을 확인했습니다.' if not missing else '필수 파일이 없습니다: '+', '.join(missing))
    try:
        server_text=(ROOT/'ShortCompassServer.py').read_text(encoding='utf-8')
        html_text=(ROOT/'ShortsCompass.html').read_text(encoding='utf-8')
        title_match=re.search(r'<title>[^<]*?v([0-9]+(?:\.[0-9]+){1,3})',html_text,re.I)
        footer_match=re.search(r'class=["\']footer["\'][^>]*>[^<]*?v([0-9]+(?:\.[0-9]+){1,3})',html_text,re.I)
        backup_match=re.search(r"backupMeta:\{app:'ShortCompass',version:'([0-9]+(?:\.[0-9]+){1,3})'",html_text)
        server_match=re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]",server_text,re.M)
        versions={'serverSource':server_match.group(1) if server_match else None,'runtime':APP_VERSION,
                  'htmlTitle':title_match.group(1) if title_match else None,
                  'htmlFooter':footer_match.group(1) if footer_match else None,'backup':backup_match.group(1) if backup_match else None}
        aligned=all(versions[k]==APP_VERSION for k in ('serverSource','runtime','htmlTitle','htmlFooter','backup'))
        add('version-alignment','앱 버전 일치','PASS' if aligned else 'FAIL',
            '서버·화면·백업 버전이 일치합니다.' if aligned else '서버·화면 제목·화면 하단·백업 메타데이터 버전을 맞춰야 합니다.',versions)
    except (OSError,UnicodeError) as e:
        add('version-alignment','앱 버전 일치','FAIL','버전 정보를 읽을 수 없습니다: '+str(e)[:160])

    # Local writable paths are checked using a disposable file and no actual user data is read.
    data_writable=False
    try:
        USER_DATA_ROOT.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.shortcompass-diagnostic-',dir=str(USER_DATA_ROOT))
        os.close(fd); os.unlink(tmp); data_writable=True
    except OSError:
        data_writable=False
    add('user-data-write','사용자 데이터 저장 공간','PASS' if data_writable else 'FAIL',
        '설정·백업용 데이터 폴더에 쓸 수 있습니다.' if data_writable else '사용자 데이터 폴더에 쓸 수 없습니다. 폴더 권한과 디스크 공간을 확인하세요.')
    app_writable=os.access(str(ROOT),os.W_OK)
    add('app-folder-write','프로그램 폴더 쓰기 권한','PASS' if app_writable else 'WARN',
        '프로그램 폴더에 쓸 수 있습니다.' if app_writable else '프로그램 폴더에 쓰기 권한이 없습니다. 업데이트 적용에는 관리자/폴더 권한 조정이 필요할 수 있습니다.')

    # Update state: hide the full feed URL and validate any staged package before reporting it as ready.
    cfg=_read_update_settings(); state=_load_json_file(UPDATE_STATE_PATH,{})
    manifest_host=(parse_url(cfg['manifestUrl']).hostname if cfg.get('manifestUrl') else None)
    add('update-feed','업데이트 피드','PASS' if cfg.get('manifestUrl') else 'WARN',
        ('신뢰 목록에 포함된 HTTPS GitHub 피드가 설정되어 있습니다.' if cfg.get('manifestUrl') else '업데이트 피드가 아직 설정되지 않았습니다. 공개 릴리스와 manifest를 배포한 뒤 설정해야 자동 확인이 작동합니다.'),
        {'configured':bool(cfg.get('manifestUrl')),'host':manifest_host,'autoCheck':cfg['autoCheck'],'autoDownload':cfg['autoDownload'],'intervalHours':cfg['intervalHours']})
    staged_status='INFO'; staged_msg='검증 대기 중인 업데이트가 없습니다.'
    if state.get('stagedVersion') or UPDATE_STAGE_PATH.exists():
        try:
            if not UPDATE_STAGE_PATH.is_file(): raise ValueError('다운로드한 ZIP 파일이 없습니다.')
            expected=str(state.get('stagedSha256') or '')
            actual=hashlib.sha256(UPDATE_STAGE_PATH.read_bytes()).hexdigest()
            if not expected or actual!=expected: raise ValueError('저장된 SHA-256과 ZIP 파일이 일치하지 않습니다.')
            _validate_update_zip_bytes(UPDATE_STAGE_PATH.read_bytes(),expected,state.get('stagedVersion'))
            staged_status='PASS'; staged_msg='대기 중인 업데이트 파일의 해시·ZIP 구조·버전 검사를 통과했습니다.'
        except Exception as e:
            staged_status='FAIL'; staged_msg='대기 중인 업데이트를 다시 확인해야 합니다: '+str(e)[:220]
    add('staged-update','대기 업데이트 무결성',staged_status,staged_msg,
        {'staged':bool(state.get('stagedVersion')),'stagedVersion':state.get('stagedVersion')})

    # Only non-secret provider status is included. Never include env values, tokens, or absolute paths.
    try:
        ai=ai_status_view()
        providers=[]
        for item in ai.get('providers',[]):
            providers.append({'id':item.get('id'),'label':item.get('label'),'configured':bool(item.get('configured')),
                'keySource':item.get('keySource'),'selectedModel':item.get('selectedModel'),
                'selectedModelListed':item.get('selectedModelListed'),'catalogCount':int(item.get('catalogCount') or 0),
                'catalogRetrievedAt':item.get('catalogRetrievedAt')})
        configured=sum(1 for item in providers if item['configured'])
        add('ai-providers','AI 제공자 연결','PASS' if configured else 'WARN',
            f'{configured}/{len(providers)}개 제공자가 연결되어 있습니다. 모델 권한과 요금 여부는 실제 생성 테스트가 필요합니다.',providers)
    except Exception as e:
        add('ai-providers','AI 제공자 연결','WARN','AI 연결 상태를 읽을 수 없습니다: '+str(e)[:160])

    release_files=['Prepare_Release.py','release_workflow_template.yml','RELEASE_PUBLISHING_GUIDE_KO.md','Test_ReleaseTools.py']
    absent=[name for name in release_files if not (ROOT/name).is_file()]
    add('release-automation','릴리스 자동화 도구','PASS' if not absent else 'WARN',
        '릴리스 준비 도구와 GitHub Actions 템플릿이 있습니다.' if not absent else '릴리스 자동화 파일이 일부 없습니다: '+', '.join(absent))
    add('policy-precheck','정책 사전 점검','INFO','정규식 기반 사전 점검이 활성화되어 있습니다. 공식 플랫폼 심사·저작권 판단·게시 승인 보증은 아닙니다.')

    counts={status:sum(1 for x in checks if x['status']==status) for status in ('PASS','WARN','FAIL','INFO')}
    critical=counts['FAIL']
    return {'ok':critical==0,'appVersion':APP_VERSION,'generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'runtime':{'pythonVersion':__import__('platform').python_version(),'platform':__import__('platform').system()},
            'summary':{'pass':counts['PASS'],'warning':counts['WARN'],'fail':counts['FAIL'],'info':counts['INFO']},
            'checks':checks,'privacyNote':'이 리포트에는 API 키, 인증 토큰, 전체 사용자 데이터 경로, 프롬프트나 백업 내용이 포함되지 않습니다. 공유 전 본문을 직접 확인하세요.'}


# -------- Safe staged updater --------
def _load_json_file(path, default):
    try:
        obj=json.loads(Path(path).read_text(encoding='utf-8'))
        return obj if isinstance(obj,dict) else dict(default)
    except (OSError, ValueError, TypeError): return dict(default)

def _write_json_file(path, payload):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp,path)

def _version_tuple(value):
    value=str(value or '').strip().lstrip('vV')
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', value): raise ValueError('버전은 2.37 또는 2.37.1처럼 숫자와 점으로 입력해야 합니다.')
    parts=tuple(int(x) for x in value.split('.'))
    return parts + (0,) * (4-len(parts))

def _https_github_url(url):
    try:
        parsed=parse_url(str(url or '').strip()); host=(parsed.hostname or '').lower()
        return parsed.scheme=='https' and host in UPDATE_ALLOWED_HOSTS and not parsed.username and not parsed.password
    except Exception: return False

def _read_update_settings():
    data=_load_json_file(UPDATE_SETTINGS_PATH, {'manifestUrl':DEFAULT_UPDATE_MANIFEST_URL,'autoCheck':True,'autoDownload':False,'intervalHours':24})
    # Migrate older empty-feed settings to the signed-off public feed embedded at release build time.
    # Users can disable update checks explicitly by setting autoCheck to false.
    if not str(data.get('manifestUrl') or '').strip() and bool(data.get('autoCheck',True)) and DEFAULT_UPDATE_MANIFEST_URL:
        data['manifestUrl']=DEFAULT_UPDATE_MANIFEST_URL
    url=str(data.get('manifestUrl') or '').strip()
    try: interval=max(1,min(168,int(data.get('intervalHours',24))))
    except (TypeError,ValueError): interval=24
    return {'manifestUrl':url if _https_github_url(url) else '', 'autoCheck':bool(data.get('autoCheck',True)), 'autoDownload':bool(data.get('autoDownload',False)), 'intervalHours':interval}

def update_settings_view():
    cfg=_read_update_settings(); state=_load_json_file(UPDATE_STATE_PATH,{})
    staged=bool(UPDATE_STAGE_PATH.exists() and state.get('stagedVersion') and state.get('stagedSha256'))
    try: update_available=bool(state.get('availableVersion') and _version_tuple(state.get('availableVersion'))>_version_tuple(APP_VERSION))
    except ValueError: update_available=False
    return {'ok':True,'currentVersion':APP_VERSION,'manifestUrl':cfg['manifestUrl'],'autoCheck':cfg['autoCheck'],'autoDownload':cfg['autoDownload'],'intervalHours':cfg['intervalHours'],'lastCheckedAt':state.get('lastCheckedAt'),'lastCheckStatus':state.get('lastCheckStatus'),'availableVersion':state.get('availableVersion'),'updateAvailable':update_available,'releaseNotes':state.get('releaseNotes',''),'staged':staged,'stagedVersion':state.get('stagedVersion'),'note':'자동 확인은 설정한 간격에 따라 실행되고, 자동 다운로드는 선택한 경우 검증된 ZIP을 준비합니다. 최종 적용은 사용자가 승인해야 합니다.'}

def save_update_settings(payload):
    if not isinstance(payload,dict): return 400, {'ok':False,'error':'INVALID_JSON','message':'설정 형식이 올바르지 않습니다.'}
    url=str(payload.get('manifestUrl') or '').strip()
    if url and (len(url)>2000 or not _https_github_url(url)):
        return 400, {'ok':False,'error':'INVALID_MANIFEST_URL','message':'업데이트 피드는 허용된 HTTPS GitHub 주소만 사용할 수 있습니다.'}
    try: interval=max(1,min(168,int(payload.get('intervalHours',24) or 24)))
    except (TypeError,ValueError): return 400, {'ok':False,'error':'INVALID_INTERVAL','message':'확인 간격은 1~168시간이어야 합니다.'}
    cfg={'manifestUrl':url,'autoCheck':bool(payload.get('autoCheck',True)),'autoDownload':bool(payload.get('autoDownload',False)),'intervalHours':interval}
    try: _write_json_file(UPDATE_SETTINGS_PATH,cfg)
    except OSError as e: return 500, {'ok':False,'error':'SAVE_FAILED','message':'업데이트 설정을 저장하지 못했습니다: '+str(e)[:160]}
    return 200, {'ok':True,'settings':update_settings_view(),'message':'업데이트 설정을 저장했습니다.'}

def _fetch_https_json(url, max_bytes=MAX_UPDATE_MANIFEST_BYTES):
    if not _https_github_url(url): raise ValueError('허용된 HTTPS GitHub 피드 주소가 아닙니다.')
    req=Request(url,headers={'User-Agent':'ShortCompass-Updater/'+APP_VERSION,'Accept':'application/json'})
    with _open_github_url(req,timeout=12) as resp:
        if not _https_github_url(resp.geturl()): raise ValueError('허용되지 않은 주소로 리디렉션되어 중단했습니다.')
        raw=resp.read(max_bytes+1)
        if len(raw)>max_bytes: raise ValueError('응답이 허용 크기를 초과했습니다.')
        return json.loads(raw.decode('utf-8'))

def check_for_update(force=False):
    cfg=_read_update_settings()
    if not cfg['manifestUrl']:
        return {'ok':True,'configured':False,'currentVersion':APP_VERSION,'updateAvailable':False,'message':'업데이트 피드 주소가 설정되지 않았습니다. 제작자가 공개 릴리스와 manifest를 게시해야 원격 자동 확인을 사용할 수 있습니다.','settings':update_settings_view()}
    old=_load_json_file(UPDATE_STATE_PATH,{})
    now=datetime.datetime.now(datetime.timezone.utc)
    if not force and old.get('lastCheckedAt') and old.get('lastCheckStatus') in ('UPDATE_AVAILABLE','UP_TO_DATE'):
        try:
            elapsed=(now-datetime.datetime.fromisoformat(old['lastCheckedAt'].replace('Z','+00:00'))).total_seconds()/3600
            if elapsed < cfg['intervalHours']:
                v=old.get('availableVersion'); newer=bool(v and _version_tuple(v)>_version_tuple(APP_VERSION))
                return {'ok':True,'configured':True,'cached':True,'currentVersion':APP_VERSION,'availableVersion':v,'updateAvailable':newer,'message':'최근 확인 결과를 사용했습니다.','releaseNotes':old.get('releaseNotes',''),'settings':update_settings_view()}
        except Exception: pass
    try:
        manifest=_fetch_https_json(cfg['manifestUrl'])
        if not isinstance(manifest,dict) or int(manifest.get('schemaVersion',0))!=1: raise ValueError('지원하지 않는 manifest 형식입니다.')
        remote=str(manifest.get('version') or '').strip().lstrip('vV'); rv=_version_tuple(remote); cv=_version_tuple(APP_VERSION)
        if not _https_github_url(manifest.get('downloadUrl')): raise ValueError('패키지 URL은 허용된 HTTPS GitHub 주소여야 합니다.')
        digest=str(manifest.get('sha256') or '').lower()
        if not re.fullmatch(r'[0-9a-f]{64}',digest): raise ValueError('manifest의 SHA-256 값이 올바르지 않습니다.')
        if _version_tuple(manifest.get('minimumVersion') or '0.0')>cv: raise ValueError('이 업데이트는 더 최신의 설치 버전에서만 사용할 수 있습니다.')
        available=rv>cv; checked=now.isoformat()
        st={'lastCheckedAt':checked,'lastCheckStatus':'UPDATE_AVAILABLE' if available else 'UP_TO_DATE','availableVersion':remote if available else None,'releaseNotes':str(manifest.get('releaseNotes') or manifest.get('notes') or '')[:5000],'manifest':manifest if available else None,'stagedVersion':old.get('stagedVersion'),'stagedSha256':old.get('stagedSha256'),'stagedFiles':old.get('stagedFiles',[]),'stagedAt':old.get('stagedAt')}
        _write_json_file(UPDATE_STATE_PATH,st)
        return {'ok':True,'configured':True,'cached':False,'currentVersion':APP_VERSION,'availableVersion':remote,'updateAvailable':available,'manifest':{k:v for k,v in manifest.items() if k not in ('privateKey','signature')},'releaseNotes':st['releaseNotes'],'message':'새 버전을 확인했습니다.' if available else '현재 버전이 최신입니다.','settings':update_settings_view(),'securityNote':'HTTPS와 SHA-256은 전송/파일 무결성 확인용이며 디지털 서명 검증을 대체하지 않습니다. 신뢰하는 배포자만 사용하세요.'}
    except Exception as e:
        old.update({'lastCheckedAt':now.isoformat(),'lastCheckStatus':'CHECK_FAILED','lastError':str(e)[:500]})
        try: _write_json_file(UPDATE_STATE_PATH,old)
        except OSError: pass
        return {'ok':False,'configured':True,'currentVersion':APP_VERSION,'updateAvailable':False,'error':'UPDATE_CHECK_FAILED','message':'업데이트 확인 실패: '+str(e)[:300],'settings':update_settings_view()}

def _validate_update_zip_bytes(blob, expected_sha256, expected_version=None):
    digest=hashlib.sha256(blob).hexdigest()
    if digest.lower()!=str(expected_sha256).lower(): raise ValueError('SHA-256 검증에 실패했습니다. 패키지는 적용하지 않았습니다.')
    if not zipfile.is_zipfile(io.BytesIO(blob)): raise ValueError('정상 ZIP 패키지가 아닙니다.')
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        infos=[i for i in zf.infolist() if not i.is_dir()]
        if len(infos)<3 or len(infos)>len(UPDATE_ALLOWED_FILES): raise ValueError('패키지 파일 개수가 허용 범위를 벗어났습니다.')
        names=[]; unpacked=0
        for info in infos:
            name=info.filename
            if '/' in name or '\\' in name or name in ('.','..') or name not in UPDATE_ALLOWED_FILES: raise ValueError('허용하지 않는 패키지 경로/파일입니다: '+name[:120])
            if name in names: raise ValueError('중복 파일명이 포함되어 있습니다.')
            names.append(name); unpacked+=info.file_size
            if info.file_size>MAX_UPDATE_UNPACKED_BYTES or unpacked>MAX_UPDATE_UNPACKED_BYTES: raise ValueError('압축 해제 크기가 제한을 초과합니다.')
            if info.file_size and info.compress_size and info.file_size/info.compress_size>250: raise ValueError('비정상적인 압축 비율로 중단했습니다.')
        if not {'ShortsCompass.html','ShortCompassServer.py','Start_ShortCompass.bat'}.issubset(set(names)): raise ValueError('필수 프로그램 파일이 없습니다.')
        server_source=zf.read('ShortCompassServer.py').decode('utf-8')
        match=re.search(r"APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]",server_source)
        if not match: raise ValueError('업데이트 안에서 프로그램 버전을 확인할 수 없습니다.')
        package_version=match.group(1)
        _version_tuple(package_version)
        if expected_version and _version_tuple(package_version)!=_version_tuple(expected_version):
            raise ValueError('manifest 버전과 패키지 내부 서버 버전이 일치하지 않습니다.')
        html_source=zf.read('ShortsCompass.html').decode('utf-8')
        if not re.search(r'숏폼 나침반[^<]{0,80}v?'+re.escape(package_version), html_source):
            raise ValueError('HTML 화면의 버전 표기가 패키지 내부 버전과 일치하지 않습니다.')
        if zf.testzip() is not None: raise ValueError('ZIP 내부 CRC 검사에 실패했습니다.')
        return digest,names

def _download_verified_update_locked():
    state=_load_json_file(UPDATE_STATE_PATH,{}) ; manifest=state.get('manifest')
    if not isinstance(manifest,dict) or not state.get('availableVersion'): return 400, {'ok':False,'error':'NO_VERIFIED_MANIFEST','message':'먼저 업데이트 확인으로 새 버전을 확인하세요.'}
    if not _https_github_url(manifest.get('downloadUrl')): return 400, {'ok':False,'error':'INVALID_DOWNLOAD_URL','message':'허용되지 않는 다운로드 주소입니다.'}
    try:
        req=Request(manifest['downloadUrl'],headers={'User-Agent':'ShortCompass-Updater/'+APP_VERSION,'Accept':'application/zip,application/octet-stream'})
        with _open_github_url(req,timeout=45) as resp:
            if not _https_github_url(resp.geturl()): raise ValueError('허용되지 않은 다운로드 호스트로 이동했습니다.')
            declared=resp.headers.get('Content-Length')
            if declared and int(declared)>MAX_UPDATE_ARCHIVE_BYTES: raise ValueError('패키지가 150MB를 초과합니다.')
            blob=resp.read(MAX_UPDATE_ARCHIVE_BYTES+1)
        if len(blob)>MAX_UPDATE_ARCHIVE_BYTES: raise ValueError('패키지가 150MB를 초과합니다.')
        digest,names=_validate_update_zip_bytes(blob,manifest['sha256'],manifest.get('version'))
        UPDATE_STAGE_PATH.parent.mkdir(parents=True,exist_ok=True); tmp=UPDATE_STAGE_PATH.with_suffix('.tmp'); tmp.write_bytes(blob); os.replace(tmp,UPDATE_STAGE_PATH)
        state.update({'stagedVersion':str(manifest['version']).lstrip('vV'),'stagedSha256':digest,'stagedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stagedFiles':names})
        _write_json_file(UPDATE_STATE_PATH,state)
        return 200, {'ok':True,'staged':True,'stagedVersion':state['stagedVersion'],'sha256':digest,'files':names,'message':'SHA-256와 ZIP 구조 검증 완료. 실제 적용은 사용자가 승인한 뒤 진행됩니다.'}
    except Exception as e: return 400, {'ok':False,'error':'DOWNLOAD_OR_VERIFY_FAILED','message':'다운로드/검증 실패: '+str(e)[:300]}

def download_verified_update():
    if not UPDATE_DOWNLOAD_LOCK.acquire(blocking=False):
        return 409, {'ok':False,'error':'DOWNLOAD_IN_PROGRESS','message':'다른 다운로드/검증 작업이 진행 중입니다.'}
    try: return _download_verified_update_locked()
    finally: UPDATE_DOWNLOAD_LOCK.release()

def background_update_worker():
    """While the local helper runs, periodically check the configured feed and optionally stage a verified ZIP. Never auto-apply code."""
    while True:
        time.sleep(300)
        try:
            cfg=_read_update_settings()
            if not cfg['autoCheck'] or not cfg['manifestUrl']: continue
            result=check_for_update(force=False)
            if not result.get('ok') or not result.get('updateAvailable') or not cfg['autoDownload']: continue
            staged=_load_json_file(UPDATE_STATE_PATH,{})
            version=str(result.get('availableVersion') or '')
            if staged.get('stagedVersion')==version and UPDATE_STAGE_PATH.exists(): continue
            # Avoid hammering GitHub every five minutes when a release is temporarily unavailable.
            if staged.get('lastAutoDownloadAttemptVersion')==version and staged.get('lastAutoDownloadAttemptAt'):
                try:
                    previous=datetime.datetime.fromisoformat(str(staged['lastAutoDownloadAttemptAt']).replace('Z','+00:00'))
                    if (datetime.datetime.now(datetime.timezone.utc)-previous).total_seconds()<3600: continue
                except Exception: pass
            staged['lastAutoDownloadAttemptVersion']=version
            staged['lastAutoDownloadAttemptAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            _write_json_file(UPDATE_STATE_PATH,staged)
            download_verified_update()
        except Exception:
            # Update checking must not interrupt the local server or user work.
            continue

def apply_staged_update():
    state=_load_json_file(UPDATE_STATE_PATH,{})
    if not UPDATE_STAGE_PATH.exists() or not state.get('stagedVersion') or not state.get('stagedSha256'): return 400, {'ok':False,'error':'NO_STAGED_UPDATE','message':'검증된 업데이트 패키지가 없습니다.'}
    try:
        if _version_tuple(state['stagedVersion'])<=_version_tuple(APP_VERSION): return 400, {'ok':False,'error':'NOT_NEWER','message':'다운로드한 버전이 현재 버전보다 새롭지 않습니다.'}
        blob=UPDATE_STAGE_PATH.read_bytes(); _digest,names=_validate_update_zip_bytes(blob,state['stagedSha256'],state['stagedVersion'])
        backup_dir=USER_DATA_ROOT/'backups'; backup_dir.mkdir(parents=True,exist_ok=True); stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path=backup_dir/f'ShortCompass_backup_v{APP_VERSION}_{stamp}.zip'
        existed=[n for n in names if (ROOT/n).is_file()]
        with zipfile.ZipFile(backup_path,'w',compression=zipfile.ZIP_DEFLATED) as backup:
            for name in existed: backup.write(ROOT/name,arcname=name)
        temp_root=Path(tempfile.mkdtemp(prefix='.shortcompass-update-',dir=str(ROOT))); saved_old={}; installed=[]
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                for name in names:
                    with zf.open(name) as src,open(temp_root/name,'wb') as dst: shutil.copyfileobj(src,dst)
            for name in names:
                target=ROOT/name
                if target.exists(): saved_old[name]=target.read_bytes()
                os.replace(temp_root/name,target); installed.append(name)
        except Exception:
            for name in reversed(installed):
                target=ROOT/name
                if name in saved_old: target.write_bytes(saved_old[name])
                elif target.exists(): target.unlink()
            raise
        finally: shutil.rmtree(temp_root,ignore_errors=True)
        state.update({'lastAppliedVersion':state.get('stagedVersion'),'lastAppliedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backupPath':str(backup_path),'stagedVersion':None,'stagedSha256':None,'stagedFiles':[]})
        _write_json_file(UPDATE_STATE_PATH,state)
        try: UPDATE_STAGE_PATH.unlink()
        except OSError: pass
        return 200, {'ok':True,'applied':True,'version':state['lastAppliedVersion'],'backupPath':str(backup_path),'files':installed,'message':'업데이트가 적용되었습니다. 브라우저를 새로 고침하고 로컬 서버를 재시작하세요.'}
    except Exception as e: return 500, {'ok':False,'error':'APPLY_FAILED','message':'적용 실패: '+str(e)[:300]+' 기존 파일은 가능한 범위에서 복구했습니다.'}

# -------- Provider-neutral AI workbench --------
AI_SYSTEM_POLICY = '''당신은 숏폼 콘텐츠 제작, 조사 설계, 편집, SEO, 데이터 해석을 돕는 안전한 전문 조력자입니다.
정책 준수: 불법 행위, 위험한 피해 방법, 괴롭힘/혐오, 사기, 플랫폼 탐지·제재 우회, 저작권 보호 회피를 돕지 않습니다. 그런 요청은 실행 방법 대신 안전하고 허용되는 대안을 제시합니다.
저작권: 타인의 원본을 대량 복제하거나 단순 번역/재업로드를 권하지 않습니다. 새로운 해설·비평·교육 맥락을 권하되 이것만으로 저작권 면책이나 수익 창출 자격이 보장된다고 말하지 않습니다.
사실성: 모르는 사실을 만들지 말고, 실시간 자료를 확인하지 못했으면 확인 필요로 표시합니다. 가짜 출처/링크/통계/인용을 꾸며내지 않습니다. 건강·금융·법률 주장은 과장하지 않고 공식/전문 출처 확인을 권합니다.
플랫폼: 정책 위반 여부나 수익 창출 승인을 보장하지 않습니다. 제목/썸네일은 내용과 일치해야 하고 시청자 기만, 스팸, 허위참여를 조장하지 않습니다.
개인정보·보안: API 키, 비밀번호, 인증 토큰을 출력하지 않습니다. 답변은 한국어로, 실행 가능하고 불확실성을 구분해 작성합니다.'''
def _ai_key_for(provider):
    env={'openai':'OPENAI_API_KEY','gemini':'GEMINI_API_KEY','anthropic':'ANTHROPIC_API_KEY'}.get(provider)
    return (SESSION_AI_KEYS.get(provider) or (os.environ.get(env,'') if env else '') or '').strip()

def ai_status_view():
    vars={'openai':('OPENAI_API_KEY','OpenAI'),'gemini':('GEMINI_API_KEY','Gemini'),'anthropic':('ANTHROPIC_API_KEY','Anthropic Claude')}
    saved=_load_json_file(AI_MODELS_PATH,{})
    rows=[]
    for pid,(env,label) in vars.items():
        cat=AI_MODEL_CATALOGS.get(pid) or {}
        model=(saved.get(pid) if isinstance(saved,dict) else '') or AI_DEFAULT_MODELS[pid]
        catalog_ids={x.get('id') for x in cat.get('models',[]) if isinstance(x,dict)}
        rows.append({'id':pid,'label':label,'configured':bool(_ai_key_for(pid)),'keySource':'session-memory' if SESSION_AI_KEYS.get(pid) else ('environment' if os.environ.get(env) else 'not-configured'),'defaultModel':AI_DEFAULT_MODELS[pid],'selectedModel':model,'catalogRetrievedAt':cat.get('retrievedAt'),'catalogCount':len(cat.get('models',[])),'selectedModelListed':(model in catalog_ids) if cat else None})
    return {'ok':True,'providers':rows,'routingPriorities':AI_TASK_ROUTING_PRIORITY,'keyPersistence':'API 키는 로컬 서버 프로세스 메모리 또는 운영체제 환경 변수에서만 읽습니다. 브라우저 저장소·모델 설정 파일·백업에 키를 기록하지 않습니다. 세션 키는 서버 종료 시 사라집니다.'}

def configure_ai_session(payload):
    provider=str(payload.get('provider') or '').lower(); key=str(payload.get('key') or '').strip()
    if provider not in SESSION_AI_KEYS: return 400, {'ok':False,'error':'INVALID_PROVIDER','message':'OpenAI, Gemini 또는 Anthropic Claude를 선택하세요.'}
    if key and (len(key)>500 or any(c.isspace() for c in key)): return 400, {'ok':False,'error':'INVALID_KEY_FORMAT','message':'API 키에 공백이 있거나 길이가 올바르지 않습니다.'}
    model=str(payload.get('model') or AI_DEFAULT_MODELS[provider]).strip()
    if not model or len(model)>120 or not re.fullmatch(r'[A-Za-z0-9._:/-]+',model): return 400, {'ok':False,'error':'INVALID_MODEL','message':'모델 ID를 확인하세요.'}
    if key: SESSION_AI_KEYS[provider]=key
    elif SESSION_AI_KEYS.get(provider): SESSION_AI_KEYS[provider]=''
    models=_load_json_file(AI_MODELS_PATH,{})
    models[provider]=model
    try: _write_json_file(AI_MODELS_PATH,models)
    except OSError: pass
    return 200, {'ok':True,'status':ai_status_view(),'provider':provider,'model':model,'message':'키가 현재 서버 세션 메모리에 연결되었습니다.' if key else '세션 키 연결을 해제했습니다. 환경 변수 키가 있으면 계속 사용할 수 있습니다.'}

def _ai_model_for(provider, supplied):
    model=str(supplied or '').strip()
    if not model:
        saved=_load_json_file(AI_MODELS_PATH,{})
        model=(saved.get(provider) if isinstance(saved,dict) else '') or AI_DEFAULT_MODELS[provider]
    if len(model)>120 or not re.fullmatch(r'[A-Za-z0-9._:/-]+',model): raise ValueError('모델 ID 형식을 확인하세요.')
    return model

def _read_limited_response(resp, limit=2500000):
    raw=resp.read(limit+1)
    if len(raw)>limit: raise ValueError('AI 응답이 허용 크기를 초과했습니다.')
    return json.loads(raw.decode('utf-8'))

def list_provider_models(payload):
    provider=str(payload.get('provider') or '').lower()
    if provider not in AI_PROVIDER_ENDPOINTS: return 400, {'ok':False,'error':'INVALID_PROVIDER','message':'지원하지 않는 AI 제공자입니다.'}
    key=_ai_key_for(provider)
    if not key: return 400, {'ok':False,'error':'MISSING_API_KEY','provider':provider,'message':'먼저 이 제공자의 API 키를 세션에 연결하거나 운영체제 환경 변수를 설정하세요.'}
    url=AI_MODEL_LIST_ENDPOINTS[provider]
    headers={'Accept':'application/json','User-Agent':'ShortCompass-AI/'+APP_VERSION}
    if provider=='openai': headers['Authorization']='Bearer '+key
    elif provider=='gemini': headers['x-goog-api-key']=key
    else:
        headers['x-api-key']=key; headers['anthropic-version']='2023-06-01'
    started=time.monotonic()
    try:
        req=Request(url,headers=headers,method='GET')
        with _open_provider_url(req,timeout=25,provider=provider) as resp: data=_read_limited_response(resp,limit=2_500_000)
        raw_models=[]
        if provider=='gemini':
            for item in data.get('models',[]):
                methods=item.get('supportedGenerationMethods') or item.get('supported_generation_methods') or []
                if 'generateContent' not in methods and 'generate_content' not in methods: continue
                raw_models.append({'id':str(item.get('name',''))[7:] if str(item.get('name','')).startswith('models/') else str(item.get('name','')),'displayName':str(item.get('displayName') or item.get('name') or ''),'description':str(item.get('description') or '')[:200]})
        else:
            source=data.get('data') or data.get('models') or []
            for item in source:
                mid=(str(item.get('id') or item.get('name') or '')[7:] if str(item.get('id') or item.get('name') or '').startswith('models/') else str(item.get('id') or item.get('name') or ''))
                if not mid: continue
                raw_models.append({'id':mid,'displayName':str(item.get('display_name') or item.get('displayName') or mid),'description':str(item.get('description') or '')[:200]})
        # Keep the response bounded; the API endpoint's list is a catalogue, not proof every model can generate.
        dedup={}
        for item in raw_models:
            if re.fullmatch(r'[A-Za-z0-9._:/-]{1,180}',item['id']): dedup[item['id']]=item
        models=list(dedup.values())[:300]
        models.sort(key=lambda x:(x['id']!=AI_DEFAULT_MODELS[provider],x['id'].casefold()))
        if not models: raise ValueError('제공자 API에서 사용할 모델 목록을 찾지 못했습니다. API 문서와 키 권한을 확인하세요.')
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        AI_MODEL_CATALOGS[provider]={'retrievedAt':now,'models':models}
        selected=_ai_model_for(provider,'')
        return 200, {'ok':True,'provider':provider,'models':models,'count':len(models),'retrievedAt':now,'elapsedMs':round((time.monotonic()-started)*1000),'selectedModel':selected,'selectedModelListed':selected in {m['id'] for m in models},'note':'계정 API가 반환한 모델 목록입니다. 목록에 있어도 메시지 생성 권한·결제 한도·리전 접근이 보장되지는 않습니다. 연결 테스트로 실제 생성을 확인하세요.'}
    except HTTPError as e:
        return 502, {'ok':False,'error':'AI_MODEL_LIST_HTTP_ERROR','provider':provider,'status':e.code,'message':f'{provider} 모델 목록 조회 HTTP {e.code}. API 키, 계정 접근 권한, 호출 한도를 확인하세요. 응답 본문은 민감정보 보호를 위해 표시하지 않습니다.'}
    except (URLError,TimeoutError,OSError,ValueError) as e:
        return 502, {'ok':False,'error':'AI_MODEL_LIST_FAILED','provider':provider,'message':'모델 목록을 불러오지 못했습니다: '+str(e)[:300]}

AI_TASKS = {
    'plan':'주제·대상·차별점·검증 자료·다음 행동을 포함한 기획서를 작성하세요.',
    'script':'독창적인 숏폼 대본을 작성하세요. 후킹, 내레이션, 화면/자막 아이디어, 사실 확인 목록을 구분하세요.',
    'packaging':'서로 다른 제목·후킹·CTA를 만들고 과장 위험 및 비교 실험 계획을 포함하세요.',
    'review':'제공한 결과를 비판적으로 검토하고 명확성·근거·저작권·시청자 오해·정책 위험과 안전한 수정안을 제시하세요.',
    'research':'실시간 웹 검증을 했다고 주장하지 마세요. 주장별 확인할 사실, 공식 출처 유형, 검색어, 확인된 것과 추정을 분리한 조사 계획을 작성하세요.',
    'seo':'검색 의도에 맞는 제목·설명·해시태그·키워드를 만들되 키워드 스터핑과 허위 약속은 피하세요.',
    'connectivity_test':'이것은 연결 테스트입니다. 다른 설명 없이 READY 한 단어만 출력하세요.'
}

def _normalize_ai_images(images):
    if images in (None, []): return []
    if not isinstance(images,list) or len(images)>8: raise ValueError('이미지는 최대 8장까지만 전송할 수 있습니다.')
    normalized=[]; total=0
    for index,item in enumerate(images,1):
        if not isinstance(item,dict): raise ValueError(f'{index}번 이미지 형식이 올바르지 않습니다.')
        data_url=str(item.get('dataUrl') or item.get('url') or '')
        match=re.fullmatch(r'data:image/(jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=]+)',data_url)
        if not match: raise ValueError(f'{index}번 이미지는 JPEG/PNG/WebP data URL이어야 합니다.')
        mime='image/jpeg' if match.group(1) in ('jpeg','jpg') else 'image/'+match.group(1)
        b64=match.group(2)
        if len(b64)>2_800_000: raise ValueError(f'{index}번 이미지가 허용 크기를 초과했습니다.')
        try: raw=base64.b64decode(b64,validate=True)
        except Exception: raise ValueError(f'{index}번 이미지의 Base64 데이터가 올바르지 않습니다.')
        if not raw or len(raw)>2_000_000: raise ValueError(f'{index}번 이미지 크기는 1 byte~2MB여야 합니다.')
        valid_signature = (
            (mime=='image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or
            (mime=='image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or
            (mime=='image/webp' and len(raw)>=12 and raw.startswith(b'RIFF') and raw[8:12]==b'WEBP')
        )
        if not valid_signature: raise ValueError(f'{index}번 이미지의 실제 파일 형식이 선언한 MIME과 일치하지 않습니다.')
        total+=len(raw)
        if total>12*1024*1024: raise ValueError('이미지 전체 크기는 12MB를 초과할 수 없습니다.')
        try: frame_time=max(0.0,min(86400.0,float(item.get('time',index-1))))
        except (TypeError,ValueError): frame_time=float(index-1)
        normalized.append({'mimeType':mime,'data':b64,'time':frame_time,'dataUrl':data_url})
    return normalized

def generate_with_provider(payload):
    global AI_LAST_REQUEST
    provider=str(payload.get('provider') or 'openai').lower(); task=str(payload.get('task') or 'script').lower(); prompt=str(payload.get('prompt') or '').strip()
    if provider not in AI_PROVIDER_ENDPOINTS: return 400, {'ok':False,'error':'INVALID_PROVIDER','message':'지원하지 않는 AI 제공자입니다.'}
    if task not in AI_TASKS: return 400, {'ok':False,'error':'INVALID_TASK','message':'지원하지 않는 작업 유형입니다.'}
    if not prompt: return 400, {'ok':False,'error':'EMPTY_PROMPT','message':'작업 내용을 입력하세요.'}
    if len(prompt)>60000: return 413, {'ok':False,'error':'PROMPT_TOO_LONG','message':'입력은 60,000자 이하로 줄이세요.'}
    try: images=_normalize_ai_images(payload.get('images'))
    except ValueError as e: return 400, {'ok':False,'error':'INVALID_IMAGES','message':str(e)}
    env={'openai':'OPENAI_API_KEY','gemini':'GEMINI_API_KEY','anthropic':'ANTHROPIC_API_KEY'}[provider]; key=SESSION_AI_KEYS.get(provider) or os.environ.get(env,'')
    if not key: return 400, {'ok':False,'error':'MISSING_API_KEY','message':provider+' API 키가 연결되어 있지 않습니다. 설정에서 현재 세션에 연결하거나 운영체제 환경 변수를 설정하세요.'}
    try: model=_ai_model_for(provider,payload.get('model'))
    except ValueError as e: return 400, {'ok':False,'error':'INVALID_MODEL','message':str(e)}
    system=AI_SYSTEM_POLICY+'\n\n[작업 지침]\n'+AI_TASKS[task]; headers={'Content-Type':'application/json','User-Agent':'ShortCompass-AI/'+APP_VERSION}
    max_tokens=24 if payload.get('_connection_test') is True else 5000
    if provider=='openai':
        url=AI_PROVIDER_ENDPOINTS[provider]; headers['Authorization']='Bearer '+key
        if images:
            content=[{'type':'input_text','text':prompt}]
            for img in images:
                content.extend([{'type':'input_text','text':'Sampled frame at '+f"{img['time']:.1f}"+' seconds.'},{'type':'input_image','image_url':img['dataUrl'],'detail':'low'}])
            user_input=[{'role':'user','content':content}]
        else: user_input=prompt
        body={'model':model,'instructions':system,'input':user_input,'max_output_tokens':max_tokens}
    elif provider=='gemini':
        url=AI_PROVIDER_ENDPOINTS[provider].format(model=quote_plus(model)); headers['x-goog-api-key']=key
        parts=[{'text':prompt}]
        for img in images:
            parts.extend([{'text':'Sampled frame at '+f"{img['time']:.1f}"+' seconds.'},{'inlineData':{'mimeType':img['mimeType'],'data':img['data']}}])
        body={'systemInstruction':{'parts':[{'text':system}]},'contents':[{'role':'user','parts':parts}],'generationConfig':{'maxOutputTokens':max_tokens,'temperature':0.5}}
    else:
        url=AI_PROVIDER_ENDPOINTS[provider]; headers['x-api-key']=key; headers['anthropic-version']='2023-06-01'
        content=[{'type':'text','text':prompt}]
        for img in images:
            content.extend([{'type':'text','text':'Sampled frame at '+f"{img['time']:.1f}"+' seconds.'},{'type':'image','source':{'type':'base64','media_type':img['mimeType'],'data':img['data']}}])
        body={'model':model,'max_tokens':max_tokens,'system':system,'messages':[{'role':'user','content':content}]}
    with AI_REQUEST_LOCK:
        wait=max(0,1.0-(time.monotonic()-AI_LAST_REQUEST))
        if wait: time.sleep(wait)
        AI_LAST_REQUEST=time.monotonic()
    started=time.monotonic()
    try:
        req=Request(url,data=json.dumps(body).encode('utf-8'),headers=headers,method='POST')
        with _open_provider_url(req,timeout=70,provider=provider) as resp: data=_read_limited_response(resp)
        if provider=='openai':
            result=str(data.get('output_text') or '').strip()
            if not result: result='\n'.join(c.get('text','') for out in data.get('output',[]) for c in out.get('content',[]) if c.get('type')=='output_text').strip()
        elif provider=='gemini': result='\n'.join(p.get('text','') for c in data.get('candidates',[]) for p in (c.get('content') or {}).get('parts',[]) if p.get('text')).strip()
        else: result='\n'.join(c.get('text','') for c in data.get('content',[]) if c.get('type')=='text').strip()
        if not result: raise ValueError('AI 제공자가 비어 있는 답변을 반환했습니다. 안전 필터, 모델 ID, 응답 형식을 확인하세요.')
        return 200, {'ok':True,'provider':provider,'model':model,'task':task,'text':result,'elapsedMs':round((time.monotonic()-started)*1000),'policyPrompt':'안전/사실성 지침을 요청에 포함함','note':'AI 결과는 초안입니다. 최신 사실·출처·저작권·플랫폼 정책 및 전문 영역 주장은 게시 전에 검토해야 합니다.'}
    except HTTPError as e:
        try: detail=e.read(1200).decode('utf-8','replace')
        except Exception: detail=''
        return 502, {'ok':False,'error':'AI_PROVIDER_HTTP_ERROR','provider':provider,'status':e.code,'message':f'{provider} API HTTP {e.code}. 응답 본문은 민감정보 노출 방지를 위해 표시하지 않습니다. 키·모델 ID·할당량·결제 상태를 확인하세요.'}
    except (URLError,TimeoutError,OSError,ValueError) as e: return 502, {'ok':False,'error':'AI_PROVIDER_ERROR','provider':provider,'message':'AI 요청 실패: '+str(e)[:400]}

def test_provider_connection(payload):
    provider=str(payload.get('provider') or '').lower()
    if provider not in AI_PROVIDER_ENDPOINTS: return 400, {'ok':False,'error':'INVALID_PROVIDER','message':'지원하지 않는 AI 제공자입니다.'}
    model=str(payload.get('model') or '').strip()
    try: model=_ai_model_for(provider,model)
    except ValueError as e: return 400, {'ok':False,'error':'INVALID_MODEL','message':str(e)}
    status,result=generate_with_provider({'provider':provider,'task':'connectivity_test','prompt':'Reply with exactly the word READY.','model':model,'_connection_test':True})
    if status!=200 or not result.get('ok'):
        return status, {'ok':False,'provider':provider,'model':model,'error':result.get('error','CONNECTION_TEST_FAILED'),'message':result.get('message','AI 생성 연결 테스트가 실패했습니다.')}
    return 200, {'ok':True,'provider':provider,'model':model,'elapsedMs':result.get('elapsedMs',0),'responseReceived':bool(result.get('text')),'responsePreview':result.get('text','')[:80],'note':'실제 생성 요청으로 연결을 확인했습니다. 적은 토큰을 사용하지만 API 요금/할당량이 발생할 수 있습니다.'}

def auto_generate_with_router(payload):
    task=str(payload.get('task') or 'script').lower(); prompt=str(payload.get('prompt') or '').strip()
    if task not in AI_TASK_ROUTING_PRIORITY: return 400, {'ok':False,'error':'INVALID_TASK','message':'자동 라우팅에서 지원하지 않는 작업 유형입니다.'}
    if not prompt: return 400, {'ok':False,'error':'EMPTY_PROMPT','message':'작업 내용을 입력하세요.'}
    if len(prompt)>60000: return 413, {'ok':False,'error':'PROMPT_TOO_LONG','message':'입력은 60,000자 이하로 줄이세요.'}
    try: images=_normalize_ai_images(payload.get('images'))
    except ValueError as e: return 400, {'ok':False,'error':'INVALID_IMAGES','message':str(e)}
    priority=AI_TASK_ROUTING_PRIORITY[task]
    configured=[p for p in priority if _ai_key_for(p)]
    if not configured: return 400, {'ok':False,'error':'NO_CONNECTED_PROVIDER','message':'자동 선택에 사용할 AI API 키가 없습니다. 최소 한 개 제공자를 연결하세요.'}
    if not bool(payload.get('allowFallback',False)): configured=configured[:1]
    attempts=[]
    for provider in configured:
        try: model=_ai_model_for(provider,'')
        except ValueError: model=AI_DEFAULT_MODELS[provider]
        status,result=generate_with_provider({'provider':provider,'task':task,'prompt':prompt,'model':model,'images':payload.get('images') or []})
        attempts.append({'provider':provider,'model':model,'httpStatus':status,'ok':bool(result.get('ok')),'error':result.get('error')})
        if status==200 and result.get('ok'):
            result['routingMode']='task-priority';result['routingPriority']=priority;result['attempts']=attempts
            result['note']=result.get('note','')+' 자동 선택은 사용자가 연결한 제공자 중 고정된 작업별 우선순위를 이용한 휴리스틱이며, 모든 작업에서 더 우수하다는 보장은 아닙니다.'
            if len(attempts)>1: result['note']+=' 앞선 제공자 실패로 다음 연결된 제공자를 사용했습니다. 실패 요청에서도 제공자에 따라 요금/할당량이 적용될 수 있습니다.'
            return 200,result
        # Without explicit failover, return after the first attempt. With failover, try next connected provider.
        if not bool(payload.get('allowFallback',False)):
            return status,result
    last=attempts[-1] if attempts else {}
    return 502, {'ok':False,'error':'ALL_CONNECTED_PROVIDERS_FAILED','message':'연결된 제공자로 생성할 수 없었습니다. API 키, 모델 접근, 할당량, 결제를 확인하세요. 각 시도에서 민감한 응답 본문은 표시하지 않았습니다.','attempts':attempts,'lastProvider':last.get('provider')}


def policy_precheck(payload):
    text=str(payload.get('text') or '')
    if not text.strip(): return {'ok':False,'error':'EMPTY_TEXT','message':'검토할 텍스트를 입력하세요.','checks':[]}
    if len(text)>100000: return {'ok':False,'error':'TEXT_TOO_LONG','message':'검토할 텍스트는 100,000자 이하로 줄이세요.','checks':[]}
    checks=[]
    rules=[('권리/재사용',r'(그대로\s*(?:번역|재업로드|복사)|워터마크\s*제거|저작권\s*(?:피하기|우회)|원본\s*영상\s*(?:통째로|그대로))','높음','사용 권한을 확인하고 자체 제작·라이선스·허가받은 자료를 우선하세요.'),('허위·과장 약속',r'(100\s*%\s*(?:보장|확실)|무조건\s*(?:수익|돈|합격|완치)|절대\s*(?:안\s*걸|제재\s*안)|확정\s*수익|수익\s*보장)','높음','근거 없는 보장 표현을 삭제하고 조건·한계·근거를 적으세요.'),('건강 관련 주장',r'(암을\s*(?:치료|예방|없애)|완치된다|독소를\s*(?:제거|배출)|약을\s*끊어|치료제라고)','높음','건강 주장을 의학 근거로 확인하고 치료 효과를 단정하지 마세요.'),('금융/투자 주장',r'(원금\s*보장|손실\s*없(?:다|는)|확정\s*수익|매달\s*\d+\s*%\s*수익|무조건\s*오른다)','높음','위험과 조건을 명시하고 보장성 표현을 피하세요.'),('기만/스팸',r'(댓글\s*도배|가짜\s*댓글|조회수\s*조작|봇으로\s*(?:조회|구독)|무한\s*계정)','중간','허위 참여·스팸을 피하고 시청자의 자발적인 CTA를 사용하세요.'),('사실 확인 필요',r'(속보|충격\s*실화|전문가가\s*인정|연구에\s*따르면|통계에\s*따르면|과학적으로\s*증명)','중간','주장에 출처·날짜·표본을 붙여 검증하고 근거가 약하면 표현을 낮추세요.')]
    for label,pattern,severity,advice in rules:
        matches=re.findall(pattern,text,flags=re.I)
        if matches: checks.append({'area':label,'severity':severity,'matchCount':len(matches),'advice':advice})
    return {'ok':True,'checks':checks,'status':'REVIEW_REQUIRED' if any(x['severity']=='높음' for x in checks) else ('CHECK_SUGGESTED' if checks else 'NO_RULE_MATCH'),'matchedRules':len(checks),'note':'규칙 기반 사전 점검입니다. 공식 플랫폼 판정·저작권 판단·법률 조언 또는 통과 보증이 아닙니다. 규칙에 잡히지 않아도 위반일 수 있습니다.'}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self, fmt, *args): pass
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path=='/api/search':
            query=parse_qs(parsed.query).get('q',[''])[0].strip()
            if not query:
                return self.send_json(400,{'ok':False,'error':'EMPTY_QUERY','message':'검색어를 입력하세요.','results':[],'recovery':search_recovery_advice('EMPTY_QUERY')})
            if len(query)>MAX_QUERY:
                return self.send_json(400,{'ok':False,'error':'QUERY_TOO_LONG','message':f'검색어는 {MAX_QUERY}자 이내로 입력하세요.','results':[],'recovery':search_recovery_advice('QUERY_TOO_LONG')})
            result=search_public_index(query)
            return self.send_json(200 if result.get('ok') else 502,result)
        if parsed.path=='/api/diagnostics': return self.send_json(200, run_network_diagnostics())
        if parsed.path=='/api/diagnostics/full': return self.send_json(200, run_full_diagnostics())
        if parsed.path=='/api/search-diagnostics': return self.send_json(200, run_search_engine_diagnostics())
        if parsed.path=='/api/update/config': return self.send_json(200, update_settings_view())
        if parsed.path=='/api/update/check': return self.send_json(200, check_for_update(force=parse_qs(parsed.query).get('force',['0'])[0]=='1'))
        if parsed.path=='/api/ai/status': return self.send_json(200,ai_status_view())
        if parsed.path=='/health': return self.send_json(200,{'ok':True,'service':'ShortCompass local helper','version':APP_VERSION})
        return super().do_GET()
    def do_POST(self):
        parsed=urlparse(self.path); origin=self.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765'):
            return self.send_json(403,{'ok':False,'error':'ORIGIN_DENIED','message':'로컬 앱에서 보낸 요청만 허용됩니다.'})
        routes={'/api/tiktok-research':MAX_POST_BYTES,'/api/update/config':65536,'/api/update/download':65536,'/api/update/apply':65536,'/api/ai/configure':65536,'/api/ai/models':65536,'/api/ai/test':65536,'/api/ai/auto-generate':MAX_AI_BODY_BYTES,'/api/ai/generate':MAX_AI_BODY_BYTES,'/api/policy/precheck':200000}
        if parsed.path not in routes: return self.send_json(404,{'ok':False,'error':'NOT_FOUND','message':'요청한 API 경로를 찾을 수 없습니다.'})
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: length=0
        if length<1 or length>routes[parsed.path]: return self.send_json(413,{'ok':False,'error':'INVALID_BODY_SIZE','message':'요청 데이터가 비어 있거나 허용 크기를 초과했습니다.'})
        try:
            payload=json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(payload,dict): raise ValueError('JSON object required')
        except Exception: return self.send_json(400,{'ok':False,'error':'INVALID_JSON','message':'요청 데이터 형식이 올바르지 않습니다.'})
        if parsed.path=='/api/tiktok-research': status,result=run_tiktok_research_search(payload); return self.send_json(status,result)
        if parsed.path=='/api/update/config': status,result=save_update_settings(payload); return self.send_json(status,result)
        if parsed.path=='/api/update/download': status,result=download_verified_update(); return self.send_json(status,result)
        if parsed.path=='/api/update/apply': status,result=apply_staged_update(); return self.send_json(status,result)
        if parsed.path=='/api/ai/configure': status,result=configure_ai_session(payload); return self.send_json(status,result)
        if parsed.path=='/api/ai/models': status,result=list_provider_models(payload); return self.send_json(status,result)
        if parsed.path=='/api/ai/test': status,result=test_provider_connection(payload); return self.send_json(status,result)
        if parsed.path=='/api/ai/auto-generate': status,result=auto_generate_with_router(payload); return self.send_json(status,result)
        if parsed.path=='/api/ai/generate': status,result=generate_with_provider(payload); return self.send_json(status,result)
        if parsed.path=='/api/policy/precheck': result=policy_precheck(payload); return self.send_json(200 if result.get('ok') else 400,result)
    def send_json(self,status,obj):
        data=json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    threading.Thread(target=background_update_worker,daemon=True,name='ShortCompassUpdateWorker').start()
    print('숏폼 나침반 로컬 도우미: http://127.0.0.1:8765/ShortsCompass.html')
    print('종료하려면 이 창에서 Ctrl+C를 누르세요.')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
