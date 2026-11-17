// =============================================================================
// Código.gs — SERVIDOR PRINCIPAL
// Juego de Cartas Interactivo MARVEL / DC
// Versión 4.0
// =============================================================================

// -----------------------------------------------------------------------------
// CONSTANTES DE CONFIGURACIÓN
// -----------------------------------------------------------------------------
const CONFIG_SERVIDOR = {
  HOJA_BASE:      "BASE",
  HOJA_SINERGIA:  "SINERGIA",
  MAX_PERSONAJES: 500,
  WIKI_MAX_CHARS: 500,
};

// =============================================================================
// doGet() — PUNTO DE ENTRADA
// =============================================================================
function doGet() {
  return HtmlService.createTemplateFromFile("Index")
    .evaluate()
    .setSandboxMode(HtmlService.SandboxMode.IFRAME)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .setTitle("JUEGO MARVEL & DC");
}

// =============================================================================
// TEST — Ejecutar desde el editor GAS para diagnosticar Gemini
// Menú: seleccionar "testGemini" → Run → ver logs
// =============================================================================
function testGemini() {
  Logger.log("=== TEST GEMINI ===");

  const apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
  if (!apiKey) {
    Logger.log("❌ GEMINI_API_KEY no encontrada en Script Properties");
    Logger.log("   Ir a ⚙️ Configuración → Propiedades del script → Agregar GEMINI_API_KEY");
    return;
  }
  Logger.log("✅ API Key encontrada: " + apiKey.substring(0, 8) + "...");

  // Test 1: narración simple
  const datosTest = {
    ganadorNom:  "Bauti",
    perdedorNom: "Papá",
    nombresG:    "Spider-Man, Doctor Strange, Hulk",
    nombresP:    "Thanos, Galactus, Iron Man",
    paresG:      1,
    marcador:    "Papá 0 - 1 Bauti",
    topHeroes:   "Doctor Strange y Spider-Man",
    ronda:       1,
    esFinal:     false,
  };

  Logger.log("\n--- Test narración ronda ---");
  const resultado = generarNarracionBatalla(datosTest);
  Logger.log("Status: " + resultado.status);
  Logger.log("Narración: " + resultado.narracion);

  // Test 2: pronunciaciones
  Logger.log("\n--- Test pronunciaciones ---");
  const resPron = generarPronunciaciones(["Spider-Man", "Los 4 Fantásticos", "Wolverine", "Thor", "MODOK"]);
  Logger.log("Status: " + resPron.status);
  Logger.log("Pronunciaciones: " + JSON.stringify(resPron.pronunciaciones));
}


// Valores válidos para categorías elementales (16 valores)
const CATEGORIAS_VALIDAS = new Set([
  "FUEGO", "AGUA", "ELECTRICIDAD", "MAGIA", "KRYPTONITA", "METAL",
  "MENTE", "TECNOLOGIA", "LUZ", "OSCURIDAD", "SONIDO", "FRIO",
  "RADIACION", "FISICO", "VENENO", "NINGUNA"
]);

// Campos numéricos que deben clampear a 1–100
const CAMPOS_NUMERICOS = [
  "AGILIDAD", "ARMADURA/DEFENSA", "DAÑO", "FUERZA", "RESISTENCIA",
  "VELOCIDAD", "NIVEL_DE_AMENAZA", "INTELIGENCIA", "LIDERAZGO",
  "TACTICA", "TRABAJO_EN_EQUIPO", "FACTOR_MIEDO", "PODER_ESPECIAL",
  "REGENERACION", "SIGILO"
];

// Columnas de texto que se incluyen tal cual (sin validación de enum)
const CAMPOS_TEXTO = [
  "PERSONAJE", "IMAGEN", "UNIVERSO", "HISTORIA_BREVE",
  "RAREZA_DE_CARTA", "REPUTACION", "ALIADOS_CLAVE",
  "DEBILIDAD", "DEBILIDAD_CATEGORIA", "PODER_ESPECIAL_CATEGORIA",
  "ALCANCE", "HABILIDAD_ESPECIAL"
];

