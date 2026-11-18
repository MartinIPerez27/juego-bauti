# MODOS DE JUEGO DE CHOQUE DE HÉROES

Lista de todos los modos elegidos y sus reglas. Las constantes están en `balance_params` y se pueden cambiar sin tocar código.

| Modo | Jugadores | Estado |
|---|---|---|
| PARES Y BATALLA (modo principal) | 2 o más, o contra la máquina | Prototipo hecho; reglas en `PLAN.md` |
| BIBLIOTECA | 1 | Prototipo hecho |
| DRAFT | 2 o más | Pendiente |
| PERSONAJE vs PERSONAJE | 2 o más, o contra la máquina | Reglas abajo |
| ELEGÍ UNO | 1 | Reglas abajo, TIER calibrados |
| PIEDRA, PAPEL Y TIJERA DE PODERES | 2 | Elementos listos (`element_rules`) |
| CARRERA DE HÉROES | 2 o más | Pendiente |
| EQUIPO PERFECTO | 1 o 2 | Pendiente |
| DESAFÍO DEL DÍA | 1 | Pendiente |

## Regla general de la batalla por equipos
Competir en una arena favorable **no alcanza para ganar**. El puntaje de un equipo es la suma de lo que rinde cada integrante en esa arena. Las 2 estadísticas de la arena pesan 3 veces, pero las otras 4 siguen contando. Comprobado: el equipo de Hulk, Hombre Hormiga y Batman pierde en las 8 arenas contra Doom Emperador, Galactus y Fénix. En "Ciudad en ruinas", que favorece a Hulk, el resultado es 181,5 contra 281.

## PERSONAJE vs PERSONAJE
Cada jugador arma un héroe con 6 espacios vacíos: inteligencia, fuerza, velocidad, aguante, poder y combate.
1. Antes de empezar se define la cantidad de rondas y quiénes juegan (personas o máquina).
2. En cada turno, el jugador gira la ruleta y le toca una carta al azar del catálogo.
3. Ve las estadísticas de esa carta y elige **una** de ellas, entre las que todavía tiene vacías. Se queda con ese valor en ese espacio.
4. Se repite hasta completar los 6 espacios. Cada jugador gira su propia ruleta y le tocan cartas distintas.
5. Gana la ronda el héroe con mejor **poder general**, que es el promedio de sus 6 estadísticas.
6. Después de todas las rondas gana quien más rondas ganó.

Supuestos que tomé y se pueden cambiar:
- Cada espacio solo se llena con la misma estadística (la fuerza de una carta va al espacio de fuerza).
- Si hay empate en una ronda, los dos suman un punto.
- La máquina elige siempre la mejor opción disponible.

## ELEGÍ UNO (modo individual)
1. Hay 6 espacios vacíos.
2. En cada tirada, la ruleta ofrece **una carta distinta por cada espacio libre**, mostrando su valor en esa estadística.
3. El jugador se queda con **una sola opción**. Ese espacio queda fijo.
4. Se vuelve a girar solo para los espacios que siguen libres, hasta completar los 6.
5. Al final, el héroe formado recibe un TIER: D, C, B, A, S o S+.
6. **Solo se gana con S+.** Si no se logra, se pierde y se puede reintentar.

**TIER.** Se calcula con el percentil promedio de lo obtenido dentro del catálogo (el percentil dice qué tan arriba está un valor respecto de todas las cartas). Cortes calibrados con 100.000 partidas simuladas, eligiendo siempre la mejor opción:

| TIER | Percentil promedio mínimo | Aprox. de las partidas |
|---|---|---|
| D | menos de 0,665 | 20 % |
| C | 0,665 | 30 % |
| B | 0,736 | 25 % |
| A | 0,791 | 15 % |
| S | 0,838 | 8 % |
| S+ | 0,887 **y** las 6 estadísticas entre el 20 % mejor del catálogo | **unos 0,9 %** (1 de cada ~115) |

**Qué hace difícil al S+.** Hay que conseguir lo mejor de **cada** estadística. Con el catálogo actual, "entre lo mejor" significa, como mínimo, valores de inteligencia 90, fuerza 95, velocidad 80, aguante 95, poder 95 y combate 90. Ninguna estadística floja se compensa con otra.

Para que sea más fácil o más difícil se cambia el piso de S+ (`elegiuno_piso_splus`: 0,8 es "el 20 % mejor"; 0,9 lo deja en 1 de cada ~1.250). Los cortes se recalculan con `python3 tools/sim_elegi_uno.py --save` cuando crezca el catálogo.

## Preguntas abiertas
1. PERSONAJE vs PERSONAJE: ¿cada jugador gira su propia ruleta y le tocan cartas distintas? (Lo asumí así.)
2. PERSONAJE vs PERSONAJE: ¿el empate da un punto a cada uno?
3. ELEGÍ UNO: ¿el piso de S+ en "el 20 % mejor" (≈ 1 de cada 115) te parece bien de difícil?
