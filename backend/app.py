import os, json, time, hashlib
from flask import Flask, request, render_template_string, jsonify, abort
from elasticsearch import Elasticsearch, helpers, exceptions as es_exceptions
import redis

ES_HOST = os.environ.get('ES_HOST','localhost')
ES_PORT = int(os.environ.get('ES_PORT',9200))
ES_INDEX = 'documents'
REDIS_HOST = os.environ.get('REDIS_HOST','localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT',6379))

es = Elasticsearch([{'host': ES_HOST, 'port': ES_PORT}])
rds = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

app = Flask(__name__)

TEMPLATE = '''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Organized Search</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body{font-family: Arial, Helvetica, sans-serif; margin:0; padding:20px; background:#f7f8fb;}
    .search-box{max-width:800px;margin:40px auto;text-align:center;}
    input[type=text]{width:70%; padding:14px 16px; font-size:18px; border-radius:8px; border:1px solid #ddd;}
    button{padding:10px 14px;margin-left:8px;border-radius:8px;border:0;background:#2b6cb0;color:white;}
    .results{max-width:900px;margin:20px auto;background:white;padding:20px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);}
    .result{margin-bottom:18px;}
    .title{font-size:18px;color:#1a0dab;text-decoration:none;}
    .url{color:#006621;font-size:13px;}
    .snippet{color:#444;font-size:14px;}
    .meta{font-size:12px;color:#666;margin-top:6px;}
    .card{margin-bottom:12px;padding:12px;border-left:4px solid #eef2ff;background:#fbfbff;border-radius:6px;}
  </style>
</head>
<body>
  <div class="search-box">
    <h1>Organized Search</h1>
    <form action="/search" method="get">
      <input name="q" type="text" placeholder="Search the indexed web..." value="{{q|e}}" autofocus />
      <button type="submit">Search</button>
    </form>
  </div>
  {% if results is defined %}
  <div class="results">
    <div class="card"><strong>About {{total}} results</strong> — took {{t}} ms</div>
    {% for r in results %}
      <div class="result">
        <div class="url">{{r._source.url}}</div>
        <a class="title" href="{{r._source.url}}" target="_blank">{{r._source.title or r._source.url}}</a>
        <div class="snippet">{{r._source.snippet}}</div>
        <div class="meta">Keywords: {{', '.join(r._source.keywords or [])}}</div>
      </div>
    {% endfor %}
  </div>
  {% endif %}
</body>
</html>'''

def ensure_index():
    if not es.indices.exists(index=ES_INDEX):
        mapping = {
            "mappings": {
                "properties": {
                    "url": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "english"},
                    "text": {"type": "text", "analyzer": "english"},
                    "snippet": {"type": "text", "analyzer": "english"},
                    "keywords": {"type": "keyword"},
                    "last_modified": {"type": "date"}
                }
            }
        }
        es.indices.create(index=ES_INDEX, body=mapping)

ensure_index()

@app.route('/')
def home():
    return render_template_string(TEMPLATE)

@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    t0 = time.time()
    cache_key = f"search:{q}" if q else None
    if cache_key:
        cached = rds.get(cache_key)
        if cached:
            res = json.loads(cached)
            res['cached'] = True
            res['t'] = int((time.time()-t0)*1000)
            return render_template_string(TEMPLATE, results=res['hits'], q=q, total=res['total'], t=res['t'])
    results = []
    total = 0
    if q:
        body = {
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": ["title^3", "keywords^4", "text"]
                }
            }
        }
        try:
            resp = es.search(index=ES_INDEX, body=body, size=20)
            hits = resp['hits']['hits']
            total = resp['hits']['total']['value'] if 'total' in resp['hits'] else len(hits)
            results = hits
        except es_exceptions.NotFoundError:
            results = []
        out = {'hits': results, 'total': total}
        if cache_key:
            rds.set(cache_key, json.dumps(out), ex=60)
    t = int((time.time()-t0)*1000)
    return render_template_string(TEMPLATE, results=results, q=q, total=total, t=t)

@app.route('/api/index', methods=['POST'])
def api_index():
    docs = request.get_json() or []
    if not isinstance(docs, list):
        abort(400, 'JSON list expected')
    actions = []
    for d in docs:
        source = {
            'url': d.get('url'),
            'title': d.get('title','')[:300],
            'text': d.get('text',''),
            'snippet': d.get('snippet', '')[:500],
            'keywords': d.get('keywords', []),
            'last_modified': d.get('last_modified')
        }
        actions.append({'_index': ES_INDEX, '_id': source['url'], '_source': source})
    if actions:
        helpers.bulk(es, actions)
    return jsonify({'indexed': len(actions)})

@app.route('/api/ping')
def ping():
    return jsonify({'ok': es.ping()})

@app.route('/admin/stats')
def stats():
    try:
        count = es.count(index=ES_INDEX)['count']
    except:
        count = 0
    cache_info = {'keys': rds.dbsize()}
    return jsonify({'indexed_docs': count, 'cache': cache_info})

@app.route('/admin/reindex', methods=['POST'])
def reindex():
    payload = request.get_json() or {}
    docs = payload.get('docs')
    path = payload.get('path')
    actions = []
    if docs and isinstance(docs, list):
        for d in docs:
            actions.append({'_index': ES_INDEX, '_id': d.get('url'), '_source': d})
    elif path:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for url, d in data.items():
                actions.append({'_index': ES_INDEX, '_id': url, '_source': {
                    'url': url,
                    'title': d.get('title','')[:300],
                    'text': d.get('text',''),
                    'snippet': d.get('text','')[:500],
                    'keywords': d.get('keywords',[]),
                    'last_modified': d.get('last_modified')
                }})
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    if actions:
        helpers.bulk(es, actions)
    return jsonify({'indexed': len(actions)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
