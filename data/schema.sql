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
