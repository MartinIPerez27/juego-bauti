CREATE VIEW v_power AS
WITH s AS (
  SELECT cs.character_id, cs.value, d.weight,
         ROW_NUMBER() OVER (PARTITION BY cs.character_id ORDER BY cs.value DESC) AS rn
  FROM character_stats cs JOIN stat_defs d ON d.key=cs.stat_key AND d.active=1 AND d.in_power=1),
a AS (
  SELECT character_id, SUM(value*weight)/SUM(weight) AS avg_w,
         AVG(CASE WHEN rn<=3 THEN value END) AS top3
  FROM s GROUP BY character_id)
SELECT c.id AS character_id, c.name,
       ROUND((1-p.value)*a.avg_w + p.value*a.top3, 1) AS power
FROM characters c JOIN a ON a.character_id=c.id
JOIN balance_params p ON p.key='pico_peso';
CREATE VIEW v_sin_foto AS SELECT c.id, c.name FROM characters c
                  WHERE NOT EXISTS (SELECT 1 FROM images i WHERE i.character_id=c.id AND i.is_selected=1);
CREATE TABLE balance_params(key TEXT PRIMARY KEY, value REAL NOT NULL, note TEXT);
CREATE TABLE character_stats(
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  stat_key TEXT NOT NULL REFERENCES stat_defs(key), value REAL NOT NULL,
  PRIMARY KEY(character_id, stat_key));
CREATE TABLE "characters"(
        id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, universe TEXT,
        rarity TEXT REFERENCES rarities(key), fame INTEGER,           -- fama 1-5 (de la rareza original de la hoja)
        alignment TEXT,                                               -- HEROE | VILLANO | NEUTRAL (responde "¿es bueno o malo?")
        story TEXT, story_short TEXT, story_source TEXT,
        special_ability TEXT, power_element TEXT REFERENCES elements(key), reach TEXT,
        review_status TEXT NOT NULL DEFAULT 'pendiente');
CREATE TABLE element_map(old_key TEXT PRIMARY KEY, element TEXT REFERENCES elements(key));
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
CREATE TABLE rarities(key TEXT PRIMARY KEY, rank INTEGER NOT NULL);
CREATE TABLE review_flags(
  id INTEGER PRIMARY KEY, character_id INTEGER REFERENCES characters(id), code TEXT NOT NULL,
  severity TEXT NOT NULL, detail TEXT, resolved INTEGER NOT NULL DEFAULT 0);
CREATE TABLE stat_defs(
  key TEXT PRIMARY KEY, label TEXT NOT NULL, grp TEXT, description TEXT,
  weight REAL NOT NULL DEFAULT 1,      -- peso dentro del promedio de poder
  in_power INTEGER NOT NULL DEFAULT 1, -- 1 = entra en el promedio de poder
  active INTEGER NOT NULL DEFAULT 1, retired_reason TEXT);