// Reputaciones válidas (para normalización)
const REPUTACIONES_VALIDAS = new Set([
  "LEYENDA", "HÉROE", "NEUTRAL", "VILLANO", "DESCONOCIDO"
]);

// =============================================================================
// doGet() — PUNTO DE ENTRADA DE LA WEB APP
// =============================================================================
// leerBaseDatos() — LECTURA, NORMALIZACIÓN Y VALIDACIÓN DE LA HOJA BASE
//
// Retorna:
//   { datos, sinergia, lastModified, totalPersonajes, status: "OK" }
//   { error, status: "ERROR" }
//
// Llamada desde el cliente vía: google.script.run.leerBaseDatos()
// =============================================================================
function leerBaseDatos() {
  try {
    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(CONFIG_SERVIDOR.HOJA_BASE);

    if (!sheet) {
      throw new Error(
        'No se encontró la hoja "' + CONFIG_SERVIDOR.HOJA_BASE + '". ' +
        "Verificar que el nombre sea exactamente BASE (mayúsculas)."
      );
    }

    const datos   = sheet.getDataRange().getValues();
    const headers = datos[0];
    const filas   = datos.slice(1);

    // ── 1. LEER TABLA DE SINERGIA (hoja separada, configurable sin tocar código) ──
    const sheetSinergia = ss.getSheetByName(CONFIG_SERVIDOR.HOJA_SINERGIA);
    const sinergia = sheetSinergia
      ? sheetSinergia.getDataRange().getValues().slice(1)
          .filter(r => String(r[0]).trim())   // omitir filas vacías
          .map(r => ({
            poder:         String(r[0]).trim().toUpperCase(),
            debilidad:     String(r[1]).trim().toUpperCase(),
            bonusAtacante: parseFloat(r[2]) || 0.05,
            penalizacion:  parseFloat(r[3]) || 0.03,
          }))
      : [];   // si no existe la hoja, el cliente usa defaults de CONFIG

    // ── 2. lastModified: fecha real del Google Sheet en Drive ──
    const lastModified = DriveApp.getFileById(ss.getId())
      .getLastUpdated()
      .toISOString();

    // ── 3. HELPER: obtener valor de una columna por nombre ──
    function get(fila, col) {
      const i = headers.indexOf(col);
      return i >= 0 ? fila[i] : "";
    }

    // ── 4. MAPEAR Y NORMALIZAR PERSONAJES ──
    const personajes = filas
      .filter(fila => String(get(fila, "PERSONAJE")).trim() !== "")
      .slice(0, CONFIG_SERVIDOR.MAX_PERSONAJES)
      .map(fila => {
        // Objeto de personaje con todos los campos necesarios para los motores JS
        const p = {};

        // — Nombre (campo clave, nunca vacío en este punto) —
        p.PERSONAJE = String(get(fila, "PERSONAJE")).trim();

        // — Imagen: solo acepta URLs https:// válidas —
        const imagen = String(get(fila, "IMAGEN")).trim();
        p.IMAGEN = imagen.startsWith("https://") ? imagen : "";

        // — Universo: normalizar a MARVEL o DC, default MARVEL —
        const universo = String(get(fila, "UNIVERSO")).trim().toUpperCase();
        p.UNIVERSO = ["MARVEL", "DC"].includes(universo) ? universo : "MARVEL";

        // — Historia breve: máx 300 chars para no saturar la respuesta JSON —
        p.HISTORIA_BREVE = String(get(fila, "HISTORIA_BREVE")).trim().substring(0, 300);

        // — Rareza: texto libre, normalizar mayúsculas —
        p.RAREZA_DE_CARTA = String(get(fila, "RAREZA_DE_CARTA")).trim().toUpperCase();

        // — Reputación: validar contra enum, default NEUTRAL —
        const rep = String(get(fila, "REPUTACION")).trim().toUpperCase();
        p.REPUTACION = REPUTACIONES_VALIDAS.has(rep) ? rep : "NEUTRAL";

        // — Aliados: texto libre "Batman,Robin,Batgirl" sin espacios —
        p.ALIADOS_CLAVE = String(get(fila, "ALIADOS_CLAVE")).trim();

        // — Debilidad: descripción textual libre —
        p.DEBILIDAD = String(get(fila, "DEBILIDAD")).trim();

        // — Categoría de debilidad: validar contra los 16 valores —
        const debCat = String(get(fila, "DEBILIDAD_CATEGORIA")).trim().toUpperCase();
        p.DEBILIDAD_CATEGORIA = CATEGORIAS_VALIDAS.has(debCat) ? debCat : "NINGUNA";

        // — Categoría de poder especial: ídem —
        const poderCat = String(get(fila, "PODER_ESPECIAL_CATEGORIA")).trim().toUpperCase();
        p.PODER_ESPECIAL_CATEGORIA = CATEGORIAS_VALIDAS.has(poderCat) ? poderCat : "NINGUNA";

        // — Alcance: CUERPO_A_CUERPO / DISTANCIA / etc. —
        p.ALCANCE = String(get(fila, "ALCANCE")).trim().toUpperCase();

        // — Habilidad especial: descripción textual del poder único —
        p.HABILIDAD_ESPECIAL = String(get(fila, "HABILIDAD_ESPECIAL")).trim().substring(0, 200);

        // — Campos numéricos: clampar 1–100, default 50 si inválido —
        CAMPOS_NUMERICOS.forEach(campo => {
          const raw = parseInt(get(fila, campo));
          p[campo] = isNaN(raw) ? 50 : Math.max(1, Math.min(100, raw));
        });

        return p;
      });

    // ── 5. RETORNAR PAYLOAD ──
    return {
      datos:           personajes,
      sinergia:        sinergia,
      lastModified:    lastModified,
      totalPersonajes: personajes.length,
      status:          "OK"
    };

  } catch (e) {
    Logger.log("leerBaseDatos() ERROR: " + e.toString());
    return {
      error:  e.toString(),
      status: "ERROR"
    };
  }
}

