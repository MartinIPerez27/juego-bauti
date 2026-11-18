#!/usr/bin/env python3
"""Ver qué héroes y villanos faltan en el catálogo y sumarlos con estadísticas generadas automáticamente.

  python3 tools/missing_heroes.py list [--publisher marvel|dc|otros|todos] [--search TEXTO] [--limit 40] [--sort poder|nombre]
  GEMINI_API_KEY=... python3 tools/missing_heroes.py add NOMBRE [NOMBRE ...] [--dry-run]
  GEMINI_API_KEY=... python3 tools/missing_heroes.py add --id 620 --id 346 [--dry-run]

Fuente de candidatos: SuperHero API (731 personajes, gratis). Opcional: COMICVINE_API_KEY para sumar datos de ComicVine.
Los personajes agregados quedan con review_status='auto' y una bandera ESTADISTICAS_AUTOMATICAS para que los revises.
"""
import argparse, difflib, json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import ELEMENTS, ROOT, QuotaExceeded, connect, gemini_json, http_json, norm, recompute_rarity, slug

CACHE = os.path.join(ROOT, 'data', 'cache', 'superhero_api.json')
API_ALL = 'https://akabab.github.io/superhero-api/api/all.json'
STATS = ['agilidad', 'armadura', 'dano', 'velocidad', 'inteligencia', 'liderazgo', 'equipo', 'miedo', 'poder_especial', 'regeneracion', 'sigilo']
REACHES = ['CUERPO A CUERPO', 'CORTO', 'MEDIO', 'LARGO', 'GLOBAL']
ANCHORS = ['BABYPOOL', 'CAPITAN BOOMERANG', 'BATMAN', 'SPIDER-MAN', 'HULK', 'WOLVERINE', 'DOCTOR DOOM', 'SUPERMAN', 'THANOS', 'ODIN', 'THE PRESENCE']


def candidates():
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(http_json(API_ALL), open(CACHE, 'w'))
    return json.load(open(CACHE))


def publisher_kind(c):
    p = (c['biography'].get('publisher') or '').lower()
    return 'marvel' if 'marvel' in p else 'dc' if p.startswith('dc') or 'dc comics' in p else 'otros'


# nombres del catálogo en español -> como figuran en SuperHero API (para no listar como faltante lo que ya tenés)
ES_TO_EN = {
    '4 FANTASTICOS': 'Fantastic Four', 'CAPITAN AMERICA': 'Captain America', 'CAPITAN BOOMERANG': 'Captain Boomerang',
    'CAPITAN FRIO': 'Captain Cold', 'CAPITAN UNIVERSO': 'Captain Universe', 'CAPITANA MARVEL': 'Captain Marvel', 'CANARIO NEGRO': 'Black Canary',
    'CHICA ARDILLA': 'Squirrel Girl', 'CRANEO ROJO': 'Red Skull', 'DUENDE ROJO': 'Red Goblin', 'DUENDE VERDE': 'Green Goblin',
    'EL AVISPON VERDE': 'Green Hornet', 'LA COSA DEL PANTANO': 'Swamp Thing', 'FLECHA VERDE': 'Green Arrow', 'GATA NEGRA': 'Black Cat',
    'HOMBRE ABSORVENTE': 'Absorbing Man', 'HOMBRE ANTORCHA': 'Human Torch', 'HOMBRE DE ARENA': 'Sandman', 'HOMBRE DE HIELO': 'Iceman',
    'HOMBRE MARAVILLA': 'Wonder Man', 'LINTERNA VERDE': 'Green Lantern', 'MUJER AVISPA': 'Wasp', 'MUJER INVISIBLE': 'Invisible Woman',
    'MUJER MARAVILLA': 'Wonder Woman', 'OMEGA ROJO': 'Omega Red', 'PANTERA NEGRA': 'Black Panther', 'RAYO NEGRO': 'Black Bolt',
    'SEÑOR FREEZE': 'Mister Freeze', 'SOLDADO DE INVERNO': 'Winter Soldier', 'TORMENTA': 'Storm', 'HULK ROJO': 'Red Hulk', 'SHE HULK ROJO': 'Red She-Hulk'}


