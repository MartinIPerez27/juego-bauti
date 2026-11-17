#!/usr/bin/env python3
"""Construye data/choque_heroes.db a partir de la hoja de cálculo original.

Uso:  python3 tools/build_catalog.py [--sheet-id ID] [--xlsx ruta.xlsx]
Requiere: openpyxl.
NO usa la columna IMAGEN de la hoja: las fotos se buscarán aparte en fuentes públicas gratuitas
(SuperHero API, ComicVine, Wikipedia) y se registrarán en la tabla `images`.
No contiene claves ni secretos.
"""
import argparse, os, re, sqlite3, unicodedata, urllib.request
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DEFAULT_SHEET = '1MJ5gdpePfesJKlRxoKDqX1jcQ04oxozHvccrAA8I5pE'
UA = {'User-Agent': 'choque-heroes-personal/0.1'}

# clave interna -> columna de la hoja BASE
STATS = {
    'agilidad': 'AGILIDAD', 'armadura': 'ARMADURA/DEFENSA', 'dano': 'DAÑO', 'fuerza': 'FUERZA',
    'resistencia': 'RESISTENCIA', 'velocidad': 'VELOCIDAD', 'amenaza': 'NIVEL_DE_AMENAZA',
    'inteligencia': 'INTELIGENCIA', 'liderazgo': 'LIDERAZGO', 'tactica': 'TACTICA',
    'equipo': 'TRABAJO_EN_EQUIPO', 'miedo': 'FACTOR_MIEDO', 'poder_especial': 'PODER_ESPECIAL',
    'regeneracion': 'REGENERACION', 'sigilo': 'SIGILO',
}
# grupo y etiqueta corta para cada estadística (la descripción sale de la pestaña ESTADISTICAS)
STAT_META = {
    'agilidad': ('COMBATE', 'AGILIDAD'), 'armadura': ('COMBATE', 'ARMADURA'), 'dano': ('COMBATE', 'DAÑO'),
    'fuerza': ('COMBATE', 'FUERZA'), 'resistencia': ('COMBATE', 'RESISTENCIA'), 'velocidad': ('COMBATE', 'VELOCIDAD'),
    'amenaza': ('INFO DE LA CARTA', 'AMENAZA'), 'inteligencia': ('MENTE Y LIDERAZGO', 'INTELIGENCIA'),
    'liderazgo': ('MENTE Y LIDERAZGO', 'LIDERAZGO'), 'tactica': ('MENTE Y LIDERAZGO', 'TÁCTICA'),
    'equipo': ('MENTE Y LIDERAZGO', 'TRABAJO EN EQUIPO'), 'miedo': ('PODERES Y VOLUNTAD', 'FACTOR MIEDO'),
    'poder_especial': ('PODERES Y VOLUNTAD', 'PODER ESPECIAL'), 'regeneracion': ('PODERES Y VOLUNTAD', 'REGENERACIÓN'),
    'sigilo': ('PODERES Y VOLUNTAD', 'SIGILO'),
}
RAREZAS = ['COMÚN', 'INFRECUENTE', 'RARA', 'ÉPICA', 'LEGENDARIA']
# parámetros del motor original (MotorBD.html) para no perderlos
PARAMS = [
    ('bonus_aliados_por_par', 0.15, 'Bono por cada par de aliados en el equipo'),
    ('bonus_aliados_max', 0.30, 'Tope del bono por aliados'),
    ('bonus_liderazgo_umbral', 80, 'Liderazgo mínimo para contar como líder'),
    ('bonus_liderazgo_cantidad', 3, 'Cantidad de líderes para activar el bono'),
    ('bonus_liderazgo_valor', 0.10, 'Valor del bono por liderazgo'),
    ('penalizacion_max', 0.15, 'Tope de penalización por debilidad elemental'),
    ('bonus_reputacion_alto', 0.08, 'Bono si la reputación promedio es alta'),
    ('penalizacion_reputacion', 0.05, 'Penalización si la reputación promedio es baja'),
    ('poder_modo', 0, '0 = promedio ponderado de estadísticas activas (ver stat_defs)'),
]
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE stat_defs(
  key TEXT PRIMARY KEY, label TEXT NOT NULL, grp TEXT, description TEXT,
  weight REAL NOT NULL DEFAULT 1,      -- peso dentro del promedio de poder
  in_power INTEGER NOT NULL DEFAULT 1, -- 1 = entra en el promedio de poder
  active INTEGER NOT NULL DEFAULT 1);  -- 0 = estadística retirada (se conservan los datos)