// =============================================================================
// obtenerBiografiaWikipedia(nombrePersonaje)
// Obtiene el intro de Wikipedia en español para un personaje.
//
// Estrategia de caché en servidor (PropertiesService):
//   - Persiste entre sesiones de todos los usuarios.
//   - Clave: "wiki_" + nombre normalizado (lowercase, sin espacios).
//   - Sin expiración (Wikipedia de superhéroes cambia raramente).
//
// Retorna:
//   { biografia: "...", fuente: "wikipedia" }   — hit o fetch exitoso
//   { biografia: "",    fuente: "fallback"  }   — personaje no encontrado / error de red
//
// Llamada desde el cliente vía: google.script.run.obtenerBiografiaWikipedia(nombre)
// =============================================================================
function obtenerBiografiaWikipedia(nombrePersonaje) {
  if (!nombrePersonaje || typeof nombrePersonaje !== "string") {
    return { biografia: "", fuente: "fallback" };
  }

  const nombre = nombrePersonaje.trim();

  // ── 1. CACHÉ EN SERVIDOR ──
  const cache    = PropertiesService.getScriptProperties();
  const cacheKey = "wiki_" + nombre.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");

  try {
    const cached = cache.getProperty(cacheKey);
    if (cached) {
      // Respuesta en < 1 ms, sin llamada externa — Log para confirmar hit
      Logger.log("Wikipedia cache HIT: " + nombre);
      return JSON.parse(cached);
    }
  } catch (eCaché) {
    // Si el caché está corrupto, ignorarlo y continuar a fetch
    Logger.log("Cache parse error para [" + nombre + "]: " + eCaché);
  }

  // ── 2. FETCH A WIKIPEDIA (es.wikipedia.org) ──
  try {
    const url =
      "https://es.wikipedia.org/w/api.php"
      + "?action=query"
      + "&titles="      + encodeURIComponent(nombre)
      + "&prop=extracts"
      + "&explaintext=true"
      + "&exintro=true"
      + "&format=json"
      + "&redirects=1";     // seguir redirecciones (ej: "Iron Man" → artículo principal)

    const response = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,  // GAS no soporta timeout; try/catch atrapa errores de red
    });

    // Verificar HTTP status
    const statusCode = response.getResponseCode();
    if (statusCode !== 200) {
      throw new Error("Wikipedia respondió HTTP " + statusCode);
    }

    const json  = JSON.parse(response.getContentText());
    const pages = json.query.pages;
    const page  = pages[Object.keys(pages)[0]];

    // page.missing indica que el artículo no existe en Wikipedia ES
    if (!page || page.missing || !page.extract) {
      Logger.log("Wikipedia: sin artículo para [" + nombre + "]");
      return { biografia: "", fuente: "fallback" };
    }

    // Extraer y limpiar: máx WIKI_MAX_CHARS caracteres del intro
    const bioRaw    = page.extract.replace(/\n+/g, " ").trim();
    const biografia = bioRaw.substring(0, CONFIG_SERVIDOR.WIKI_MAX_CHARS);

    const resultado = {
      biografia: biografia,
      fuente:    "wikipedia"
    };

    // ── 3. GUARDAR EN CACHÉ (sin expiración) ──
    try {
      cache.setProperty(cacheKey, JSON.stringify(resultado));
    } catch (eCacheWrite) {
      // PropertiesService tiene límite de 500 KB total; si falla, simplemente no cachear
      Logger.log("No se pudo guardar en caché [" + nombre + "]: " + eCacheWrite);
    }

    Logger.log("Wikipedia FETCH OK: " + nombre + " (" + biografia.length + " chars)");
    return resultado;

  } catch (e) {
    Logger.log("Wikipedia FETCH ERROR [" + nombre + "]: " + e.toString());
    return { biografia: "", fuente: "fallback" };
  }
}

