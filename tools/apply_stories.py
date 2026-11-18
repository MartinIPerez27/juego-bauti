#!/usr/bin/env python3
"""Carga las historias escritas a mano (data/stories/batch*.txt, formato id|texto) en la base.
Rechaza las que no tengan entre 350 y 560 caracteres y marca como 'poco segura' las de personajes poco conocidos (data/stories/dudosas.txt)."""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ROOT, connect

db = connect(); n = 0; fuera = []
for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'stories', 'batch*.txt'))):
    for ln in open(f, encoding='utf8'):
        ln = ln.strip()
        if not ln or ln.startswith('#'): continue
        cid, txt = ln.split('|', 1); cid = int(cid)
        if not 350 <= len(txt) <= 560: fuera.append((cid, len(txt))); continue      # no se aplica lo que no cumple el largo
        db.execute("UPDATE characters SET story=?, story_source='claude' WHERE id=?", (txt, cid)); n += 1
dud = os.path.join(ROOT, 'data', 'stories', 'dudosas.txt')
db.execute("DELETE FROM review_flags WHERE code='HISTORIA_POCO_SEGURA'")
if os.path.exists(dud):
    for ln in open(dud, encoding='utf8'):
        ln = ln.split('#')[0].strip()
        for x in ln.replace(',', ' ').split():
            db.execute("INSERT INTO review_flags(character_id,code,severity,detail) VALUES(?,?,?,?)", (int(x), 'HISTORIA_POCO_SEGURA', 'media', 'Personaje poco conocido: verificar la historia con una fuente'))
db.commit()
print('historias aplicadas:', n, '| rechazadas por largo (fuera de 350-560):', fuera)
print('por origen:', dict(db.execute('SELECT story_source, COUNT(*) FROM characters GROUP BY story_source').fetchall()))
