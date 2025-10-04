# Polite crawler with basic robots.txt check and structured output
import requests, time, json, argparse, re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

USER_AGENT = "OrganizedCrawler/0.2 (+https://example.com)"

def allowed_by_robots(base_url):
    try:
        rp_url = urljoin(base_url, '/robots.txt')
        r = requests.get(rp_url, headers={'User-Agent': USER_AGENT}, timeout=5)
        if r.status_code != 200:
            return True
        txt = r.text.lower()
        if 'disallow: /' in txt:
            return False
        return True
    except:
        return True

def fetch(url):
    try:
        r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=10)
        if r.status_code == 200 and 'text/html' in r.headers.get('Content-Type',''):
            return r.text
    except Exception as e:
        print('fetch error', e)
    return None

def extract_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup(['script','style','noscript']):
        s.extract()
    title = soup.title.string.strip() if soup.title and soup.title.string else ''
    body = soup.get_text(separator=' ')
    body = re.sub(r'\s+', ' ', body).strip()
    desc = ''
    try:
        meta = soup.find('meta', attrs={'name':'description'})
        if meta and meta.get('content'):
            desc = meta['content'].strip()
    except:
        desc = body[:300]
    snippet = (desc or body)[:500]
    return title, body, snippet, desc

def crawl(seeds, max_pages=100, delay=1.0, same_domain=True):
    visited = set()
    docs = {}
    queue = list(seeds)
    while queue and len(docs) < max_pages:
        url = queue.pop(0)
        if url in visited: continue
        visited.add(url)
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if not allowed_by_robots(base):
            print('Blocked by robots:', base)
            continue
        print('Crawling:', url)
        html = fetch(url)
        if not html: continue
        title, text, snippet, desc = extract_text(html)
        docs[url] = {'url': url, 'title': title, 'text': text, 'snippet': snippet, 'description': desc, 'last_modified': None, 'keywords': []}
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('#') or href.startswith('mailto:'): continue
            absurl = urljoin(base, href)
            if same_domain and urlparse(absurl).netloc != parsed.netloc:
                continue
            if absurl not in visited and absurl not in queue:
                queue.append(absurl)
        time.sleep(delay)
    return docs

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', default='seeds.txt')
    parser.add_argument('--max-pages', type=int, default=50)
    args = parser.parse_args()
    seeds = []
    with open(args.seeds, 'r') as f:
        for line in f:
            line=line.strip()
            if line: seeds.append(line)
    docs = crawl(seeds, max_pages=args.max_pages)
    with open('docs.json', 'w', encoding='utf-8') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print('Saved', len(docs), 'documents to docs.json')
