#!/usr/bin/env python3
"""Busca en dc.com/characters (sitio oficial, robots.txt lo permite) las fotos de los personajes de DC que no tienen foto.

  python3 tools/dc_official.py index            # lee el sitemap y guarda nombre -> imágenes en data/cache/dc_official.json
  python3 tools/dc_official.py match            # muestra qué personajes sin foto tienen ficha oficial
  python3 tools/dc_official.py download         # baja la foto (versión vertical) de los que coinciden
Uso personal. Pide pocas páginas, con pausa, y se identifica con un nombre propio.
"""
import json, os, re, sys, time, urllib.request, io, hashlib
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ROOT, connect, norm

UA = {'User-Agent': 'choque-heroes-personal/0.1'}
CACHE = os.path.join(ROOT, 'data', 'cache', 'dc_official.json')
OUT = os.path.join(ROOT, 'data', 'images')


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()


def index():
    sm = get('https://www.dc.com/merged.sitemap.dc.xml').decode()
    urls = [u for u in re.findall(r'<loc>([^<]+)</loc>', sm) if '/characters/' in u]
    res = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    for n, u in enumerate(urls):
        if u in res: continue
        try:
            s = get(u).decode('utf8', 'ignore')
            t = re.search(r'og:title" content="([^"|]+?) \|', s)
            th = re.search(r'cuts\.0\.url%\]","value":"([^"]+)"', s); pr = re.search(r'cuts\.1\.url%\]","value":"([^"]+)"', s)
            res[u] = {'name': t.group(1).strip() if t else None, 'thumb': th.group(1) if th else None, 'profile': pr.group(1) if pr else None}
        except Exception as e:
            res[u] = {'error': str(e)[:80]}
        if n % 25 == 0: json.dump(res, open(CACHE, 'w'), ensure_ascii=False); print(n, '/', len(urls), flush=True)
        time.sleep(0.35)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True); json.dump(res, open(CACHE, 'w'), ensure_ascii=False)
    print('fichas leídas:', len(res), '| con imagen:', sum(1 for v in res.values() if v.get('thumb')))


ES = {'ACERTIJO': 'RIDDLER', 'PINGUINO': 'PENGUIN', 'ESPANTAPAJAROS': 'SCARECROW', 'DOSCARAS': 'TWOFACE', 'HIEDRAVENENOSA': 'POISONIVY', 'CARADEARCILLA': 'CLAYFACE',
      'SOMBREROLOCO': 'MADHATTER', 'COCODRILOASESINO': 'KILLERCROC', 'CAPITANFRIO': 'CAPTAINCOLD', 'CAPITANBOOMERANG': 'CAPTAINBOOMERANG', 'SENORFREEZE': 'MRFREEZE',
      'MUJERMARAVILLA': 'WONDERWOMAN', 'FLECHAVERDE': 'GREENARROW', 'LINTERNAVERDE': 'GREENLANTERN', 'CANARIONEGRO': 'BLACKCANARY', 'GORILAGRODD': 'GORILLAGRODD',
      'SINIESTRO': 'SINESTRO', 'FLASHREVERSO': 'REVERSEFLASH', 'ATOMO': 'ATOM', 'ALFRED': 'ALFREDPENNYWORTH', 'ELVIGILANTE': 'VIGILANTE', 'PLASTICMAN': 'PLASTICMAN'}


def want(db):
    rows = db.execute("""SELECT c.id,c.name FROM characters c WHERE c.universe='DC' AND NOT EXISTS(SELECT 1 FROM images i WHERE i.character_id=c.id AND i.is_selected=1 AND i.status='lista')""").fetchall()
    return rows


def matches(db):
    res = json.load(open(CACHE)); byn = {}
    for u, v in res.items():
        if v.get('name') and v.get('thumb'): byn.setdefault(norm(v['name']), (u, v))
    out = []
    for r in want(db):
        k = norm(r['name']); k = ES.get(k, k)
        if k in byn: out.append((r, byn[k]))
    return out


def match():
    db = connect(); m = matches(db)
    print(f'Sin foto en DC: {len(want(db))} | con ficha oficial: {len(m)}')
    for r, (u, v) in m: print(f"{r['id']:>4} {r['name']:32} -> {v['name']}")


def download():
    db = connect(); ok = 0
    for r, (u, v) in matches(db):
        try:
            raw = get(v['thumb']); im = Image.open(io.BytesIO(raw)).convert('RGB'); im.thumbnail((480, 720))
            base = re.sub(r'[^a-z0-9]+', '-', r['name'].lower()).strip('-')
            card = os.path.join(OUT, base + '.webp'); th = os.path.join(OUT, base + '_thumb.webp')
            im.save(card, 'WEBP', quality=82, method=4); t = im.copy(); t.thumbnail((160, 240)); t.save(th, 'WEBP', quality=78, method=4)
            db.execute('UPDATE images SET is_selected=0 WHERE character_id=?', (r['id'],))
            db.execute('INSERT INTO images(character_id,source,source_url,page_url,card_path,thumb_path,width,height,bytes,sha256,has_alpha,is_selected,status) VALUES(?,?,?,?,?,?,?,?,?,?,0,1,?)',
                       (r['id'], 'dc.com', v['thumb'], u, os.path.relpath(card, ROOT), os.path.relpath(th, ROOT), im.width, im.height, os.path.getsize(card), hashlib.sha256(raw).hexdigest(), 'lista'))
            ok += 1
        except Exception as e:
            print('falló', r['name'], str(e)[:80])
        time.sleep(0.2)
    db.commit(); print('fotos oficiales de DC bajadas:', ok)


if __name__ == '__main__':
    {'index': index, 'match': match, 'download': download}[sys.argv[1]]()
