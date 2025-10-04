# Index docs.json into Elasticsearch; runs keyword extraction using spaCy (English + Arabic if available)
import sys, json, os
from elasticsearch import Elasticsearch, helpers
import spacy

ES_HOST = os.environ.get('ES_HOST','localhost')
ES_PORT = int(os.environ.get('ES_PORT',9200))
ES_INDEX = 'documents'
es = Elasticsearch([{'host': ES_HOST, 'port': ES_PORT}])

# Try to load Arabic and English spaCy models; fall back to multilingual or None.
nlp_en = None
nlp_ar = None
try:
    nlp_en = spacy.load('en_core_web_sm')
except Exception:
    try:
        nlp_en = spacy.load('xx_ent_wiki_sm')
    except Exception:
        nlp_en = None
try:
    nlp_ar = spacy.load('ar_core_news_sm')
except Exception:
    # try multilingual or skip
    try:
        nlp_ar = spacy.load('xx_ent_wiki_sm')
    except Exception:
        nlp_ar = None

def extract_keywords(text, top_k=8, lang='en'):
    # choose model based on lang hint; otherwise try both
    kws = []
    if lang == 'ar' and nlp_ar:
        doc = nlp_ar(text[:10000])
        kws = [ent.text for ent in doc.ents]
        if len(kws) < top_k:
            kws += [chunk.text for chunk in doc.noun_chunks][:top_k-len(kws)]
    elif nlp_en:
        doc = nlp_en(text[:10000])
        kws = [ent.text for ent in doc.ents]
        if len(kws) < top_k:
            kws += [chunk.text for chunk in doc.noun_chunks][:top_k-len(kws)]
    else:
        return []
    # normalize and dedup
    seen = set(); out = []
    for k in kws:
        kk = k.strip().lower()
        if kk and kk not in seen:
            seen.add(kk); out.append(kk)
    return out[:top_k]

def index_docs(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    actions = []
    for url, d in data.items():
        text = d.get('text','')
        # naive language guess: check for Arabic letters
        lang = 'ar' if any('\u0600' <= ch <= '\u06FF' for ch in text) else 'en'
        keywords = extract_keywords(text, lang=lang)
        doc = {
            '_index': ES_INDEX,
            '_id': url,
            '_source': {
                'url': url,
                'title': d.get('title',''),
                'text': text,
                'snippet': d.get('snippet','') or text[:500],
                'keywords': keywords,
                'last_modified': d.get('last_modified')
            }
        }
        actions.append(doc)
    if actions:
        helpers.bulk(es, actions)
        print('Indexed', len(actions))
    else:
        print('No docs to index')

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv)>1 else 'docs.json'
    index_docs(path)