def catalog_names(db):
    names = {norm(r['name']): r['name'] for r in db.execute('SELECT name FROM characters')}
    for es, en in ES_TO_EN.items():
        if norm(es) in names: names[norm(en)] = names[norm(es)]
    return names


def find_state(c, names):
    n = norm(c['name'])
    if n in names: return 'ya', names[n]
    close = difflib.get_close_matches(n, list(names), n=1, cutoff=0.86)
    return ('parecido', names[close[0]]) if close else ('falta', None)


def cmd_list(a):
    db = connect(); names = catalog_names(db); rows = []
    for c in candidates():
        if a.publisher != 'todos' and publisher_kind(c) != a.publisher: continue
        if a.search and a.search.lower() not in c['name'].lower(): continue
        st, other = find_state(c, names)
        if st == 'ya': continue
        ps = c['powerstats']; avg = sum(ps.values()) / 6
        rows.append((c['id'], c['name'], publisher_kind(c), (c['biography'].get('alignment') or '-'), avg, st, other))
    rows.sort(key=lambda r: -r[4] if a.sort == 'poder' else r[1].lower())
    print(f'Catálogo actual: {db.execute("SELECT COUNT(*) FROM characters").fetchone()[0]} personajes. Candidatos que faltan: {len(rows)} '
          f'(de {len(candidates())} en SuperHero API). Los nombres en español pueden aparecer como faltantes aunque ya los tengas.')
    print(f'{"id":>4}  {"nombre":28} {"editorial":8} {"alinea.":8} {"poder API":>9}  nota')
    for r in rows[:a.limit]:
        print(f'{r[0]:>4}  {r[1][:28]:28} {r[2]:8} {r[3][:8]:8} {r[4]:9.0f}  ' + (f'¿es "{r[6]}"?' if r[5] == 'parecido' else ''))
    if len(rows) > a.limit: print(f'... y {len(rows) - a.limit} más (usá --limit o --search)')


def anchors_text(db):
    out = []
    for n in ANCHORS:
        r = db.execute('SELECT id FROM characters WHERE name=?', (n,)).fetchone()
        if not r: continue
        st = {k: int(v) for k, v in db.execute('SELECT stat_key, value FROM character_stats WHERE character_id=?', (r['id'],)) if k in STATS}
        out.append(f'{n}: ' + json.dumps(st))
    return '\n'.join(out)


def facts(c):
    b, ps = c['biography'], c['powerstats']
    return (f'{c["name"]} | nombre real: {b.get("fullName")} | editorial: {b.get("publisher")} | alineación: {b.get("alignment")} | '
            f'primera aparición: {b.get("firstAppearance")} | ocupación: {c.get("work", {}).get("occupation")} | grupos: {c.get("connections", {}).get("groupAffiliation")} | '
            f'stats base de SuperHero API: {json.dumps(ps)}')