// =============================================================================
// generarPronunciaciones(nombres) — PRONUNCIACIÓN FONÉTICA VÍA GEMINI
//
// Recibe un array de nombres de personajes y devuelve un objeto
// { "Spider-Man": "Spáiderman", "Wolverine": "Güolverín", ... }
// Se llama UNA SOLA VEZ al cargar la BD y se cachea en el cliente.
// =============================================================================
function generarPronunciaciones(nombres) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');

  if (!apiKey || !nombres || nombres.length === 0) {
    return { pronunciaciones: {}, status: "FALLBACK" };
  }

  // Cache en PropertiesService — si ya los procesamos, devolver directo
  const cacheKey  = "pronunc_" + nombres.length;
  const cacheRaw  = CacheService.getScriptCache().get(cacheKey);
  if (cacheRaw) {
    try {
      return { pronunciaciones: JSON.parse(cacheRaw), status: "CACHE" };
    } catch(e) {}
  }

  const prompt = `Tenés una lista de nombres de personajes de Marvel y DC Comics.
Tu tarea es escribir cómo se pronuncia cada nombre en español rioplatense (Argentina), 
de forma fonética, para que un sintetizador de voz en español los diga correctamente.

REGLAS:
- Si el nombre ya suena bien en español, dejarlo igual (ej: Thor, Hulk → dejá "Thor", "Hulk")
- Si tiene palabras en inglés, escribilas como suenan (ej: Spider-Man → Spáiderman)
- Números: escribilos como palabras (ej: 4 Fantásticos → Cuatro Fantásticos)
- Siglas: separalas con puntos (ej: MODOK → M.O.D.O.K.)
- Nombres compuestos: mantené el significado (ej: Black Widow → Black Güidou)
- Si es completamente en español, dejalo exactamente igual

Respondé ÚNICAMENTE con un objeto JSON válido, sin explicaciones, sin markdown, sin bloques de código.
Formato exacto: {"nombre original": "pronunciación", "nombre original 2": "pronunciación 2"}

NOMBRES A PROCESAR:
${nombres.join("\n")}`;

  try {
    const url     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + apiKey;
    const payload = JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature:     0.1,
        maxOutputTokens: 8000,
        thinkingConfig:  { thinkingBudget: 0 }  // desactivar thinking — libera tokens para el output
      }
    });

    const response = UrlFetchApp.fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      payload: payload,
      muteHttpExceptions: true,
    });

    if (response.getResponseCode() !== 200) {
      return { pronunciaciones: {}, status: "FALLBACK" };
    }

    const json  = JSON.parse(response.getContentText());
    let texto   = json?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";

    // Limpiar si Gemini mete markdown igual
    texto = texto.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();

    const pronunciaciones = JSON.parse(texto);

    // Guardar en cache por 6 horas
    try {
      CacheService.getScriptCache().put(cacheKey, JSON.stringify(pronunciaciones), 21600);
    } catch(e) {}

    Logger.log("Pronunciaciones generadas: " + Object.keys(pronunciaciones).length + " nombres");
    return { pronunciaciones, status: "OK" };

  } catch(e) {
    Logger.log("generarPronunciaciones() ERROR: " + e.toString());
    return { pronunciaciones: {}, status: "ERROR" };
  }
}