CREATE TABLE rarities(key TEXT PRIMARY KEY, rank INTEGER NOT NULL);
CREATE TABLE elements(key TEXT PRIMARY KEY, label TEXT);
CREATE TABLE characters(
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, universe TEXT,
  rarity TEXT REFERENCES rarities(key), reputation_raw TEXT, alignment TEXT,
  story TEXT, special_ability TEXT, weakness TEXT,
  power_element TEXT REFERENCES elements(key), weakness_element TEXT REFERENCES elements(key),
  reach TEXT, allies_raw TEXT, review_status TEXT NOT NULL DEFAULT 'pendiente');
CREATE TABLE character_stats(
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  stat_key TEXT NOT NULL REFERENCES stat_defs(key), value REAL NOT NULL,
  PRIMARY KEY(character_id, stat_key));
CREATE TABLE element_rules(
  attacker_element TEXT REFERENCES elements(key), defender_weakness TEXT REFERENCES elements(key),
  attacker_bonus REAL, defender_penalty REAL, PRIMARY KEY(attacker_element, defender_weakness));
CREATE TABLE allies(
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  ally_name_raw TEXT NOT NULL, ally_id INTEGER REFERENCES characters(id),
  PRIMARY KEY(character_id, ally_name_raw));
-- Fotos: varias candidatas por personaje, una elegida. Se llena con SuperHero API, ComicVine y Wikipedia.
CREATE TABLE images(
  id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  source TEXT NOT NULL,            -- 'superhero_api' | 'comicvine' | 'wikipedia' | ...
  source_url TEXT NOT NULL, page_url TEXT, card_path TEXT, thumb_path TEXT,
  width INTEGER, height INTEGER, bytes INTEGER, sha256 TEXT, has_alpha INTEGER,
  is_selected INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'candidata');
CREATE VIEW v_sin_foto AS
  SELECT c.id, c.name FROM characters c
  WHERE NOT EXISTS (SELECT 1 FROM images i WHERE i.character_id=c.id AND i.is_selected=1);
CREATE TABLE review_flags(
  id INTEGER PRIMARY KEY, character_id INTEGER REFERENCES characters(id), code TEXT NOT NULL,
  severity TEXT NOT NULL, detail TEXT, resolved INTEGER NOT NULL DEFAULT 0);
CREATE TABLE balance_params(key TEXT PRIMARY KEY, value REAL NOT NULL, note TEXT);
CREATE VIEW v_power AS
  SELECT c.id AS character_id, c.name,
         ROUND(SUM(cs.value*d.weight)/SUM(d.weight), 1) AS power
  FROM characters c JOIN character_stats cs ON cs.character_id=c.id
  JOIN stat_defs d ON d.key=cs.stat_key AND d.active=1 AND d.in_power=1
  GROUP BY c.id;
