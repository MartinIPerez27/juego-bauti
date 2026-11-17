#!/usr/bin/env python3
"""Enriquece el catálogo con Gemini. Se puede interrumpir y volver a correr: salta lo que ya está hecho.

  GEMINI_API_KEY=... python3 tools/enrich_gemini.py stories [--limit N] [--workers 4]

stories: reescribe la historia de cada personaje en 4-5 oraciones (450-600 caracteres) para un nene de 5 años.
La historia original de la hoja queda en characters.story_short.
"""
import argparse, concurrent.futures as cf, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catalog_lib import QuotaExceeded, connect, gemini_json

PROMPT = """Sos un narrador de cuentos para un nene de 5 años que está empezando a aprender. Escribís en español rioplatense (vos, tené, mirá).
Para cada personaje de cómics de la lista, escribí una historia de 4 o 5 oraciones, entre 450 y 600 caracteres en total.
Reglas:
- Contá quién es (y si es una versión alternativa del personaje, decilo con palabras simples), de dónde viene y qué poder o habilidad lo hace único. Sumá un dato curioso SOLO si estás completamente seguro de que es verdadero y conocido; si no, omitilo.
- Usá solo lo que realmente sabés del personaje y del resumen que te doy. No inventes hechos, nombres, poderes ni anécdotas. Si sabés poco, escribí menos pero sin inventar.
- Palabras simples, tono cálido y de aventura. Nada de violencia explícita: los villanos "hacen maldades" o "causan problemas".
- Empezá directamente con el nombre o la descripción del personaje: nada de saludos, ni "había una vez", ni "te cuento", ni "mirá". Si un integrante del equipo es de piedra, decí "de piedra" y no uses jerga.
- Sin emojis, sin markdown, sin listas, sin comillas raras. Escribí en minúsculas y mayúsculas normales.
Devolvé SOLO un JSON: una lista con objetos {{"id": <número>, "story": "<texto>"}}, uno por personaje.

Personajes:
{items}
"""


def todo(db, limit):
    rows = db.execute("SELECT id,name,universe,story_short,special_ability FROM characters WHERE story_source IS NOT 'gemini' ORDER BY id").fetchall()
    return rows[:limit] if limit else rows


def run_batch(batch, model='gemini-3-flash-preview'):
    items = '\n'.join(f'- id {r["id"]}: {r["name"]} ({r["universe"]}). Resumen: {r["story_short"]}. Habilidad: {r["special_ability"]}' for r in batch)
    out = gemini_json(PROMPT.format(items=items), model=model, temperature=0.8)
    ok = {}
    for o in out if isinstance(out, list) else []:
        s = str(o.get('story', '')).strip()
        if 330 <= len(s) <= 760: ok[int(o['id'])] = s
    return ok


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('task', choices=['stories']); ap.add_argument('--limit', type=int); ap.add_argument('--workers', type=int, default=3); ap.add_argument('--model', default='gemini-3-flash-preview')
    a = ap.parse_args()
    db = connect(); rows = todo(db, a.limit)
    print('pendientes:', len(rows))
    batches = [rows[i:i + 8] for i in range(0, len(rows), 8)]
    done = 0
    def safe(b):
        try: return run_batch(b, a.model)
        except QuotaExceeded: return None
    stop = False
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for res in ex.map(safe, batches):
            if res is None: stop = True; continue
            for cid, s in res.items():
                db.execute("UPDATE characters SET story=?, story_source='gemini' WHERE id=?", (s, cid)); done += 1
            db.commit(); print(f'  guardadas {done}', flush=True)
    if stop: print('Se agotó la cuota diaria del modelo', a.model, '- seguí mañana o probá con --model gemini-3.1-flash-lite')
    left = db.execute("SELECT COUNT(*) FROM characters WHERE story_source IS NOT 'gemini'").fetchone()[0]
    print(f'listo. sin historia nueva: {left} (volvé a correr el comando para reintentar)')


if __name__ == '__main__':
    main()
