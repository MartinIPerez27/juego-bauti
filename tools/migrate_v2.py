#!/usr/bin/env python3
"""Migración v2 del catálogo (una sola vez; se puede volver a correr sin riesgo).

Decisiones aplicadas:
- Estadísticas: salen las repetidas (FUERZA, RESISTENCIA, TACTICA) y AMENAZA (nota global derivada); se conservan
  los datos pero fuera del poder (active=0). Se elimina VOLUNTAD. Quedan 11, con pesos derivados.
- Se eliminan REPUTACIÓN, DEBILIDAD (texto y categoría) y ALIADOS.
- Poder elemental: 16 categorías -> 5 elementos con ciclo "A vence a B" (para batalla y Piedra, Papel y Tijera).
- Rareza: se recalcula como pirámide coleccionable (50% poder + 50% fama).
"""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import DB_PATH, ROOT, POWER_VIEW, connect, recompute_rarity

KEEP = ['agilidad', 'armadura', 'dano', 'velocidad', 'inteligencia', 'liderazgo', 'equipo', 'miedo', 'poder_especial', 'regeneracion', 'sigilo']
RETIRE = {
    'fuerza': 'Casi igual a RESISTENCIA (0,93) y a DAÑO (0,73)',
    'resistencia': 'Casi igual a FUERZA (0,93)',
    'tactica': 'Casi igual a INTELIGENCIA (0,79)',
    'amenaza': 'Es una nota global que resume a las demás; se usa solo para calibrar pesos',
}
ELEMENT_MAP = {'FISICO': 'FUERZA', 'MAGIA': 'MAGIA', 'OSCURIDAD': 'MAGIA', 'TECNOLOGIA': 'TECNOLOGIA', 'METAL': 'TECNOLOGIA',
               'MENTE': 'MENTE', 'LUZ': 'ENERGIA', 'ELECTRICIDAD': 'ENERGIA', 'RADIACION': 'ENERGIA', 'SONIDO': 'ENERGIA',
               'FUEGO': 'ENERGIA', 'AGUA': 'ENERGIA', 'FRIO': 'ENERGIA', 'VENENO': 'ENERGIA', 'KRYPTONITA': 'ENERGIA'}
ELEMENT_INFO = [
    ('MAGIA', 'MAGIA', 'Hechizos, magia y oscuridad'), ('FUERZA', 'FUERZA', 'Músculos y golpes'),
    ('MENTE', 'MENTE', 'Cerebro, telepatía y estrategia'), ('TECNOLOGIA', 'TECNOLOGÍA', 'Máquinas, armaduras e inventos'),
    ('ENERGIA', 'ENERGÍA', 'Rayos, fuego, luz y energía')]
# ciclo de 5: cada elemento vence a 2 y pierde contra 2
RULES = [
    ('MAGIA', 'FUERZA', 'LA MAGIA LE GANA A LA FUERZA BRUTA'), ('MAGIA', 'MENTE', 'LA MAGIA ENGAÑA A LA MENTE'),
    ('FUERZA', 'MENTE', 'UN GOLPE LLEGA ANTES QUE UN PLAN'), ('FUERZA', 'TECNOLOGIA', 'LA FUERZA ROMPE LAS MÁQUINAS'),
    ('MENTE', 'TECNOLOGIA', 'EL CEREBRO ENGAÑA A LAS MÁQUINAS'), ('MENTE', 'ENERGIA', 'LA MENTE CONTROLA LA ENERGÍA'),
    ('TECNOLOGIA', 'ENERGIA', 'LOS ESCUDOS FRENAN LA ENERGÍA'), ('TECNOLOGIA', 'MAGIA', 'LA CIENCIA VENCE A LA MAGIA'),
    ('ENERGIA', 'MAGIA', 'LA ENERGÍA ROMPE LOS HECHIZOS'), ('ENERGIA', 'FUERZA', 'LOS RAYOS SON MÁS RÁPIDOS QUE LOS GOLPES')]
QUOTAS = {'cuota_comun': .35, 'cuota_infrecuente': .28, 'cuota_rara': .20, 'cuota_epica': .11, 'cuota_legendaria': .06}


def derive_weights(db):
    """Pesos = mitad de lo que 'aprende' una regresión no negativa de AMENAZA + mitad igualdad."""
    import numpy as np
    def col(k): return np.array([r[0] for r in db.execute('SELECT value FROM character_stats WHERE stat_key=? ORDER BY character_id', (k,))])
    X = np.column_stack([col(k) for k in KEEP]); y = col('amenaza')
    A = np.column_stack([X, np.ones(len(X))]); act = list(range(len(KEEP)))
    while True:
        s = np.linalg.lstsq(A[:, act + [len(KEEP)]], y, rcond=None)[0]
        if (s[:-1] >= 0).all(): break
        act = [a for a, v in zip(act, s[:-1]) if v > 0]
    learn = np.zeros(len(KEEP)); learn[act] = s[:-1]; learn /= learn.sum()
    return {k: round(float(0.5 * l + 0.5 / len(KEEP)), 4) for k, l in zip(KEEP, learn)}


