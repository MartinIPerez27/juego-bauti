CREATE VIEW v_arena_score AS
      SELECT cs.character_id, a.key AS arena,
             ROUND((SUM(cs.value*d.weight) + SUM(CASE WHEN cs.stat_key IN (a.stat_a,a.stat_b) THEN cs.value*d.weight*(p.value-1) ELSE 0 END))
                   / (SUM(d.weight) + SUM(CASE WHEN cs.stat_key IN (a.stat_a,a.stat_b) THEN d.weight*(p.value-1) ELSE 0 END)), 1) AS score
      FROM character_stats cs JOIN stat_defs d ON d.key=cs.stat_key
      CROSS JOIN arenas a JOIN balance_params p ON p.key='arena_multiplicador'
      GROUP BY cs.character_id, a.key;
CREATE VIEW v_power AS
SELECT c.id AS character_id, c.name, ROUND(SUM(cs.value*d.weight)/SUM(d.weight), 1) AS power
FROM characters c JOIN character_stats cs ON cs.character_id=c.id JOIN stat_defs d ON d.key=cs.stat_key
GROUP BY c.id;
CREATE VIEW v_sin_elemento AS SELECT id, name FROM characters WHERE power_element IS NULL;
CREATE VIEW v_sin_foto AS SELECT c.id, c.name FROM characters c
                  WHERE NOT EXISTS (SELECT 1 FROM images i WHERE i.character_id=c.id AND i.is_selected=1);
CREATE TABLE arenas(key TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT,
        stat_a TEXT NOT NULL REFERENCES stat_defs(key), stat_b TEXT NOT NULL REFERENCES stat_defs(key));
CREATE TABLE balance_params(key TEXT PRIMARY KEY, value REAL NOT NULL, note TEXT);
CREATE TABLE character_stats(
        character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        stat_key TEXT NOT NULL REFERENCES stat_defs(key), value REAL NOT NULL, PRIMARY KEY(character_id, stat_key));
CREATE TABLE "characters"(
        id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, universe TEXT,
        rarity TEXT REFERENCES rarities(key), fame INTEGER,           -- fama 1-5 (de la rareza original de la hoja)
        alignment TEXT,                                               -- HEROE | VILLANO | NEUTRAL (responde "¿es bueno o malo?")
        story TEXT, story_short TEXT, story_source TEXT,
        special_ability TEXT, power_element TEXT REFERENCES elements(key), reach TEXT,
        review_status TEXT NOT NULL DEFAULT 'pendiente');
CREATE TABLE element_rules(
        attacker_element TEXT NOT NULL REFERENCES elements(key), defender_element TEXT NOT NULL REFERENCES elements(key),
        attacker_bonus REAL NOT NULL DEFAULT 0.05, defender_penalty REAL NOT NULL DEFAULT 0.03, reason TEXT,
        PRIMARY KEY(attacker_element, defender_element));
CREATE TABLE elements(key TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT);
CREATE TABLE images(
  id INTEGER PRIMARY KEY, character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  source TEXT NOT NULL,            -- 'superhero_api' | 'comicvine' | 'wikipedia' | ...
  source_url TEXT NOT NULL, page_url TEXT, card_path TEXT, thumb_path TEXT,
  width INTEGER, height INTEGER, bytes INTEGER, sha256 TEXT, has_alpha INTEGER,
  is_selected INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'candidata');
CREATE TABLE "legacy_character_stats"(
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  stat_key TEXT NOT NULL REFERENCES "legacy_stat_defs"(key), value REAL NOT NULL,
  PRIMARY KEY(character_id, stat_key));
CREATE TABLE "legacy_stat_defs"(
  key TEXT PRIMARY KEY, label TEXT NOT NULL, grp TEXT, description TEXT,
  weight REAL NOT NULL DEFAULT 1,      -- peso dentro del promedio de poder
  in_power INTEGER NOT NULL DEFAULT 1, -- 1 = entra en el promedio de poder
  active INTEGER NOT NULL DEFAULT 1, retired_reason TEXT);
CREATE TABLE rarities(key TEXT PRIMARY KEY, rank INTEGER NOT NULL);
CREATE TABLE review_flags(
  id INTEGER PRIMARY KEY, character_id INTEGER REFERENCES characters(id), code TEXT NOT NULL,
  severity TEXT NOT NULL, detail TEXT, resolved INTEGER NOT NULL DEFAULT 0);
CREATE TABLE stat_defs(key TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT, weight REAL NOT NULL DEFAULT 1);
