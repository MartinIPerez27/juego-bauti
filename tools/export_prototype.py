#!/usr/bin/env python3
"""Exporta el catálogo para el prototipo web: prototipo2/data.js e imágenes (solo la versión de carta).

  python3 tools/export_prototype.py
"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ROOT, connect

OUT = os.path.join(ROOT, 'prototipo2')
# La plataforma de prueba admite 511 archivos por versión: los personajes nuevos viajan juntos en pack.js (data URI)
FILES_MAX = 440  # cuántos personajes con foto van como archivo suelto; el resto viaja reducido dentro de pack*.js
KEYS = ['inteligencia', 'fuerza', 'velocidad', 'aguante', 'poder', 'combate']


def small(path):
    from PIL import Image
    import io
    im = Image.open(path).convert('RGB'); im.thumbnail((300, 450)); b = io.BytesIO(); im.save(b, 'WEBP', quality=72, method=4); return b.getvalue()


def main():
    db = connect(); os.makedirs(os.path.join(OUT, 'img'), exist_ok=True)
    stats = {}
    for cid, k, v in db.execute('SELECT character_id,stat_key,value FROM character_stats'): stats.setdefault(cid, {})[k] = int(v)
    img = {r['character_id']: r['card_path'] for r in db.execute("SELECT character_id,card_path FROM images WHERE is_selected=1 AND status='lista'")}
    gal = {}
    for r in db.execute("SELECT character_id,card_path FROM images WHERE is_selected=0 AND status='lista' AND card_path IS NOT NULL ORDER BY id"):
        gal.setdefault(r['character_id'], []).append(r['card_path'])
    power = dict(db.execute('SELECT character_id,power FROM v_power'))
    chars = []; pack = {}
    file_ids = set(sorted(img)[:FILES_MAX])
    for r in db.execute('SELECT * FROM characters ORDER BY id'):
        st = stats[r['id']]; p = img.get(r['id']); fn = None
        if p and os.path.exists(os.path.join(ROOT, p)):
            fn = 'img/' + os.path.basename(p)
            if r['id'] in file_ids: shutil.copy(os.path.join(ROOT, p), os.path.join(OUT, fn))
            else: pack[fn] = p
        g = []
        for gp in gal.get(r['id'], []):
            if os.path.exists(os.path.join(ROOT, gp)):
                pack['img/' + os.path.basename(gp)] = gp; g.append('img/' + os.path.basename(gp))
        chars.append(dict(id=r['id'], n=r['name'], u=r['universe'], gal=g, al=r['alignment'], ra=r['rarity'], fa=r['fame'], el=r['power_element'],
                          ab=r['special_ability'], re=r['reach'], hi=r['story'], st=[st[k] for k in KEYS], pw=round(power[r['id']], 1), im=fn))
    params = {k: v for k, v in db.execute("SELECT key,value FROM balance_params WHERE key LIKE 'elegiuno%' OR key IN ('arena_multiplicador')")}
    data = dict(
        stats=[dict(k=r['key'], l=r['label']) for r in db.execute('SELECT key,label FROM stat_defs ORDER BY rowid')],
        arenas=[dict(k=r['key'], l=r['label'], d=r['description'], a=r['stat_a'], b=r['stat_b']) for r in db.execute('SELECT * FROM arenas')],
        elements=[dict(k=r['key'], l=r['label'], d=r['description']) for r in db.execute('SELECT * FROM elements')],
        rules=[dict(a=r['attacker_element'], d=r['defender_element'], t=r['reason'], b=r['attacker_bonus'], p=r['defender_penalty']) for r in db.execute('SELECT * FROM element_rules')],
        params=params, chars=chars)
    with open(os.path.join(OUT, 'data.js'), 'w', encoding='utf8') as f:
        f.write('const DATA=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')
    import base64
    # tres archivos (pack.js, pack2.js, pack3.js) para no pasar el máximo de 16 MB por archivo
    items = [(k, json.dumps(k) + ':"data:image/webp;base64,' + base64.b64encode(small(os.path.join(ROOT, v))).decode() + '"') for k, v in sorted(pack.items())]
    total = sum(len(t) for _, t in items); parts = [[], [], []]; acc = 0
    for k, t in items:
        n = min(2, int(acc / (total / 3 + 1))); parts[n].append(t); acc += len(t)
    for n, name in enumerate(['pack.js', 'pack2.js', 'pack3.js']):
        with open(os.path.join(OUT, name), 'w', encoding='utf8') as f:
            f.write('window.PACK=window.PACK||{};Object.assign(PACK,{' + ','.join(parts[n]) + '});\n')
    print('en packs:', len(pack), '| MB: %.1f' % (total / 1e6))
    print('personajes:', len(chars), '| con foto:', sum(1 for c in chars if c['im']), '| tamaño data.js: %d KB' % (os.path.getsize(os.path.join(OUT, 'data.js')) // 1024))
    print('imágenes MB: %.1f' % (sum(os.path.getsize(os.path.join(OUT, 'img', f)) for f in os.listdir(os.path.join(OUT, 'img'))) / 1e6))


if __name__ == '__main__':
    main()
