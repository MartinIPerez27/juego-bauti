#!/usr/bin/env python3
"""Calibra los TIER del modo ELEGÍ UNO simulando miles de partidas con el catálogo real.

Reglas simuladas: hay 6 estadísticas vacías. En cada tirada, la ruleta ofrece un personaje al azar por cada estadística libre.
El jugador se queda con UNA opción (esa estadística queda fija) y se vuelve a girar para las que siguen libres.
Estrategia simulada: se elige siempre la opción con mejor percentil (un jugador atento; un humano puede hacerlo apenas mejor o peor).
El TIER sale del percentil promedio de lo obtenido. S+ exige además que TODAS las estadísticas estén entre las mejores del catálogo.

  python3 tools/sim_elegi_uno.py [--n 200000] [--save]      (--save guarda los cortes en balance_params)
"""
import argparse, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import connect

STATS = ['inteligencia', 'fuerza', 'velocidad', 'aguante', 'poder', 'combate']
TIERS = ['D', 'C', 'B', 'A', 'S', 'S+']
SHARE = [0.20, 0.30, 0.25, 0.15, 0.08, None]   # reparto buscado de resultados (S+ = lo que sobra, se calibra aparte)
TARGET_SPLUS = 0.02                            # difícil: unas 2 de cada 100 partidas con buen juego


def percentiles(db):
    pct = {}
    for s in STATS:
        vals = sorted(r[0] for r in db.execute('SELECT value FROM character_stats WHERE stat_key=?', (s,)))
        n = len(vals)
        def mid(v):                       # percentil por rango medio (maneja los empates en 100)
            lo = sum(1 for x in vals if x < v); eq = sum(1 for x in vals if x == v)
            return (lo + eq / 2) / n
        pct[s] = {v: mid(v) for v in set(vals)}
    return pct


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--n', type=int, default=200000); ap.add_argument('--save', action='store_true')
    a = ap.parse_args(); db = connect(); rng = random.Random(7)
    pct = percentiles(db)
    ids = [r[0] for r in db.execute('SELECT id FROM characters')]
    val = {s: {} for s in STATS}
    for cid, s, v in db.execute('SELECT character_id,stat_key,value FROM character_stats'): val[s][cid] = v
    # "lo mejor de cada estadística": valor mínimo para estar entre el 15 % de arriba
    top = {}
    for s in STATS:
        vs = sorted(val[s].values()); top[s] = vs[int(len(vs) * 0.85)]
    res = []
    for _ in range(a.n):
        free = list(STATS); got = {}
        while free:
            opts = [(pct[s][val[s][rng.choice(ids)]], s) for s in free]
            p, s = max(opts, key=lambda t: t[0] + rng.random() * 1e-9)
            got[s] = p; free.remove(s)
        # guardamos percentil promedio y si todas las estadísticas están entre las mejores
        res.append((sum(got.values()) / 6, min(got.values())))
    res.sort(key=lambda t: t[0])
    n = len(res)
    avg = [r[0] for r in res]
    # cortes por cuantiles (de abajo hacia arriba)
    cuts = []; acc = 0.0
    for sh in SHARE[:-1]:
        acc += sh; cuts.append(avg[int(n * acc)])
    splus_cut = avg[int(n * (1 - TARGET_SPLUS))]
    cuts.append(splus_cut)
    print('Partidas simuladas:', n, '| estadísticas con valor "de élite" (top 15 %):', top)
    print('Percentil promedio: mediana %.2f  p90 %.2f  p98 %.2f  máx %.2f' % (avg[n // 2], avg[int(n * .9)], avg[int(n * .98)], avg[-1]))
    print('\nTIER  corte (percentil promedio ≥)   % de partidas')
    lows = [0.0] + cuts
    for i, t in enumerate(TIERS):
        lo = lows[i]; hi = lows[i + 1] if i + 1 < len(lows) else 1.01
        share = sum(1 for x in avg if lo <= x < hi) / n * 100
        print('%-4s  %.3f                         %5.1f %%' % (t, lo, share))
    # S+ exige además que ninguna estadística quede floja: percentil mínimo ≥ m
    for m in (0.0, 0.5, 0.7, 0.8, 0.9):
        ok = sum(1 for av, mn in res if av >= splus_cut and mn >= m) / n * 100
        print('S+ con piso por estadística %.1f: %.2f %%' % (m, ok))
    if a.save:
        db.executemany('INSERT OR REPLACE INTO balance_params VALUES(?,?,?)',
                       [('elegiuno_corte_' + t.lower().replace('+', 'mas'), round(c, 4), 'Percentil promedio mínimo para el TIER ' + t) for t, c in zip(TIERS[1:], cuts)])
        db.execute("INSERT OR REPLACE INTO balance_params VALUES('elegiuno_piso_splus',0.80,'Para S+ cada estadística debe estar en el 20 % mejor del catálogo (percentil mínimo)')")
        db.commit(); print('\nCortes guardados en balance_params (elegiuno_corte_*, elegiuno_piso_splus).')


if __name__ == '__main__':
    main()
