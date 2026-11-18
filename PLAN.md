# PLAN POR FASES: LA BATALLA DE BAUTI (Flutter + Flame, APK para tablet)

El prototipo HTML (`prototipo/`) ya fija la sensación, el arte y las reglas. Este plan lo convierte en una app instalable. Cada fase termina con algo que se puede probar.

## Decisiones ya tomadas
- Solo digital, en tablet horizontal. Un nene de 4 años que no lee: voz, imágenes, botones enormes.
- Textos en español rioplatense y SIEMPRE en MAYÚSCULAS de imprenta.
- Mismo dispositivo: persona contra persona o contra la máquina. Sin online.
- Contenido dentro de la app (offline). Progreso guardado solo en el dispositivo.
- Arte real de los personajes, extraído una sola vez (SuperHero API, ComicVine, Wikipedia). Repo privado.
- El motor de reglas decide el ganador; la narración solo lo cuenta. Voces pregrabadas con IA neural.
- Modo principal: pares → equipos → batallas por rondas. Cartas dadas vuelta quedan a la vista, 2 cartas por turno siempre, el par se forma con cualquier carta visible.

## Fase 1. Catálogo de personajes (una sola extracción)
- Script que junta datos de SuperHero API, ComicVine y Wikipedia ES, con pedidos espaciados y caché.
- Catálogo con variantes (Rune King Thor, Batman Who Laughs, etc.): nombre, foto, estadísticas, etiquetas (vuela, magia, tecnología, cósmico, etc.) e historia corta.
- Historias reescritas para chicos con Gemini y revisadas por una persona.
- Fotos: dos tamaños en WebP, recorte vertical 2:3 y revisión manual de las que salgan mal. Se arma una página de revisión para aprobar o cambiar cada foto.
- Salida: `catalog.json` y carpeta de imágenes. Meta de tamaño: cabe en el APK (por ejemplo 300 cartas en menos de 30 MB).
- Aprobación: vos revisás el catálogo en la página de revisión.

## Fase 2. Motor de reglas (Dart puro, con tests)
- Pasar `evaluate()` del prototipo a Dart: poder base, sinergias, contraataques, empates.
- El resultado lleva la lista de razones, que alimenta la narración.
- Tests que garantizan que el mismo duelo siempre da el mismo ganador.
- Aprobación: tabla de duelos de ejemplo con sus razones, para que vos juzgues si son justos.

## Fase 3. Voz natural (opción 1)
- Banco de frases por razón, con variantes, y lista de nombres de personajes.
- Muestras de 3 o 4 voces de Gemini TTS; elegís una.
- Generación de todos los audios una sola vez y guardado en la app.
- Armador de narración que une clips (frase + nombre + frase) y usa la voz del dispositivo si falta un clip.
- Requiere `GEMINI_API_KEY` en el entorno.
- Aprobación: escuchás 5 batallas completas.

## Fase 4. Base de la app Flutter + Flame
- Proyecto, tema pop-art (colores, tipografías Bangers y Nunito), pantallas, botones grandes.
- Componente de carta con el diseño del prototipo (número en la franja, sin tapar el rostro).
- Sonidos de efectos, vibración y guardado local.
- Compilación del APK con GitHub Actions, porque el entorno de esta sesión puede no traer el SDK de Flutter.
- Aprobación: instalás el APK en la tablet y navegás título, menú y configuración.

## Fase 5. Modo principal completo
- Configuración: jugadores con nombre, pares, héroes por equipo, rondas.
- Memoria con tablero con scroll para catálogos grandes, regla de 2 cartas y animación del par hacia el jugador.
- Armado de equipos, batalla con voz y puntaje, pantalla final.
- Máquina que juega sola.
- Aprobación: partida completa con Bauti.

## Fase 6. Biblioteca y Draft
- Biblioteca con todas las cartas, estadísticas, historia y botón de escuchar.
- Draft: elegir cartas por turnos de un mazo común.

## Fase 7. Modos nuevos
Las reglas de todos los modos están en `data/MODOS.md`. Elegidos hasta ahora:
- PERSONAJE vs PERSONAJE: cada jugador arma un héroe con una ruleta que le ofrece cartas, y gana el mejor promedio.
- ELEGÍ UNO: modo individual con ruleta y TIER; solo se gana con S+ (muy difícil, calibrado con simulación).
- PIEDRA, PAPEL Y TIJERA DE PODERES.
- CARRERA DE HÉROES.
- EQUIPO PERFECTO.
- DESAFÍO DEL DÍA.

## Fase 8. Pulido y entrega
- Animaciones y sacudidas ajustadas, rendimiento en la tablet real, tamaños de botones, accesibilidad.
- Pruebas de errores comunes: sin sonido, cambio de orientación, partida interrumpida.
- APK firmado e instrucciones de instalación. Se mueve el código de la WebApp vieja a una carpeta aparte o se borra.

## Qué necesito de vos
1. Fase 1: tu revisión de las fotos del catálogo.
2. Fase 3: `GEMINI_API_KEY` en el entorno y elegir una de las voces de muestra.
3. Fase 7: qué modos nuevos querés.
4. Tamaño del catálogo que querés (¿100, 300, más?).
5. Un nombre definitivo para la app.

## Riesgos
- **Fotos y datos de variantes:** las APIs gratuitas fallan con las versiones poco conocidas. Se resuelve con revisión manual en la Fase 1.
- **Tamaño del APK:** un catálogo muy grande con audios puede pasar los 100 MB. Se resuelve con imágenes en WebP y audios en bitrate bajo.
- **Voz:** la calidad depende de la voz elegida y de lo bien que se unan los clips. Por eso se prueba con muestras antes de generar todo.
- **Sin SDK de Flutter en esta sesión:** la compilación del APK se hace en GitHub Actions o en tu computadora.
