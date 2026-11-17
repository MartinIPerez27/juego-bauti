# CATÁLOGO DE CHOQUE DE HÉROES

Base de datos: `data/choque_heroes.db` (SQLite). Esquema legible en `data/schema.sql`.
La base es la fuente de verdad. La hoja de cálculo original solo sirvió para el primer cargado (`tools/build_catalog.py`).

## Qué decidimos (versión 2)

**Estadísticas.** Quedan 11, todas de 0 a 100: agilidad, armadura, daño, velocidad, inteligencia, liderazgo, trabajo en equipo, factor miedo, poder especial, regeneración y sigilo.
- Salieron por ser casi iguales a otra: FUERZA (≈ resistencia 0,93 y daño 0,73), RESISTENCIA, TÁCTICA (≈ inteligencia 0,79) y AMENAZA (nota global que resumía a las demás). Los datos se conservan en la base, pero no cuentan (`stat_defs.active = 0`).
- VOLUNTAD se eliminó: la hoja la describía pero nunca tuvo datos.

**Poder.** Promedio ponderado de las 11 estadísticas (vista `v_power`), con un pequeño premio al pico:
`poder = 75 % promedio ponderado + 25 % promedio de las 3 mejores estadísticas`.
- Los pesos mezclan 50 % lo que valoraba la nota AMENAZA de la hoja (daño 25 %, inteligencia 13 %, miedo 11 %) y 50 % igualdad.
- Con esos pesos, el poder se parece más a la nota AMENAZA original (0,89 contra 0,76 con todas iguales).
- Los pesos y el premio están en `stat_defs.weight` y `balance_params.pico_peso`. Se pueden cambiar sin tocar código.

**Rareza.** Pirámide de colección: 35 % común, 28 % infrecuente, 20 % rara, 11 % épica, 6 % legendaria.
- Se calcula con 50 % poder y 50 % fama (`characters.fame`, de 1 a 6; 6 = ícono mundial como Batman o Spider-Man).
- Se recalcula sola cada vez que se suman personajes (`tools/catalog_lib.py`, `recompute_rarity`).

**Elementos.** Las 16 categorías de poder pasaron a 5: MAGIA, FUERZA, MENTE, TECNOLOGÍA y ENERGÍA, en un ciclo donde cada uno vence a 2 y pierde contra 2 (tabla `element_rules`, con la frase que explica cada una). Sirve para la batalla y para "Piedra, papel y tijera de poderes".
- La tabla `element_map` guarda cómo se convirtió cada categoría vieja. Revisala: es una decisión de diseño, por ejemplo fuego, agua, luz y radiación quedaron todas en ENERGÍA.
- 58 personajes sin poder especial claro no tienen elemento.

**Se eliminó:** reputación, debilidad (texto y categoría) y aliados. Se conserva una sola alineación (HEROE, VILLANO o NEUTRAL), que responde "¿es bueno o malo?" y define el color de la carta.

**Historias.** Se reescribieron con Gemini (450-600 caracteres, para un nene de 5 años). La original de la hoja queda en `story_short`. Verificá algunas: la IA puede equivocarse con personajes poco conocidos.

**Fotos.** No se usan las imágenes de la hoja. La tabla `images` está vacía y se llena con SuperHero API, ComicVine y Wikipedia. Consulta `v_sin_foto` para ver quién no tiene.

## Herramientas (`tools/`)

| Comando | Para qué |
|---|---|
| `python3 tools/missing_heroes.py list --publisher marvel` | Ver qué héroes faltan (SuperHero API) |
| `GEMINI_API_KEY=... python3 tools/missing_heroes.py add --id 96 --dry-run` | Probar el alta automática sin guardar |
| `GEMINI_API_KEY=... python3 tools/missing_heroes.py add --id 96 --id 278` | Sumar héroes con estadísticas generadas |
| `GEMINI_API_KEY=... python3 tools/enrich_gemini.py stories` | Reescribir historias (se puede reanudar) |

Los personajes nuevos quedan con `review_status = 'auto'` y la bandera `ESTADISTICAS_AUTOMATICAS` para que los revises. Las claves se leen del entorno y no se guardan en ningún archivo.

## Límites de Gemini (plan gratuito)
Cada modelo tiene un cupo diario propio y bajo (`gemini-2.5-flash`: 20 pedidos por día). Si se agota, el script lo avisa y se retoma otro día o con `--model`. Para generar voces de todo el catálogo conviene activar la facturación.
