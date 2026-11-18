#!/usr/bin/env python3
"""Suma héroes nuevos al catálogo desde data/newheroes/batch*.txt (todo lo hace Claude con la rúbrica de data/RUBRICA.md).

Formato por línea: NOMBRE|U(M/D)|ALINEACIÓN(H/V/N)|ALCANCE|HABILIDAD|INT,FUE,VEL,AGU,POD,COM|ELEMENTO(M/F/N/T/E)|FAMA|HISTORIA
Valida todo (rangos, múltiplos de 5, largo de la historia, nombre repetido), inserta los que faltan y recalcula la rareza de todo el catálogo.
Después hay que buscar sus fotos:  python3 tools/fetch_photos.py collect && pick && download
"""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ROOT, connect, norm, recompute_rarity, slug

KEYS = ['inteligencia', 'fuerza', 'velocidad', 'aguante', 'poder', 'combate']
UNI = {'M': 'MARVEL', 'D': 'DC'}
AL = {'H': 'HEROE', 'V': 'VILLANO', 'N': 'NEUTRAL'}
EL = {'M': 'MAGIA', 'F': 'FUERZA', 'N': 'MENTE', 'T': 'TECNOLOGIA', 'E': 'ENERGIA'}
REACH = {'CUERPO A CUERPO', 'CORTO', 'MEDIO', 'LARGO', 'GLOBAL'}


def main():
    db = connect(); have = {norm(r['name']) for r in db.execute('SELECT name FROM characters')}
    added, skipped, errors = [], [], []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'newheroes', 'batch*.txt'))):
        for n, ln in enumerate(open(f, encoding='utf8'), 1):
            ln = ln.strip()
            if not ln or ln.startswith('#'): continue
            try:
                name, u, a, reach, ab, st, el, fame, story = ln.split('|', 8)
                vals = [int(x) for x in st.split(',')]
                assert len(vals) == 6 and all(0 <= v <= 100 and v % 5 == 0 for v in vals), 'estadísticas'
                assert u in UNI and a in AL and el in EL and reach in REACH and 1 <= int(fame) <= 5, 'campos'
                assert 350 <= len(story) <= 560, f'historia de {len(story)} caracteres'
            except Exception as e:
                errors.append((os.path.basename(f), n, str(e))); continue
            if norm(name) in have: skipped.append(name); continue
            cid = (db.execute('SELECT MAX(id) FROM characters').fetchone()[0] or 0) + 1
            sl = slug(name)
            db.execute("""INSERT INTO characters(id,slug,name,universe,rarity,fame,alignment,story,story_short,story_source,special_ability,power_element,reach,review_status)
                          VALUES(?,?,?,?,'COMÚN',?,?,?,NULL,'claude',?,?,?,'nuevo')""",
                       (cid, sl, name, UNI[u], int(fame), AL[a], story, ab, EL[el], reach))
            db.executemany('INSERT INTO character_stats VALUES(?,?,?)', [(cid, k, float(v)) for k, v in zip(KEYS, vals)])
            db.execute("INSERT INTO review_flags(character_id,code,severity,detail) VALUES(?,?,?,?)",
                       (cid, 'HEROE_NUEVO', 'baja', 'Calificado por Claude con la rúbrica: revisar estadísticas, elemento e historia'))
            have.add(norm(name)); added.append(name)
    recompute_rarity(db); db.commit()
    print('agregados:', len(added), '| ya existían:', skipped, '| con error:', errors)
    print('total en el catálogo:', db.execute('SELECT COUNT(*) FROM characters').fetchone()[0])
    print('rareza:', dict(db.execute('SELECT rarity, COUNT(*) FROM characters GROUP BY rarity').fetchall()))
    print('sin elemento:', db.execute('SELECT COUNT(*) FROM v_sin_elemento').fetchone()[0])


if __name__ == '__main__':
    main()