"""


def norm(s):
    s = unicodedata.normalize('NFD', str(s).upper()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Z0-9]', '', s)


def slug(s):
    s = unicodedata.normalize('NFD', str(s).lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet-id', default=DEFAULT_SHEET)
    ap.add_argument('--xlsx')
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    xlsx = a.xlsx or os.path.join(DATA, 'hoja_original.xlsx')
    if not a.xlsx:
        with urllib.request.urlopen(urllib.request.Request(
                f'https://docs.google.com/spreadsheets/d/{a.sheet_id}/export?format=xlsx', headers=UA), timeout=60) as r:
            open(xlsx, 'wb').write(r.read())
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    rows = list(wb['BASE'].iter_rows(values_only=True)); hdr = [str(h).strip() for h in rows[0]]
    base = [dict(zip(hdr, r)) for r in rows[1:] if r[0]]
    print('personajes:', len(base))

    db_path = os.path.join(DATA, 'choque_heroes.db')
    if os.path.exists(db_path): os.replace(db_path, db_path + '.bak')
    db = sqlite3.connect(db_path); db.executescript(SCHEMA)

    # definiciones de estadísticas: descripciones desde la pestaña ESTADISTICAS
    desc = {}
    for r in wb['ESTADISTICAS'].iter_rows(min_row=2, values_only=True):
        if r[0]: desc[norm(r[0])] = r[1]
    for k, col in STATS.items():
        g, lab = STAT_META[k]
        db.execute('INSERT INTO stat_defs(key,label,grp,description) VALUES(?,?,?,?)', (k, lab, g, desc.get(norm(col.replace('_', ' ')), desc.get(norm(lab)))))
    # la pestaña documenta VOLUNTAD/DETERMINACIÓN pero la hoja BASE no tiene esa columna
    db.execute("INSERT INTO stat_defs(key,label,grp,description,in_power,active) VALUES('voluntad','VOLUNTAD','PODERES Y VOLUNTAD',?,0,0)", (desc.get(norm('VOLUNTAD / DETERMINACIÓN')),))
    for i, r in enumerate(RAREZAS, 1): db.execute('INSERT INTO rarities VALUES(?,?)', (r, i))
    els = {d['PODER_ESPECIAL_CATEGORIA'] for d in base} | {d['DEBILIDAD_CATEGORIA'] for d in base}
    sin = [r for r in wb['SINERGIA'].iter_rows(min_row=2, values_only=True) if r[0]]
    els |= {r[0] for r in sin} | {r[1] for r in sin}
    for e in sorted(x for x in els if x): db.execute('INSERT INTO elements VALUES(?,?)', (e, e))
    for r in sin: db.execute('INSERT INTO element_rules VALUES(?,?,?,?)', r[:4])
    for p in PARAMS: db.execute('INSERT INTO balance_params VALUES(?,?,?)', p)

    ALIGN = {'HÉROE': 'HEROE', 'VILLANO': 'VILLANO', 'NEUTRAL': 'NEUTRAL'}
    ids, byname = {}, {}
    for n, d in enumerate(base, 1):
        sl = slug(d['PERSONAJE']); ids[sl] = n; byname[norm(d['PERSONAJE'])] = n
        rep = str(d['REPUTACIÓN']).strip()
        db.execute('INSERT INTO characters VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
            n, sl, d['PERSONAJE'], d['UNIVERSO'], d['RAREZA_DE_CARTA'], rep, ALIGN.get(rep), d['HISTORIA_BREVE'],
            d['HABILIDAD_ESPECIAL'], d['DEBILIDAD'], d['PODER_ESPECIAL_CATEGORIA'], d['DEBILIDAD_CATEGORIA'], d['ALCANCE'],
            d['ALIADOS_CLAVE'], 'pendiente'))
        for k, col in STATS.items(): db.execute('INSERT INTO character_stats VALUES(?,?,?)', (n, k, float(d[col])))

    # aliados: se intenta enlazar por nombre exacto normalizado
    unresolved = []
    for n, d in enumerate(base, 1):
        for x in str(d['ALIADOS_CLAVE']).split(','):
            x = x.strip()
            if not x or x == 'NINGUNO': continue
            aid = byname.get(norm(x))
            db.execute('INSERT OR IGNORE INTO allies VALUES(?,?,?)', (n, x, aid))
            if aid is None: unresolved.append((n, x))

    # banderas de revisión
    def flag(cid, code, sev, detail): db.execute('INSERT INTO review_flags(character_id,code,severity,detail) VALUES(?,?,?,?)', (cid, code, sev, detail))
    power = dict(db.execute('SELECT character_id, power FROM v_power'))
    rk = {r: i for i, r in enumerate(RAREZAS, 1)}
    for cid, rar, rep in db.execute('SELECT id, rarity, reputation_raw FROM characters'):
        if rep not in ('HÉROE', 'VILLANO', 'NEUTRAL', 'LEYENDA'): flag(cid, 'REPUTACION_INVALIDA', 'alta', f'Valor "{rep}" no es una reputación válida')
        if rep == 'LEYENDA': flag(cid, 'REPUTACION_MEZCLA', 'baja', 'LEYENDA mide fama, pero HÉROE/VILLANO/NEUTRAL miden alineación; falta saber si es héroe o villano')
        if rar == 'LEGENDARIA' and power[cid] < 55: flag(cid, 'RAREZA_VS_PODER', 'media', f'LEGENDARIA con poder {power[cid]}')
        if rar in ('COMÚN', 'INFRECUENTE') and power[cid] > 55: flag(cid, 'RAREZA_VS_PODER', 'media', f'{rar} con poder {power[cid]}')
    for cid, x in unresolved: flag(cid, 'ALIADO_NO_ENCONTRADO', 'baja', f'"{x}" no existe en el catálogo')
    db.commit()
    print('base creada:', db_path)
    for t in ('characters', 'character_stats', 'images', 'allies', 'review_flags', 'element_rules'):
        print(' ', t, db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])
    print('  banderas:', dict(db.execute('SELECT code||" ("||severity||")", COUNT(*) FROM review_flags GROUP BY code, severity')))
    with open(os.path.join(DATA, 'schema.sql'), 'w', encoding='utf8') as f: f.write(SCHEMA.strip() + '\n')


if __name__ == '__main__':
    main()