//
// Se llama desde el cliente vía google.script.run porque GAS tiene
// acceso a internet mientras que el IFRAME del cliente tiene CSP restringida.
//
// datos = {
//   ganadorNom, perdedorNom,
//   nombresG, nombresP,
//   paresG, marcador, topHeroes,
//   ronda, esFinal
// }
//
// Retorna: { narracion: "texto épico...", status: "OK" }
//          { narracion: "",               status: "ERROR", error: "..." }
// =============================================================================
function generarNarracionBatalla(datos) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');

  if (!apiKey) {
    return {
      narracion: _generarNarracionFallbackServidor(datos),
      status:    "FALLBACK"
    };
  }

  const instruccionPronunciacion = `
PRONUNCIACIÓN IMPORTANTE: Cuando menciones nombres en inglés, escríbelos fonéticamente en español para que suenen bien al leerlos en voz alta. Ejemplos:
- Spider-Man → Spáiderman
- Wolverine → Güolverín
- The Beyonder → De Bionder
- Sentinel → Séntinel
- Deadpool → Déidpul
- Hulk → Jalk
- Iron Man → Áiron Man
- Venom → Bénom
- Cyclops → Sáiklops
- Sabretooth → Seibrtu
Aplicá esto a TODOS los nombres en inglés que aparezcan.`;

  const promptRonda = `Sos el NARRADOR ÉPICO de un juego de cartas de superhéroes Marvel y DC para niños de 5 a 10 años. Tu estilo es apasionado, dramático y fácil de entender para chicos pequeños, como un comentarista de fútbol narrando el gol del campeonato.

RONDA ${datos.ronda} — DATOS:
- GANADOR: ${datos.ganadorNom} con el equipo: ${datos.nombresG}
- PERDEDOR: ${datos.perdedorNom} con el equipo: ${datos.nombresP}
${datos.paresG > 0 ? `- El equipo ganador tenía ${datos.paresG} par(es) de aliados que se potenciaron juntos.` : ""}
- Marcador actual: ${datos.marcador}
- Héroe más poderoso del ganador: ${datos.topHeroes}

INSTRUCCIONES:
1. Empezá con una exclamación emocionante anunciando al ganador
2. Explicá con detalle por qué ganó: inventá acciones épicas usando los poderes REALES de cada personaje (si hay Doctor Strange usó sus portales, si hay Superman usó sus ojos láser, si hay Thor usó su martillo, etc.)
3. Describí cómo los héroes del equipo ganador vencieron específicamente a los del equipo perdedor, mencionándolos a todos por nombre
4. Si había aliados, mostrá cómo trabajaron juntos
5. Cerrá con el marcador actual y una frase de aliento para el perdedor
Longitud: mínimo 5 oraciones, máximo 8. Que sea emocionante y dramático.

${instruccionPronunciacion}

Respondé SOLO con el texto narrativo completo. Sin títulos, sin listas, sin asteriscos. IMPORTANTE: completá todas las oraciones, no cortes el texto a mitad. Mínimo 5 oraciones completas.`;

  const promptFinal = `Sos el NARRADOR ÉPICO de un juego de cartas de superhéroes Marvel y DC para niños de 5 a 10 años. Narrá el RESULTADO FINAL con la emoción de la final del mundial.

BATALLA FINAL — DATOS:
- CAMPEÓN: ${datos.ganadorNom} con el equipo: ${datos.nombresG}
- SUBCAMPEÓN: ${datos.perdedorNom} con el equipo: ${datos.nombresP}
${datos.paresG > 0 ? `- El campeón tenía ${datos.paresG} par(es) de aliados clave.` : ""}
- Marcador final: ${datos.marcador}
- Héroes más destacados del campeón: ${datos.topHeroes}

INSTRUCCIONES:
1. Anunciá al campeón con la máxima emoción
2. Describí la batalla final con acciones épicas de cada personaje por nombre (usando sus poderes reales)
3. Mostrá el momento decisivo que definió la victoria
4. Reconocé el gran esfuerzo del subcampeón
5. Cerrá con el marcador final y una celebración épica para los chicos
Longitud: mínimo 6 oraciones, máximo 9.

${instruccionPronunciacion}

Respondé SOLO con el texto narrativo completo. Sin títulos, sin listas, sin asteriscos. IMPORTANTE: completá todas las oraciones, no cortes el texto a mitad. Mínimo 6 oraciones completas.`;

  const prompt = datos.esFinal ? promptFinal : promptRonda;

  try {
    const url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + apiKey;

    const payload = JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature:     0.9,
        maxOutputTokens: datos.esFinal ? 2000 : 1500,
        thinkingConfig:  { thinkingBudget: 0 }  // desactivar thinking — sin esto consume tokens internos y corta el output
      }
    });

    const response = UrlFetchApp.fetch(url, {
      method:             "POST",
      headers:            { "Content-Type": "application/json" },
      payload:            payload,
      muteHttpExceptions: true,
    });

    const codigo = response.getResponseCode();
    if (codigo !== 200) {
      Logger.log("Gemini API error: " + codigo + " — " + response.getContentText());
      return { narracion: _generarNarracionFallbackServidor(datos), status: "FALLBACK" };
    }

    const json      = JSON.parse(response.getContentText());
    const narracion = json?.candidates?.[0]?.content?.parts?.[0]?.text || "";

    if (!narracion) {
      return { narracion: _generarNarracionFallbackServidor(datos), status: "FALLBACK" };
    }

    Logger.log("Gemini narración OK (" + narracion.length + " chars) — Ronda " + datos.ronda);
    return { narracion, status: "OK" };

  } catch(e) {
    Logger.log("generarNarracionBatalla() ERROR: " + e.toString());
    return {
      narracion: _generarNarracionFallbackServidor(datos),
      status:    "ERROR",
      error:     e.toString()
    };
  }
}


