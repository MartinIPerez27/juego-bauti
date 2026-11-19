#!/usr/bin/env python3
"""Suma una foto que pasó el usuario (link de Google u otro sitio) a un personaje.

  python3 tools/add_photo.py ID_O_NOMBRE URL            # pasa a ser la foto principal
  python3 tools/add_photo.py ID_O_NOMBRE URL --extra    # se suma a la galería (no reemplaza la principal)
Se descarga una sola vez, se convierte a WebP (tarjeta 480x720 máx. y miniatura) y queda en data/images/.
"""
import argparse, hashlib, io, os, sys, urllib.request
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ROOT, connect, norm

OUT = os.path.join(ROOT, 'data', 'images')


def main():
    a = argparse.ArgumentParser(); a.add_argument('who'); a.add_argument('url'); a.add_argument('--extra', action='store_true')
    a = a.parse_args(); db = connect()
    r = db.execute('SELECT id,slug,name FROM characters WHERE id=?', (int(a.who),)).fetchone() if a.who.isdigit() else \
        next((x for x in db.execute('SELECT id,slug,name FROM characters') if norm(x['name']) == norm(a.who)), None)
    if not r: sys.exit('No encontré ese personaje')
    req = urllib.request.Request(a.url, headers={'User-Agent': 'Mozilla/5.0 choque-heroes-personal'})
    raw = urllib.request.urlopen(req, timeout=60).read()
    im = Image.open(io.BytesIO(raw)); alpha = im.mode in ('RGBA', 'LA', 'P') and 'transparency' in im.info or im.mode == 'RGBA'
    im = im.convert('RGBA' if alpha else 'RGB'); im.thumbnail((480, 720))
    n = db.execute('SELECT COUNT(*) FROM images WHERE character_id=? AND status="lista"', (r['id'],)).fetchone()[0]
    main_photo = not a.extra or n == 0
    base = r['slug'] if main_photo else f"{r['slug']}_g{n + 1}"
    card, th = os.path.join(OUT, base + '.webp'), os.path.join(OUT, base + '_thumb.webp')
    im.save(card, 'WEBP', quality=82, method=4); t = im.copy(); t.thumbnail((160, 240)); t.save(th, 'WEBP', quality=78, method=4)
    if main_photo:
        db.execute("UPDATE images SET is_selected=0, status=CASE WHEN status='lista' AND (card_path IS NULL OR card_path NOT LIKE '%_g%') THEN 'reemplazada' ELSE status END WHERE character_id=?", (r['id'],))
    db.execute('INSERT INTO images(character_id,source,source_url,card_path,thumb_path,width,height,bytes,sha256,has_alpha,is_selected,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
               (r['id'], 'usuario', a.url, os.path.relpath(card, ROOT), os.path.relpath(th, ROOT), im.width, im.height, os.path.getsize(card),
                hashlib.sha256(raw).hexdigest(), int(alpha), int(main_photo), 'lista'))
    db.commit(); print(f"OK {r['name']}: {'principal' if main_photo else 'galería'} {im.width}x{im.height}")


if __name__ == '__main__':
    main()
