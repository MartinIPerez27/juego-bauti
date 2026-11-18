#!/usr/bin/env python3
"""Suma todas las fotos de un CSV (columnas N;PERSONAJE;UNIVERSO;TIPO;LINK_FOTO). Salta las filas sin link y avisa las que fallan.

  python3 tools/add_photos_csv.py data/FALTAN_FOTOS.csv
"""
import csv, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
ok = bad = 0
for r in csv.DictReader(open(sys.argv[1], encoding='utf-8-sig'), delimiter=';'):
    link = (r.get('LINK_FOTO') or '').strip()
    if not link: continue
    p = subprocess.run([sys.executable, os.path.join(here, 'add_photo.py'), r['N'], link], capture_output=True, text=True)
    if p.returncode == 0: ok += 1; print(p.stdout.strip())
    else: bad += 1; print('FALLÓ', r['N'], r['PERSONAJE'], '->', (p.stderr.strip().splitlines() or ['error'])[-1][:120])
print(f'listas: {ok} | con error: {bad}')
