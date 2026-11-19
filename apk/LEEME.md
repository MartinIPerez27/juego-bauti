# APK de CHOQUE DE HÉROES (versión de prueba)

`dist/ChoqueDeHeroes.apk` es el juego completo (menú, los 5 modos, biblioteca, 841 personajes con foto) dentro de una app Android. Funciona **sin internet**: las fotos y las tipografías están dentro. Está pensada para tablets en horizontal.

## Cómo instalarla
1. Pasá el archivo a la tablet (cable, Drive, mail o WhatsApp).
2. Abrilo desde el administrador de archivos. Android va a pedir permiso para "instalar apps de orígenes desconocidos" para esa app: permitilo.
3. Tocá **Instalar** y después **Abrir**.

## Para volver a armarla (cuando cambie el catálogo o el juego)
```bash
bash apk/build.sh
```
Baja el SDK de Android la primera vez, exporta el prototipo con todas las fotos y compila. Resultado en `apk/dist/ChoqueDeHeroes.apk`.

## Detalles
- Es una APK de prueba firmada con la clave de depuración. Sirve para instalar a mano; para publicarla en Play Store habría que firmarla con una clave propia.
- El botón "atrás" abre el "¿SALIR DE LA PARTIDA?" del juego, así no se cierra la app sin querer.
- La voz usa el narrador del sistema (Google Text-to-Speech). Si la tablet no tiene voces en español, se instala desde Ajustes > Idioma > Salida de texto a voz.
- La versión final en Flutter con voces grabadas con IA sigue pendiente (ver `PLAN.md`).
