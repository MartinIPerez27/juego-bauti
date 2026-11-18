#!/usr/bin/env python3
"""Busca y descarga las fotos del catálogo desde fuentes públicas y gratuitas (nunca desde la hoja original).

  python3 tools/fetch_photos.py collect   [--source superhero|fandom|comicvine]   # junta candidatas (solo URLs)
  python3 tools/fetch_photos.py pick                                               # elige una por personaje según prioridad
  python3 tools/fetch_photos.py download                                           # baja y convierte a WebP las elegidas
  python3 tools/fetch_photos.py reject ID [ID ...]                                 # descarta la foto elegida (mala/equivocada) y busca otra
  python3 tools/fetch_photos.py status

Fuentes: SuperHero API (archivo local en caché), Marvel/DC Database (Fandom, MediaWiki) y ComicVine (COMICVINE_API_KEY en el entorno).
Se puede interrumpir y reanudar. Respeta los límites de cada sitio. Uso personal: no publicar las imágenes.
"""
import argparse, concurrent.futures as cf, difflib, hashlib, json, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ROOT, connect, http_json, norm, slug
from missing_heroes import ES_TO_EN, candidates

OUT = os.path.join(ROOT, 'data', 'images')
PRIORITY = {'superhero_api': 1, 'fandom': 2, 'comicvine': 3}
WIKI = {'MARVEL': ('marvel.fandom.com', ['{} (Earth-616)', '{}']), 'DC': ('dc.fandom.com', ['{} (New Earth)', '{}'])}


def english(name):
    return re.sub(r'\s+', ' ', ES_TO_EN.get(name, name)).strip()


def title_case(s):
    small = {'of', 'the', 'and', 'de', 'la', 'el', 'y', 'del'}
    return ' '.join(w if (i and w.lower() in small) else (w[:1].upper() + w[1:].lower() if not re.search(r'[A-Z].*[A-Z]', w) or w.isupper() else w)
                    for i, w in enumerate(s.split()))


def add(db, cid, source, url, page=None):
    if not url or db.execute('SELECT 1 FROM images WHERE character_id=? AND source=?', (cid, source)).fetchone(): return False
    db.execute('INSERT INTO images(character_id,source,source_url,page_url,status) VALUES(?,?,?,?,?)', (cid, source, url, page, 'candidata'))
    return True


def collect_superhero(db):
    by = {norm(c['name']): c for c in candidates()}
    n = 0
    for r in db.execute('SELECT id,name FROM characters').fetchall():
        c = by.get(norm(english(r['name'])))
        if c: n += add(db, r['id'], 'superhero_api', c['images'].get('lg') or c['images'].get('md'))
    db.commit(); print('SuperHero API: candidatas nuevas', n)


def collect_fandom(db):
    rows = db.execute("SELECT id,name,universe FROM characters WHERE universe IN ('MARVEL','DC') ORDER BY id").fetchall()
    n = 0
    for uni, (host, patterns) in WIKI.items():
        todo = [r for r in rows if r['universe'] == uni]
        for i in range(0, len(todo), 12):
            batch = todo[i:i + 12]; titles = {}
            for r in batch:
                base = title_case(re.sub(r'\s*\(.*?\)', '', english(r['name'])))
                for p in patterns: titles[p.format(base)] = r['id']
            q = urllib.parse.urlencode({'action': 'query', 'titles': '|'.join(titles), 'redirects': 1, 'prop': 'pageimages',
                                        'piprop': 'original', 'format': 'json', 'formatversion': 2})
            try: d = http_json(f'https://{host}/api.php?{q}')['query']
            except Exception as e: print('  error', e); time.sleep(5); continue
            alias = {}
            for k in ('normalized', 'redirects'):
                for x in d.get(k, []): alias[x['to']] = x['from'] if k == 'normalized' else alias.get(x['from'], x['from'])
            for pg in d.get('pages', []):
                src = (pg.get('original') or {}).get('source')
                if pg.get('missing') or not src: continue
                frm = alias.get(pg['title'], pg['title'])
                for t, cid in titles.items():
                    if t == frm or t == pg['title'] or alias.get(t) == pg['title']:
                        n += add(db, cid, 'fandom', src, f'https://{host}/wiki/' + urllib.parse.quote(pg['title'].replace(' ', '_')))
            db.commit(); time.sleep(0.6)
    print('Fandom: candidatas nuevas', n)


def collect_comicvine(db, limit):
    key = os.environ.get('COMICVINE_API_KEY')
    if not key: raise SystemExit('Falta COMICVINE_API_KEY en el entorno')
    rows = db.execute("""SELECT c.id,c.name FROM characters c WHERE NOT EXISTS
                         (SELECT 1 FROM images i WHERE i.character_id=c.id AND i.status!='rechazada')
                         AND NOT EXISTS (SELECT 1 FROM images i WHERE i.character_id=c.id AND i.source='comicvine')
                         ORDER BY c.fame DESC, c.id""").fetchall()[:limit]
    n = 0
    for r in rows:
        q = urllib.parse.urlencode({'api_key': key, 'format': 'json', 'resources': 'character', 'query': english(r['name']), 'limit': 8,
                                    'field_list': 'name,publisher,image,site_detail_url,count_of_issue_appearances'})
        try: res = http_json('https://comicvine.gamespot.com/api/search/?' + q)['results']
        except Exception as e: print('  error', e); time.sleep(30); continue
        want = norm(english(r['name']))
        ok = [x for x in res if norm(x['name']) == want and (x.get('publisher') or {}).get('name') in ('Marvel', 'DC Comics')] or \
             [x for x in res if difflib.SequenceMatcher(None, norm(x['name']), want).ratio() >= 0.9 and (x.get('publisher') or {}).get('name') in ('Marvel', 'DC Comics')]
        if ok:
            best = max(ok, key=lambda x: x.get('count_of_issue_appearances') or 0)
            n += add(db, r['id'], 'comicvine', (best['image'] or {}).get('super_url') or (best['image'] or {}).get('medium_url'), best.get('site_detail_url'))
        db.commit(); time.sleep(20)       # ComicVine: ~200 pedidos por hora
    print('ComicVine: candidatas nuevas', n)


