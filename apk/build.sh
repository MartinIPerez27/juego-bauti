#!/usr/bin/env bash
# Arma la APK de prueba (debug) de CHOQUE DE HÉROES: la web del prototipo + todas las fotos, sin internet.
# Requisitos: Java 17+, Gradle 8.7+, Python 3 con Pillow, y el SDK de Android (se baja solo la primera vez).
set -euo pipefail
cd "$(dirname "$0")"; ROOT="$(cd .. && pwd)"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
if [ ! -x "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" ]; then
  mkdir -p "$ANDROID_HOME/cmdline-tools" && cd "$ANDROID_HOME/cmdline-tools"
  curl -sSL -o t.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
  unzip -q t.zip && mv cmdline-tools latest && rm t.zip; cd - >/dev/null
fi
yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses >/dev/null || true
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platforms;android-34" "build-tools;34.0.0" >/dev/null
WWW=app/src/main/assets/www
rm -rf "$WWW" && mkdir -p "$WWW"
python3 "$ROOT/tools/export_prototype.py" --all --out "$WWW"
cp -r fonts "$WWW/fonts" && cp fonts.css "$WWW/fonts.css"
python3 - <<'PY'
import re
s = open('../prototipo2/index.html', encoding='utf8').read()
s = re.sub(r'<link rel="preconnect"[^>]*>\n?', '', s)
s = s.replace('<link href="https://fonts.googleapis.com/css2?family=Bangers&family=Nunito:wght@800;900&display=swap" rel="stylesheet">', '<link href="fonts.css" rel="stylesheet">')
s = re.sub(r'<script src="pack\d?\.js"></script>\n?', '', s)
open('app/src/main/assets/www/index.html', 'w', encoding='utf8').write(
    '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + s + '</body></html>')
PY
rm -f "$WWW"/pack*.js
sed -i 's|<script src="data.js"></script>|<script src="data.js"></script><script>window.PACK={}</script>|' "$WWW/index.html"
gradle --no-daemon -q assembleDebug
mkdir -p dist && cp app/build/outputs/apk/debug/app-debug.apk dist/ChoqueDeHeroes.apk
ls -la dist/ChoqueDeHeroes.apk
