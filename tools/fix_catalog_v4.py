#!/usr/bin/env python3
"""Correcciones pedidas tras probar el prototipo 2 (se puede volver a correr sin riesgo).

- Saca los grupos (4 Fantásticos, Hombre Hormiga y Mujer Avispa): cada personaje va individual.
- Corrige nombres: Wanda Maximoff, Kamala Khan, Magneto Dinastía X, Peni Parker y erratas.
- Descarta fotos incorrectas y la foto repetida de Super-Adaptoid.
- Saca de las historias la presentación con el nombre ("Hulk es el doctor..." -> "Es el doctor...").
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ROOT, connect, trim_name_intro

RENAME = {'BRUJA ESCARLATA': 'WANDA MAXIMOFF', 'MS MARVEL': 'KAMALA KHAN', 'MAGNETO - TRAJE BLANCO': 'MAGNETO DINASTÍA X',
          'PENI PARKER Y SPDR': 'PENI PARKER', 'IRON MAN (SORCECER SUPREME)': 'IRON MAN HECHICERO SUPREMO',
          'SOLDADO DE INVERNO': 'SOLDADO DE INVIERNO', 'PSYCKO-PIRATE': 'PSYCHO-PIRATE', 'GOD EMPEROR DOOM': 'DOCTOR DOOM EMPERADOR'}
GROUPS = ['4 FANTASTICOS', 'HOMBRE HORMIGA Y MUJER AVISPA']
BAD_PHOTOS = ['BABYPOOL', 'BOOSTER GOLD', 'DARKEST KNIGHT', 'BEETLE', 'FLASH', 'HYDROMAN', 'SUPER-ADAPTOID']


def main():
    db = connect()
    for old, new in RENAME.items():
        db.execute('UPDATE characters SET name=? WHERE name=?', (new, old))
    for g in GROUPS:
        r = db.execute('SELECT id FROM characters WHERE name=?', (g,)).fetchone()
        if not r: continue
        cid = r['id']
        for im in db.execute('SELECT card_path,thumb_path FROM images WHERE character_id=?', (cid,)).fetchall():
            for f in (im['card_path'], im['thumb_path']):
                if f and os.path.exists(os.path.join(ROOT, f)): os.remove(os.path.join(ROOT, f))
        for t in ('images', 'character_stats', 'review_flags'): db.execute(f'DELETE FROM {t} WHERE character_id=?', (cid,))
        db.execute('DELETE FROM characters WHERE id=?', (cid,))
    for n in BAD_PHOTOS:
        r = db.execute('SELECT id FROM characters WHERE name=?', (n,)).fetchone()
        if not r: continue
        for im in db.execute('SELECT id,card_path,thumb_path FROM images WHERE character_id=? AND is_selected=1', (r['id'],)).fetchall():
            for f in (im['card_path'], im['thumb_path']):
                if f and os.path.exists(os.path.join(ROOT, f)): os.remove(os.path.join(ROOT, f))
            db.execute("UPDATE images SET status='rechazada', is_selected=0, card_path=NULL, thumb_path=NULL WHERE id=?", (im['id'],))
    n = 0
    for r in db.execute('SELECT id,story FROM characters').fetchall():
        t = trim_name_intro(r['story'])
        if t != r['story']: db.execute('UPDATE characters SET story=? WHERE id=?', (t, r['id'])); n += 1
    db.commit()
    print('historias sin la presentación del nombre:', n, '| personajes:', db.execute('SELECT COUNT(*) FROM characters').fetchone()[0])


if __name__ == '__main__':
    main()