def pick(db):
    """Elige una foto para cada personaje que todavía no tiene (SuperHero API > Fandom > ComicVine), salteando las rechazadas."""
    got = 0
    for r in db.execute('SELECT id FROM characters c WHERE NOT EXISTS (SELECT 1 FROM images i WHERE i.character_id=c.id AND i.is_selected=1)').fetchall():
        c = db.execute("""SELECT id FROM images WHERE character_id=? AND status IN ('candidata','error') AND status!='rechazada'
                          ORDER BY CASE source WHEN 'superhero_api' THEN 1 WHEN 'fandom' THEN 2 ELSE 3 END LIMIT 1""", (r['id'],)).fetchone()
        if c: db.execute("UPDATE images SET is_selected=1, status='elegida' WHERE id=?", (c['id'],)); got += 1
    db.commit(); print('fotos elegidas ahora:', got, '| con foto elegida en total:', db.execute('SELECT COUNT(*) FROM images WHERE is_selected=1').fetchone()[0], 'de', db.execute('SELECT COUNT(*) FROM characters').fetchone()[0])


def reject(db, ids):
    for cid in ids:
        for r in db.execute("SELECT id,card_path,thumb_path FROM images WHERE character_id=? AND is_selected=1", (cid,)).fetchall():
            for f in (r['card_path'], r['thumb_path']):
                if f and os.path.exists(os.path.join(ROOT, f)): os.remove(os.path.join(ROOT, f))
            db.execute("UPDATE images SET status='rechazada', is_selected=0, card_path=NULL, thumb_path=NULL WHERE id=?", (r['id'],))
    db.commit(); print('rechazadas:', len(ids))


def download(db):
    from PIL import Image
    os.makedirs(OUT, exist_ok=True)
    rows = db.execute("""SELECT i.id,i.source_url,c.slug FROM images i JOIN characters c ON c.id=i.character_id
                         WHERE i.is_selected=1 AND (i.card_path IS NULL OR i.status!='lista')""").fetchall()

    def work(r):
        try:
            req = urllib.request.Request(r['source_url'], headers={'User-Agent': 'choque-heroes-personal/0.1'})
            raw = urllib.request.urlopen(req, timeout=40).read()
            tmp = os.path.join(ROOT, 'data', 'cache', 'tmp_' + r['slug']); os.makedirs(os.path.dirname(tmp), exist_ok=True); open(tmp, 'wb').write(raw)
            im = Image.open(tmp); im.load(); w, h = im.size
            alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
            conv = im.convert('RGBA' if alpha else 'RGB'); conv.thumbnail((480, 720))
            card = os.path.join(OUT, r['slug'] + '.webp'); conv.save(card, 'WEBP', quality=82, method=4)
            t = conv.copy(); t.thumbnail((160, 240)); th = os.path.join(OUT, r['slug'] + '_thumb.webp'); t.save(th, 'WEBP', quality=78, method=4)
            os.remove(tmp)
            return r['id'], (os.path.relpath(card, ROOT), os.path.relpath(th, ROOT), w, h, len(raw), hashlib.sha256(raw).hexdigest(), int(alpha))
        except Exception as e:
            return r['id'], str(e)[:80]
    with cf.ThreadPoolExecutor(6) as ex:
        for iid, res in ex.map(work, rows):
            if isinstance(res, str): db.execute('UPDATE images SET status=? WHERE id=?', ('error: ' + res, iid)); continue
            db.execute('UPDATE images SET card_path=?,thumb_path=?,width=?,height=?,bytes=?,sha256=?,has_alpha=?,status="lista" WHERE id=?', (*res, iid))
    db.commit(); status(db)


def status(db):
    print('fotos listas:', db.execute("SELECT COUNT(*) FROM images WHERE status='lista' AND is_selected=1").fetchone()[0],
          '| candidatas por fuente:', dict(db.execute('SELECT source, COUNT(*) FROM images GROUP BY source').fetchall()),
          '| sin ninguna candidata:', db.execute('SELECT COUNT(*) FROM characters c WHERE NOT EXISTS (SELECT 1 FROM images i WHERE i.character_id=c.id)').fetchone()[0])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['collect', 'pick', 'download', 'status', 'reject']); ap.add_argument('ids', nargs='*', type=int)
    ap.add_argument('--source', choices=['superhero', 'fandom', 'comicvine']); ap.add_argument('--limit', type=int, default=400)
    a = ap.parse_args(); db = connect()
    if a.cmd == 'collect':
        for s in ([a.source] if a.source else ['superhero', 'fandom']):
            {'superhero': collect_superhero, 'fandom': collect_fandom}.get(s, lambda d: collect_comicvine(d, a.limit))(db)
        status(db)
    elif a.cmd == 'pick': pick(db)
    elif a.cmd == 'reject': reject(db, a.ids)
    elif a.cmd == 'download': download(db)
    else: status(db)


if __name__ == '__main__':
    main()