PROMPT = """Sos el diseñador de un juego de cartas de superhéroes para un nene de 5 años (español rioplatense). Tenés que crear la ficha de nuevos personajes con la MISMA escala que el catálogo existente.
Escala: cada estadística va de 0 a 100, en múltiplos de 5. Estas son estadísticas reales del catálogo, para que calibres (BABYPOOL es de los más débiles, THE PRESENCE de los más poderosos):
{anchors}
Significado: agilidad=reflejos y esquive; armadura=protección extra (trajes, escudos, piel dura); dano=cuánto daño causa por ataque; velocidad=qué tan rápido se mueve; inteligencia=capacidad mental; liderazgo=comanda equipos; equipo=qué bien trabaja con otros; miedo=el terror que genera; poder_especial=intensidad de sus poderes únicos (0-10 si no tiene); regeneracion=sana heridas (0-10 si no); sigilo=actuar sin ser visto.
Para cada personaje devolvé: stats (las 11 claves: {keys}), alignment (HEROE, VILLANO o NEUTRAL), power_element (uno de {elements}, o NINGUNA si no tiene un poder especial claro; MAGIA=hechizos y oscuridad, FUERZA=músculos y golpes, MENTE=cerebro y telepatía, TECNOLOGIA=máquinas y armaduras, ENERGIA=rayos, fuego, luz), reach (uno de {reaches}), special_ability (máximo 65 caracteres, en MAYÚSCULAS, describe su poder más característico), fame (1 a 5: qué tan famoso es para el público general; 5 = ícono mundial), story (4 o 5 oraciones, entre 450 y 600 caracteres, simple y cálida para un nene de 5 años, sin saludos ni "había una vez", sin violencia explícita; si es una versión alternativa decilo; no inventes hechos, nombres ni poderes; dato curioso solo si estás seguro de que es verdadero).
Sé coherente con el personaje real: usá lo que sabés de sus poderes y no te limites a copiar los stats base de la API (son imprecisos).
Devolvé SOLO un JSON: lista de objetos {{"id": <id>, "stats": {{...}}, "alignment": "...", "power_element": "...", "reach": "...", "special_ability": "...", "fame": N, "story": "..."}}.

Personajes nuevos:
{items}
"""


def comicvine_note(name):
    key = os.environ.get('COMICVINE_API_KEY')
    if not key: return ''
    try:
        q = urllib.parse.urlencode({'api_key': key, 'format': 'json', 'resources': 'character', 'query': name, 'limit': 3, 'field_list': 'name,publisher,deck'})
        for r in http_json('https://comicvine.gamespot.com/api/search/?' + q)['results']:
            if r.get('deck') and r['name'].lower() == name.lower(): return f' | ComicVine: {r["deck"][:300]}'
    except Exception:
        pass
    return ''


def validate(o):
    if not isinstance(o.get('stats'), dict): return None
    st = {}
    for k in STATS:
        v = o['stats'].get(k)
        if not isinstance(v, (int, float)): return None
        st[k] = max(0, min(100, int(round(v / 5.0) * 5)))
    al = str(o.get('alignment', '')).upper().replace('HÉROE', 'HEROE')
    if al not in ('HEROE', 'VILLANO', 'NEUTRAL'): return None
    el = str(o.get('power_element', '')).upper().replace('Í', 'I').replace('Ó', 'O')
    el = el if el in ELEMENTS else None
    reach = str(o.get('reach', '')).upper(); reach = reach if reach in REACHES else 'MEDIO'
    story = str(o.get('story', '')).strip()
    if not 330 <= len(story) <= 760: return None
    return dict(stats=st, alignment=al, power_element=el, reach=reach, special_ability=str(o.get('special_ability', ''))[:68].upper(),
                fame=max(1, min(5, int(o.get('fame', 3)))), story=story)


