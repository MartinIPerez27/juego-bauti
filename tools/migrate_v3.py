#!/usr/bin/env python3
"""Migración v3: estadísticas nuevas (rúbrica en data/RUBRICA.md), arenas, elementos obligatorios.

- Los números de la hoja original se archivan en legacy_character_stats / legacy_stat_defs (solo referencia, no se usan).
- 6 estadísticas: inteligencia, fuerza, velocidad, aguante, poder, combate (0-100, múltiplos de 5).
- Las calificaciones salen de data/ratings/*.txt (formato: id|INT,FUE,VEL,AGU,POD,COM|elemento|fama).
- Cada pelea ocurre en una arena que duplica 2 estadísticas (tabla arenas, vista v_arena_score).
- Todas las cartas tienen elemento. Fama 1-5 reemplaza a la fama derivada de la hoja.
"""
import glob, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import DB_PATH, ROOT, POWER_VIEW, connect, recompute_rarity

STATS = [('inteligencia', 'INTELIGENCIA', 'Capacidad mental: ciencia, estrategia, ingenio.'),
         ('fuerza', 'FUERZA', 'Potencia física bruta: cuánto puede levantar, golpear o destruir.'),
         ('velocidad', 'VELOCIDAD', 'Qué tan rápido se mueve, corre, vuela o reacciona.'),
         ('aguante', 'AGUANTE', 'Cuánto daño soporta: resistencia, armadura y regeneración.'),
         ('poder', 'PODER', 'Poderes especiales: energía, magia, cosmos, telepatía.'),
         ('combate', 'COMBATE', 'Habilidad y entrenamiento para pelear.')]
EL = {'M': 'MAGIA', 'F': 'FUERZA', 'N': 'MENTE', 'T': 'TECNOLOGIA', 'E': 'ENERGIA'}
ARENAS = [  # clave, nombre para el nene, descripción, estadísticas que cuentan doble
    ('ciudad', 'CIUDAD EN RUINAS', 'Edificios que se caen: gana el más fuerte y duro.', 'fuerza', 'aguante'),
    ('castillo', 'CASTILLO HECHIZADO', 'Trampas y hechizos: gana el más listo y poderoso.', 'inteligencia', 'poder'),
    ('espacio', 'ESPACIO PROFUNDO', 'Estrellas y energía cósmica: gana el que más poder tiene.', 'poder', 'velocidad'),
    ('autopista', 'AUTOPISTA A TODA VELOCIDAD', 'Todo pasa volando: gana el más veloz y hábil.', 'velocidad', 'combate'),
    ('callejon', 'CALLEJÓN OSCURO', 'Poca luz y mucho ingenio: gana el que piensa y pelea mejor.', 'combate', 'inteligencia'),
    ('ring', 'RING DE LUCHA', 'Cuerpo a cuerpo: gana el más fuerte y que mejor pelea.', 'fuerza', 'combate'),
    ('volcan', 'VOLCÁN EN ERUPCIÓN', 'Lava y calor: gana el que más aguanta y más poder tiene.', 'aguante', 'poder'),
    ('laboratorio', 'LABORATORIO EN ALERTA', 'Máquinas y alarmas: gana el más listo y rápido.', 'inteligencia', 'velocidad')]


def load_ratings():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'ratings', 'batch*.txt'))):
        for ln in open(f, encoding='utf8'):
            ln = ln.strip()
            if not ln or ln.startswith('#'): continue
            cid, st, el, fame = ln.split('|')
            vals = [int(x) for x in st.split(',')]
            assert len(vals) == 6 and all(0 <= v <= 100 and v % 5 == 0 for v in vals), ln
            assert el in EL and 1 <= int(fame) <= 5, ln
            assert int(cid) not in out, 'id repetido ' + cid
            out[int(cid)] = (vals, EL[el], int(fame))
    return out


