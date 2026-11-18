# CATÁLOGO DE CHOQUE DE HÉROES (versión 3)

Base de datos: `data/choque_heroes.db` (SQLite). Esquema legible en `data/schema.sql`. La base es la fuente de verdad.
La hoja de cálculo original solo dio la lista de nombres y datos de texto. **Sus números de estadísticas no se usan**: quedaron archivados en `legacy_character_stats` solo como referencia.

## Cómo se decide quién gana

1. **6 estadísticas** de 0 a 100: INTELIGENCIA, FUERZA, VELOCIDAD, AGUANTE, PODER (energía, magia, cosmos) y COMBATE. La rúbrica está en `data/RUBRICA.md` y las calificaciones en `data/ratings/`.
2. **Arenas** (tabla `arenas`, vista `v_arena_score`): cada pelea ocurre en una arena que cuenta **3 veces** 2 estadísticas. Así nadie es "mejor" en todo: Hulk gana en la Ciudad en ruinas (fuerza y aguante), Doctor Doom en el Castillo hechizado (inteligencia y poder), Flash en la Autopista. Hay 8 arenas y el multiplicador se cambia en `balance_params.arena_multiplicador`.
3. **Elementos** (cada carta tiene uno): MAGIA, FUERZA, MENTE, TECNOLOGÍA y ENERGÍA, en un ciclo donde cada uno vence a 2 (`element_rules`). Sirve para un bono en la batalla y para "Piedra, papel y tijera de poderes".
4. **Poder general** (`v_power`): promedio de las 6 estadísticas. Da el "tamaño" de la carta y no decide la pelea.

## Rareza y fama
- Fama de 1 a 5 (`characters.fame`): 5 = ícono mundial. Se contrastará con las apariciones en cómics de ComicVine.
- Rareza en pirámide de colección: 35 % común, 28 % infrecuente, 20 % rara, 11 % épica, 6 % legendaria. Pesa 70 % la fama y 30 % el poder, y se recalcula al sumar personajes.

## Estado
| Qué | Estado |
|---|---|
| Personajes | 497: los 454 de la hoja y 43 nuevos (tanda 1 de `data/newheroes/`) |
| Estadísticas, elementos y fama | Hechos por Claude con la rúbrica; los 43 nuevos quedan marcados `HEROE_NUEVO` para revisar |
| Historias | Las 454 reescritas por Claude (350 a 470 caracteres); 89 marcadas `HISTORIA_POCO_SEGURA` (personajes poco conocidos) para verificar con una fuente |
| Fotos | 353 listas y revisadas a la vista; ~144 sin foto (`v_sin_foto`). Se descartaron las viñetas con globos, tapas con título y las equivocadas |
| Historias de los 43 nuevos | Escritas junto con el personaje |

## Cómo se suma un héroe
1. Agregar una línea en `data/newheroes/batchNN.txt` (nombre, estadísticas, elemento, fama, historia).
2. `python3 tools/apply_new_heroes.py` valida, inserta y recalcula la rareza de todo.
3. `python3 tools/fetch_photos.py collect && python3 tools/fetch_photos.py pick && python3 tools/fetch_photos.py download` busca su foto.

## Herramientas (`tools/`)
| Comando | Para qué |
|---|---|
| `python3 tools/fetch_photos.py collect / pick / download / status` | Buscar y bajar fotos de fuentes gratuitas (nunca de la hoja) |
| `python3 tools/fetch_photos.py reject ID ...` | Descartar una foto mala y buscar otra |
| `python3 tools/apply_new_heroes.py` | Sumar héroes nuevos desde `data/newheroes/` |
| `python3 tools/sim_elegi_uno.py --save` | Recalcular los TIER del modo ELEGÍ UNO |
| `python3 tools/apply_stories.py` | Cargar historias de `data/stories/` (rechaza las de largo fuera de rango) |
| `python3 tools/missing_heroes.py list --publisher marvel` | Ver qué héroes faltan |
| `python3 tools/migrate_v2.py` / `migrate_v3.py` | Migraciones ya aplicadas (no hace falta volver a correrlas) |

Las claves (ComicVine, Gemini) se leen del entorno y nunca se guardan en archivos. Las imágenes son de uso personal: no publicar el repo.