// Fallback en servidor cuando la API no está disponible
function _generarNarracionFallbackServidor(datos) {
  const top = datos.topHeroes || datos.nombresG.split(",")[0];
  if (datos.esFinal) {
    return "¡Campeón absoluto " + datos.ganadorNom + "! Su equipo con " + top +
           " fue simplemente imparable durante toda la batalla. " +
           datos.perdedorNom + " peleó con todo pero no pudo detenerlos. " +
           "Marcador final: " + datos.marcador + ". ¡Felicitaciones al campeón!";
  }
  return "¡Punto para " + datos.ganadorNom + " en la ronda " + datos.ronda + "! " +
         top + " lideró la victoria con una actuación increíble. " +
         datos.perdedorNom + " lo intentó pero no alcanzó. " +
         "Marcador: " + datos.marcador + ".";
}

// Ejecutar estas funciones desde el editor para verificar que todo funciona
// ANTES de pasar a la Fase 2. No se exponen al cliente.
// =============================================================================

/**
 * TEST 1 — leerBaseDatos()
 * Cómo usar: abrir el editor GAS → seleccionar "testLeerBaseDatos" → Run.
 * Verificar en el log: totalPersonajes > 0, status = "OK", sinergia.length > 0.
 */
function testLeerBaseDatos() {
  const resultado = leerBaseDatos();
  Logger.log("=== TEST leerBaseDatos() ===");
  Logger.log("Status:          " + resultado.status);

  if (resultado.status === "ERROR") {
    Logger.log("Error:           " + resultado.error);
    return;
  }

  Logger.log("totalPersonajes: " + resultado.totalPersonajes);
  Logger.log("lastModified:    " + resultado.lastModified);
  Logger.log("sinergia.length: " + resultado.sinergia.length);

  if (resultado.datos.length > 0) {
    const p = resultado.datos[0];
    Logger.log("\n── Primer personaje ──");
    Logger.log("PERSONAJE:               " + p.PERSONAJE);
    Logger.log("UNIVERSO:                " + p.UNIVERSO);
    Logger.log("RAREZA_DE_CARTA:         " + p.RAREZA_DE_CARTA);
    Logger.log("REPUTACION:              " + p.REPUTACION);
    Logger.log("DEBILIDAD_CATEGORIA:     " + p.DEBILIDAD_CATEGORIA);
    Logger.log("PODER_ESPECIAL_CATEGORIA:" + p.PODER_ESPECIAL_CATEGORIA);
    Logger.log("ALCANCE:                 " + p.ALCANCE);
    Logger.log("HABILIDAD_ESPECIAL:      " + p.HABILIDAD_ESPECIAL);
    Logger.log("FUERZA:                  " + p.FUERZA);
    Logger.log("INTELIGENCIA:            " + p.INTELIGENCIA);
    Logger.log("IMAGEN (válida):         " + (p.IMAGEN.startsWith("https://") ? "SÍ" : "NO — vacía"));
  }

  // Verificar que ningún campo numérico esté fuera de rango
  let erroresNumericos = 0;
  resultado.datos.forEach(p => {
    CAMPOS_NUMERICOS.forEach(campo => {
      if (p[campo] < 1 || p[campo] > 100) {
        Logger.log("⚠️ Fuera de rango: " + p.PERSONAJE + " → " + campo + " = " + p[campo]);
        erroresNumericos++;
      }
    });
  });
  Logger.log("\nErrores numéricos encontrados: " + erroresNumericos);
  Logger.log(erroresNumericos === 0 ? "✅ Todos los campos numéricos OK" : "🛑 Revisar campos numéricos");
}