def cmd_add(a):
    db = connect(); names = catalog_names(db); pool = candidates(); chosen = []
    for i in a.id or []:
        c = next((x for x in pool if x['id'] == i), None)
        chosen.append(c) if c else print(f'No existe el id {i} en SuperHero API')
    for n in a.names:
        m = [x for x in pool if norm(x['name']) == norm(n)] or [x for x in pool if norm(n) in norm(x['name'])]
        if not m: print(f'No encontré "{n}" en SuperHero API. Probá con el nombre en inglés o buscalo con: list --search'); continue
        chosen.append(m[0])
    todo = []
    for c in chosen:
        st, other = find_state(c, names)
        if st == 'ya': print(f'{c["name"]}: ya está en el catálogo'); continue
        if st == 'parecido': print(f'{c["name"]}: ojo, se parece a "{other}" que ya está (se agrega igual)')
        todo.append(c)
    if not todo: return
    added = []
    for i in range(0, len(todo), 5):
        batch = todo[i:i + 5]
        items = '\n'.join(f'- id {c["id"]}: {facts(c)}{comicvine_note(c["name"])}' for c in batch)
        try:
            out = gemini_json(PROMPT.format(anchors=anchors_text(db), keys=', '.join(STATS), elements=', '.join(ELEMENTS), reaches=', '.join(REACHES), items=items),
                              temperature=0.6)
        except QuotaExceeded:
            print('Se agotó la cuota diaria de Gemini. Probá de nuevo más tarde.'); break
        by = {int(o['id']): validate(o) for o in out if isinstance(o, dict) and 'id' in o}
        for c in batch:
            v = by.get(c['id'])
            if not v: print(f'{c["name"]}: Gemini devolvió datos inválidos, reintentá'); continue
            added.append((c, v))
    for c, v in added:
        name = re.sub(r'\s+', ' ', c['name']).upper()
        print(f'\n{name} [{publisher_kind(c)}] {v["alignment"]} / {v["power_element"]} / fama {v["fame"]}\n  stats: {v["stats"]}\n  habilidad: {v["special_ability"]}\n  historia: {v["story"][:140]}...')
        if a.dry_run: continue
        cid = (db.execute('SELECT MAX(id) FROM characters').fetchone()[0] or 0) + 1
        sl = slug(name); sl = sl if not db.execute('SELECT 1 FROM characters WHERE slug=?', (sl,)).fetchone() else f'{sl}-{c["id"]}'
        uni = {'marvel': 'MARVEL', 'dc': 'DC'}.get(publisher_kind(c), 'OTRO')
        db.execute("""INSERT INTO characters(id,slug,name,universe,rarity,fame,alignment,story,story_short,story_source,special_ability,power_element,reach,review_status)
                      VALUES(?,?,?,?,'COMÚN',?,?,?,?,?,?,?,?, 'auto')""",
                   (cid, sl, name, uni, v['fame'], v['alignment'], v['story'], None, 'gemini', v['special_ability'], v['power_element'], v['reach']))
        db.executemany('INSERT INTO character_stats VALUES(?,?,?)', [(cid, k, float(x)) for k, x in v['stats'].items()])
        db.execute("INSERT INTO review_flags(character_id,code,severity,detail) VALUES(?,?,?,?)",
                   (cid, 'ESTADISTICAS_AUTOMATICAS', 'media', 'Estadísticas, elemento e historia generadas por IA: revisar antes de jugar'))
        for u in (c['images'].get('lg'), c['images'].get('md')):
            if u: db.execute('INSERT INTO images(character_id,source,source_url,status) VALUES(?,?,?,?)', (cid, 'superhero_api', u, 'candidata')); break
    if added and not a.dry_run:
        recompute_rarity(db); db.commit()
        print('\nRareza recalculada para todo el catálogo (la pirámide se reparte con los personajes nuevos).')
        for c, v in added:
            r = db.execute('SELECT c.rarity, p.power FROM characters c JOIN v_power p ON p.character_id=c.id WHERE c.name=?', (re.sub(r"\s+", " ", c["name"]).upper(),)).fetchone()
            print(f'  {c["name"]}: poder {r["power"]}, rareza {r["rarity"]}')
    elif a.dry_run:
        print('\n(dry-run: no se guardó nada)')


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    l = sub.add_parser('list'); l.add_argument('--publisher', default='todos', choices=['marvel', 'dc', 'otros', 'todos'])
    l.add_argument('--search'); l.add_argument('--limit', type=int, default=40); l.add_argument('--sort', default='poder', choices=['poder', 'nombre'])
    d = sub.add_parser('add'); d.add_argument('names', nargs='*'); d.add_argument('--id', type=int, action='append'); d.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    cmd_list(a) if a.cmd == 'list' else cmd_add(a)


if __name__ == '__main__':
    main()
