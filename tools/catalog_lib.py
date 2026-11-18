"""Utilidades compartidas por las herramientas del catálogo. No contiene claves: se leen del entorno."""
import json, os, re, sqlite3, time, unicodedata, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'choque_heroes.db')
RARITIES = ['COMÚN', 'INFRECUENTE', 'RARA', 'ÉPICA', 'LEGENDARIA']
ELEMENTS = ['MAGIA', 'FUERZA', 'MENTE', 'TECNOLOGIA', 'ENERGIA']

POWER_VIEW = """
DROP VIEW IF EXISTS v_power;
CREATE VIEW v_power AS
SELECT c.id AS character_id, c.name, ROUND(SUM(cs.value*d.weight)/SUM(d.weight), 1) AS power
FROM characters c JOIN character_stats cs ON cs.character_id=c.id JOIN stat_defs d ON d.key=cs.stat_key
GROUP BY c.id;
"""


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def norm(s):
    s = unicodedata.normalize('NFD', str(s).upper()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Z0-9]', '', s)


def slug(s):
    s = unicodedata.normalize('NFD', str(s).lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def http_json(url, body=None, headers=None, timeout=90):
    h = {'User-Agent': 'choque-heroes-personal/0.1'}
    if body is not None: h['Content-Type'] = 'application/json'
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class QuotaExceeded(Exception):
    pass


def gemini_json(prompt, model='gemini-3-flash-preview', temperature=0.7, retries=5):
    """Pide una respuesta JSON a Gemini. La clave sale de la variable de entorno GEMINI_API_KEY."""
    key = os.environ.get('GEMINI_API_KEY')
    if not key: raise SystemExit('Falta la variable de entorno GEMINI_API_KEY')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    gen = {'responseMimeType': 'application/json', 'temperature': temperature}
    if '2.5' in model: gen['thinkingConfig'] = {'thinkingBudget': 0}
    body = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': gen}
    for i in range(retries):
        try:
            d = http_json(url, body, {'x-goog-api-key': key})
            return json.loads(d['candidates'][0]['content']['parts'][0]['text'])
        except urllib.error.HTTPError as e:
            detail = e.read().decode()
            if e.code == 429 and re.search(r'per day|PerDay', detail, re.I): raise QuotaExceeded(detail[:300])
            if e.code in (429, 500, 503) and i < retries - 1: time.sleep(5 * (i + 1)); continue
            raise RuntimeError(f'Gemini respondió {e.code}: {detail[:200]}')
        except (KeyError, ValueError, urllib.error.URLError):
            if i == retries - 1: raise
            time.sleep(2)


def recompute_rarity(db):
    """Rareza = mezcla de percentil de poder y de fama (peso de la fama en balance_params); reparto en pirámide (cuotas en balance_params)."""
    quota = {r: db.execute('SELECT value FROM balance_params WHERE key=?', ('cuota_' + norm(r).lower(),)).fetchone()[0] for r in RARITIES}
    rows = db.execute('SELECT c.id, v.power, c.fame FROM characters c JOIN v_power v ON v.character_id=c.id').fetchall()
    n = len(rows)
    def pct(vals):
        order = sorted(range(n), key=lambda i: vals[i]); out = [0.0] * n
        for pos, i in enumerate(order): out[i] = (pos + 0.5) / n
        return out
    pf_w = db.execute("SELECT value FROM balance_params WHERE key='rareza_peso_fama'").fetchone()
    wf = pf_w[0] if pf_w else 0.5
    pp = pct([r['power'] for r in rows]); pf = pct([(r['fame'] or 3) + (r['power'] or 0) * 1e-4 for r in rows])
    score = [(1 - wf) * a + wf * b for a, b in zip(pp, pf)]
    order = sorted(range(n), key=lambda i: score[i]); pos = 0; res = {}
    for r in RARITIES:
        k = n - pos if r == RARITIES[-1] else round(quota[r] * n)
        for i in order[pos:pos + k]: res[rows[i]['id']] = r
        pos += k
    db.executemany('UPDATE characters SET rarity=? WHERE id=?', [(r, i) for i, r in res.items()])
    return res