def main():
    db = connect()
    done = db.execute("SELECT value FROM balance_params WHERE key='schema_version'").fetchone()
    if done and done[0] >= 2:
        print('La base ya está en la versión 2.'); return
    shutil.copy(DB_PATH, DB_PATH + '.v1.bak')
    weights = derive_weights(db)
    db.commit(); db.execute('PRAGMA foreign_keys=OFF')
    db.executescript('DROP VIEW IF EXISTS v_power; DROP VIEW IF EXISTS v_sin_foto; DROP TABLE IF EXISTS allies; DROP TABLE IF EXISTS element_rules;')
    db.executescript("""
      DROP TABLE IF EXISTS elements;
      CREATE TABLE elements(key TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT);
      CREATE TABLE element_rules(
        attacker_element TEXT NOT NULL REFERENCES elements(key), defender_element TEXT NOT NULL REFERENCES elements(key),
        attacker_bonus REAL NOT NULL DEFAULT 0.05, defender_penalty REAL NOT NULL DEFAULT 0.03, reason TEXT,
        PRIMARY KEY(attacker_element, defender_element));
      CREATE TABLE element_map(old_key TEXT PRIMARY KEY, element TEXT REFERENCES elements(key));  -- trazabilidad de la migración
    """)
    db.executemany('INSERT INTO elements VALUES(?,?,?)', ELEMENT_INFO)
    db.executemany('INSERT INTO element_rules(attacker_element,defender_element,reason) VALUES(?,?,?)', RULES)
    db.executemany('INSERT INTO element_map VALUES(?,?)', list(ELEMENT_MAP.items()) + [('NINGUNA', None)])
    db.executescript("""
      CREATE TABLE characters_new(
        id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, universe TEXT,
        rarity TEXT REFERENCES rarities(key), fame INTEGER,           -- fama 1-5 (de la rareza original de la hoja)
        alignment TEXT,                                               -- HEROE | VILLANO | NEUTRAL (responde "¿es bueno o malo?")
        story TEXT, story_short TEXT, story_source TEXT,
        special_ability TEXT, power_element TEXT REFERENCES elements(key), reach TEXT,
        review_status TEXT NOT NULL DEFAULT 'pendiente');
      INSERT INTO characters_new(id,slug,name,universe,rarity,fame,alignment,story,story_short,story_source,special_ability,power_element,reach,review_status)
        SELECT c.id,c.slug,c.name,c.universe,c.rarity,(SELECT rank FROM rarities r WHERE r.key=c.rarity),c.alignment,
               c.story,c.story,'hoja_original',c.special_ability,
               (SELECT element FROM element_map m WHERE m.old_key=c.power_element),c.reach,c.review_status
        FROM characters c;
      DROP TABLE characters;
      ALTER TABLE characters_new RENAME TO characters;
      ALTER TABLE stat_defs ADD COLUMN retired_reason TEXT;
      DELETE FROM stat_defs WHERE key='voluntad';
    """)
    for k, why in RETIRE.items():
        db.execute('UPDATE stat_defs SET active=0, in_power=0, retired_reason=? WHERE key=?', (why, k))
    for k, w in weights.items():
        db.execute('UPDATE stat_defs SET weight=?, in_power=1, active=1 WHERE key=?', (w, k))
    db.execute("DELETE FROM review_flags WHERE code IN ('ALIADO_NO_ENCONTRADO','REPUTACION_INVALIDA','REPUTACION_MEZCLA','RAREZA_VS_PODER')")
    db.execute("DELETE FROM balance_params WHERE key IN ('bonus_aliados_por_par','bonus_aliados_max','bonus_reputacion_alto','penalizacion_reputacion')")
    db.execute("UPDATE balance_params SET note='Promedio ponderado de estadísticas activas + premio al pico (pico_peso)' WHERE key='poder_modo'")
    extra = [('pico_peso', .25, 'Parte del poder que sale del promedio de las 3 mejores estadísticas (premia a los especialistas)'),
             ('schema_version', 2, 'Versión del esquema')] + [(k, v, 'Cuota de la pirámide de rareza') for k, v in QUOTAS.items()]
    db.executemany('INSERT OR REPLACE INTO balance_params VALUES(?,?,?)', extra)
    db.executescript(POWER_VIEW)
    db.execute("""CREATE VIEW v_sin_foto AS SELECT c.id, c.name FROM characters c
                  WHERE NOT EXISTS (SELECT 1 FROM images i WHERE i.character_id=c.id AND i.is_selected=1)""")
    db.execute('PRAGMA foreign_keys=ON')
    for cid, in db.execute("SELECT id FROM characters WHERE alignment IS NULL").fetchall():
        db.execute("INSERT INTO review_flags(character_id,code,severity,detail) VALUES(?,?,?,?)", (cid, 'ALINEACION_FALTANTE', 'media', 'Falta definir si es héroe, villano o neutral'))
    res = recompute_rarity(db)
    db.commit()
    bad = db.execute('PRAGMA foreign_key_check').fetchall()
    with open(os.path.join(ROOT, 'data', 'schema.sql'), 'w', encoding='utf8') as f:
        f.write('\n'.join(r[0] + ';' for r in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name")) + '\n')
    print('pesos:', weights)
    print('rareza nueva:', dict(db.execute('SELECT rarity, COUNT(*) FROM characters GROUP BY rarity').fetchall()))
    print('elementos:', dict(db.execute('SELECT COALESCE(power_element,"(ninguno)"), COUNT(*) FROM characters GROUP BY power_element').fetchall()))
    print('integridad de claves foráneas:', 'ok' if not bad else bad)


if __name__ == '__main__':
    main()