def main():
    db = connect()
    done = db.execute("SELECT value FROM balance_params WHERE key='schema_version'").fetchone()
    if done and done[0] >= 3:
        print('La base ya está en la versión 3.'); return
    ratings = load_ratings()
    ids = {r[0] for r in db.execute('SELECT id FROM characters')}
    miss = ids - set(ratings)
    if miss: raise SystemExit(f'Faltan calificaciones para ids: {sorted(miss)[:20]}')
    shutil.copy(DB_PATH, DB_PATH + '.v2.bak')
    db.executescript('DROP VIEW IF EXISTS v_power; DROP VIEW IF EXISTS v_arena_score;')
    db.executescript("""
      ALTER TABLE character_stats RENAME TO legacy_character_stats;
      ALTER TABLE stat_defs RENAME TO legacy_stat_defs;
      DROP TABLE IF EXISTS element_map;
      CREATE TABLE stat_defs(key TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT, weight REAL NOT NULL DEFAULT 1);
      CREATE TABLE character_stats(
        character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        stat_key TEXT NOT NULL REFERENCES stat_defs(key), value REAL NOT NULL, PRIMARY KEY(character_id, stat_key));
      CREATE TABLE arenas(key TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT,
        stat_a TEXT NOT NULL REFERENCES stat_defs(key), stat_b TEXT NOT NULL REFERENCES stat_defs(key));
      CREATE VIEW v_sin_elemento AS SELECT id, name FROM characters WHERE power_element IS NULL;
    """)
    db.executemany('INSERT INTO stat_defs(key,label,description) VALUES(?,?,?)', STATS)
    db.executemany('INSERT INTO arenas VALUES(?,?,?,?,?)', ARENAS)
    keys = [k for k, _, _ in STATS]
    for cid, (vals, el, fame) in ratings.items():
        db.executemany('INSERT INTO character_stats VALUES(?,?,?)', [(cid, k, float(v)) for k, v in zip(keys, vals)])
        db.execute('UPDATE characters SET power_element=?, fame=? WHERE id=?', (el, fame, cid))
    db.execute("DELETE FROM balance_params WHERE key IN ('pico_peso','poder_modo','bonus_liderazgo_umbral','bonus_liderazgo_cantidad','bonus_liderazgo_valor')")
    db.executemany('INSERT OR REPLACE INTO balance_params VALUES(?,?,?)', [
        ('arena_multiplicador', 3, 'Las 2 estadísticas de la arena cuentan este número de veces'),
        ('rareza_peso_fama', 0.7, 'Parte de la rareza que sale de la fama (el resto, del poder general)'),
        ('schema_version', 3, 'Versión del esquema')])
    db.executescript(POWER_VIEW)
    db.executescript("""
      CREATE VIEW v_arena_score AS
      SELECT cs.character_id, a.key AS arena,
             ROUND((SUM(cs.value*d.weight) + SUM(CASE WHEN cs.stat_key IN (a.stat_a,a.stat_b) THEN cs.value*d.weight*(p.value-1) ELSE 0 END))
                   / (SUM(d.weight) + SUM(CASE WHEN cs.stat_key IN (a.stat_a,a.stat_b) THEN d.weight*(p.value-1) ELSE 0 END)), 1) AS score
      FROM character_stats cs JOIN stat_defs d ON d.key=cs.stat_key
      CROSS JOIN arenas a JOIN balance_params p ON p.key='arena_multiplicador'
      GROUP BY cs.character_id, a.key;
    """)
    db.execute("DELETE FROM review_flags WHERE code='ESTADISTICAS_AUTOMATICAS'")
    recompute_rarity(db); db.commit()
    bad = db.execute('PRAGMA foreign_key_check').fetchall()
    with open(os.path.join(ROOT, 'data', 'schema.sql'), 'w', encoding='utf8') as f:
        f.write('\n'.join(r[0] + ';' for r in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name")) + '\n')
    print('personajes calificados:', len(ratings), '| sin elemento:', db.execute('SELECT COUNT(*) FROM v_sin_elemento').fetchone()[0])
    print('rareza:', dict(db.execute('SELECT rarity, COUNT(*) FROM characters GROUP BY rarity').fetchall()))
    print('elementos:', dict(db.execute('SELECT power_element, COUNT(*) FROM characters GROUP BY power_element').fetchall()))
    print('integridad:', 'ok' if not bad else bad)


if __name__ == '__main__':
    main()