/**
 * TEST 2 — obtenerBiografiaWikipedia()
 * Cómo usar: abrir el editor GAS → seleccionar "testWikipedia" → Run.
 * Verificar en el log: fuente = "wikipedia", biografia con texto visible.
 * Segunda ejecución debe mostrar "cache HIT" en el log.
 */
function testWikipedia() {
  const casos = [
    "Spider-Man",   // personaje que existe en Wikipedia ES
    "Batman",       // idem
    "PersonajeXYZQueNoExiste",  // debe retornar fuente = "fallback"
  ];

  Logger.log("=== TEST obtenerBiografiaWikipedia() ===");

  casos.forEach(nombre => {
    const r = obtenerBiografiaWikipedia(nombre);
    Logger.log("\n── " + nombre + " ──");
    Logger.log("fuente:   " + r.fuente);
    Logger.log("bio:      " + (r.biografia ? r.biografia.substring(0, 100) + "..." : "(vacía)"));
  });
}

/**
 * TEST 3 — Verificar hoja SINERGIA
 * Confirma que la tabla de sinergia tiene las 16 filas esperadas.
 */
function testSinergia() {
  const r = leerBaseDatos();
  Logger.log("=== TEST Sinergia ===");
  if (r.status === "ERROR") { Logger.log("Error: " + r.error); return; }
  Logger.log("Filas de sinergia: " + r.sinergia.length);
  r.sinergia.forEach(s => {
    Logger.log(s.poder + " → " + s.debilidad
      + " | bonus=" + s.bonusAtacante
      + " pen=" + s.penalizacion);
  });
}

/**
 * TEST 4 — Limpiar caché de Wikipedia
 * Usar para forzar re-fetch en desarrollo. NO ejecutar en producción.
 */
function limpiarCacheWikipedia() {
  const props = PropertiesService.getScriptProperties();
  const claves = props.getKeys().filter(k => k.startsWith("wiki_"));
  claves.forEach(k => props.deleteProperty(k));
  Logger.log("Caché Wikipedia limpiado: " + claves.length + " entradas eliminadas.");
}