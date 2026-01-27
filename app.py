import os
import re
import json
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# ==========================================================
# CONFIGURACIÓN
# ==========================================================
BASE_DIR = "docs"
NOMBRE_ASISTENTE = "TAO"

# Guardado de memoria persistente
STATE_FILE = os.path.join(BASE_DIR, "tao_state.json")

# Activa o desactiva debug (para ver detecciones)
DEBUG = False

# ==========================================================
# STOPWORDS Y PALABRAS DE RELLENO
# ==========================================================
STOPWORDS = {
    "que", "es", "de", "la", "el", "un", "una", "sobre",
    "dime", "info", "informacion", "explícame", "explicame",
    "acerca", "del", "al", "para", "me", "puedes", "por",
    "favor", "hacer", "como", "cómo", "funciona", "quiero",
    "saber", "necesita", "necesitan", "cuales", "cuáles",
    "cual", "cuando", "donde", "porque", "porq", "ya",
    "ahora", "esto", "eso", "mi", "tu", "su", "se",
    "lo", "los", "las", "y", "o", "a", "en", "con",
    "tienen", "tiene", "hay", "dame", "quiero", "ver",
    "pasame", "pasa", "numero", "porfa", "pls", "porfavor",
    "necesito", "ocupó", "ocupo", "quiero", "mandame", "mándame",
    "rvoe", "del", "de", "la", "el", "los", "las", "un", "una",
    "quiero", "quiero", "quiero"
}

PALABRAS_GRADO = {
    "licenciatura", "ingenieria", "ingeniería", "maestria", "maestría",
    "doctorado", "carrera", "tecnologia", "tecnología", "en"
}

# ==========================================================
# SINÓNIMOS / SIGLAS (MEJORADOS)
# ==========================================================
SINONIMOS = {
    # Bachilleratos
    "bg": "bachillerato general",
    "b g": "bachillerato general",
    "bach general": "bachillerato general",
    "prepa": "bachillerato general",
    "preparatoria": "bachillerato general",
    "bgc": "bachillerato general por competencias",
    "b g c": "bachillerato general por competencias",
    "bachillerato por competencias": "bachillerato general por competencias",
    "bach compet": "bachillerato general por competencias",

    # Carreras comunes
    "admin": "administracion",
    "adm": "administracion",
    "admon": "administracion",
    "conta": "contaduria",
    "conta publica": "contaduria publica",
    "psico": "psicologia",
    "nutri": "nutricion",
    "qfb": "quimico farmaceutico biologo",
    "cfyd": "cultura fisica y deportes",
    "cfd": "cultura fisica y deportes",
    "ri": "relaciones internacionales",
    "ni": "negocios internacionales",
    "isc": "ingenieria en sistemas",
    "sis": "ingenieria en sistemas",
    "civil": "ingenieria civil",
    "datos": "ingenieria en ciencia de datos",
    "ciencia de datos": "ingenieria en ciencia de datos",

    # Abreviaturas de títulos
    "lic": "licenciatura",
    "ing": "ingenieria",
    "inge": "ingenieria",
}

# ==========================================================
# PLANTELES (ALIAS)
# ==========================================================
PLANTELES = {
    "americas": ["americas", "américas", "america", "américa"],
    "campus": ["campus"],
    "olimpica": ["olimpica", "olímpica", "olimpico", "olímpico"],
    "zapopan": ["zapopan"],
    "rio nilo": ["rio nilo", "río nilo", "rionilo", "rio", "nilo"],
    "tlajomulco": ["tlajomulco"],
    "tepatitlan": ["tepatitlan", "tepatitlàn", "tepa"],
    "pedro moreno": ["pedro moreno", "pedromoreno"],
    "lazaro cardenas": ["lazaro cardenas", "lázaro cárdenas", "lazaro", "cardenas"],
}

# ==========================================================
# INCORPORACIONES (ALIAS)
# ==========================================================
INCORPORACIONES = {
    "UDG": ["udg", "udeg", "universidad de guadalajara", "incorporada a udg", "incorporacion udg"],
    "SEP": ["sep", "incorporada a sep", "incorporacion sep"],
    "SEJ": ["sej"],
    "SICYT": ["sicyt"]
}

# ==========================================================
# CONVERSATION STATE (con persistencia)
# ==========================================================
@dataclass
class ConversationState:
    last_plantel: Optional[str] = None
    last_incorporacion: Optional[str] = None
    last_carrera: Optional[str] = None

    # Modo de respuesta
    last_mode: str = "normal"   # normal | wpp | llamada
    last_detail: str = "completo"  # corto | completo

    # Audiencia
    last_audiencia: str = "alumno"  # alumno | padre | asesor

    # Opciones recientes (para seleccionar 1/2/3)
    last_options: List[dict] = field(default_factory=list)

    # Si venimos de un menú
    last_menu: bool = False


STATE = ConversationState()

# ==========================================================
# UTILIDADES DE TEXTO
# ==========================================================
def quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )

def normalizar(texto: str) -> str:
    texto = quitar_acentos(texto.lower())
    texto = re.sub(r"[^a-z0-9\s/]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def tokenizar(texto: str) -> List[str]:
    texto = normalizar(texto)
    return [t for t in texto.split() if t and t not in STOPWORDS]

def limpiar_grado(texto_norm: str) -> str:
    toks = [t for t in tokenizar(texto_norm) if t not in PALABRAS_GRADO]
    return " ".join(toks).strip()

def aplicar_sinonimos(texto_norm: str) -> str:
    palabras = texto_norm.split()
    nuevas = []
    i = 0
    while i < len(palabras):
        w = palabras[i]

        if i + 1 < len(palabras):
            dos = f"{w} {palabras[i+1]}"
            if dos in SINONIMOS:
                nuevas.extend(SINONIMOS[dos].split())
                i += 2
                continue

        if w in SINONIMOS:
            nuevas.extend(SINONIMOS[w].split())
        else:
            nuevas.append(w)

        i += 1

    return " ".join(nuevas).strip()

def titulo_plantel(canonico: str) -> str:
    mapa = {
        "americas": "PLANTEL AMÉRICAS",
        "campus": "PLANTEL CAMPUS",
        "olimpica": "PLANTEL OLÍMPICA",
        "zapopan": "PLANTEL ZAPOPAN",
        "rio nilo": "PLANTEL RÍO NILO",
        "tlajomulco": "PLANTEL TLAJOMULCO",
        "tepatitlan": "PLANTEL TEPATITLÁN",
        "pedro moreno": "PLANTEL PEDRO MORENO",
        "lazaro cardenas": "PLANTEL LÁZARO CÁRDENAS",
    }
    return mapa.get(canonico, canonico.upper())

# ==========================================================
# MEMORIA PERSISTENTE
# ==========================================================
def cargar_state():
    global STATE
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # restaurar
            STATE.last_plantel = data.get("last_plantel")
            STATE.last_incorporacion = data.get("last_incorporacion")
            STATE.last_carrera = data.get("last_carrera")
            STATE.last_mode = data.get("last_mode", "normal")
            STATE.last_detail = data.get("last_detail", "completo")
            STATE.last_audiencia = data.get("last_audiencia", "alumno")
            # no guardamos options, se limpian
            STATE.last_options = []
            STATE.last_menu = False
    except Exception:
        # si falla, no pasa nada
        pass

def guardar_state():
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        data = {
            "last_plantel": STATE.last_plantel,
            "last_incorporacion": STATE.last_incorporacion,
            "last_carrera": STATE.last_carrera,
            "last_mode": STATE.last_mode,
            "last_detail": STATE.last_detail,
            "last_audiencia": STATE.last_audiencia,
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ==========================================================
# DETECTORES: MODO / DETALLE / AUDIENCIA
# ==========================================================
def detectar_modo(pregunta_norm: str) -> Optional[str]:
    if pregunta_norm.startswith("modo wpp") or pregunta_norm.startswith("modo whatsapp"):
        return "wpp"
    if pregunta_norm.startswith("modo llamada"):
        return "llamada"
    if pregunta_norm.startswith("modo normal"):
        return "normal"

    if pregunta_norm.startswith("wpp ") or "whatsapp" in pregunta_norm or "para whatsapp" in pregunta_norm:
        return "wpp"
    if pregunta_norm.startswith("llamada ") or "para llamada" in pregunta_norm or "en llamada" in pregunta_norm:
        return "llamada"
    return None

def detectar_detalle(pregunta_norm: str) -> Optional[str]:
    if pregunta_norm.startswith("corto "):
        return "corto"
    if pregunta_norm.startswith("completo "):
        return "completo"
    return None

def detectar_audiencia(pregunta_norm: str) -> str:
    if any(x in pregunta_norm for x in ["padre", "mama", "mamá", "papa", "papá", "familia", "tutor"]):
        return "padre"
    if any(x in pregunta_norm for x in ["asesor", "ventas", "prospecto", "aspirante", "inscripcion", "inscripción", "cierre"]):
        return "asesor"
    return "alumno"

# ==========================================================
# INTENCIÓN RVOE
# ==========================================================
def detectar_intencion_rvoe(pregunta_norm: str) -> str:
    # menu
    if pregunta_norm in {"rvoe", "rvoes"} or len(pregunta_norm.split()) <= 2:
        return "menu"

    # definicion
    if pregunta_norm.startswith("que es rvoe") or "que significa rvoe" in pregunta_norm:
        return "definicion"

    if "que es un rvoe" in pregunta_norm or "qué es un rvoe" in pregunta_norm:
        return "definicion"

    # listar
    if any(w in pregunta_norm for w in ["lista", "listado", "todos", "todas", "cuales hay", "que carreras", "cuáles carreras", "muestrame", "muéstrame"]):
        return "listar"

    # comparar
    if any(w in pregunta_norm for w in ["udg vs sep", "sep vs udg", "diferencia udg sep", "diferencia entre udg y sep"]):
        return "comparar"

    return "buscar"

def detectar_nivel(pregunta_norm: str) -> Optional[str]:
    if "bachillerato" in pregunta_norm or "bg" in pregunta_norm or "prepa" in pregunta_norm:
        return "bachillerato"
    if "maestr" in pregunta_norm:
        return "maestria"
    if "doctor" in pregunta_norm:
        return "doctorado"
    if "licenci" in pregunta_norm or "ingenier" in pregunta_norm:
        return "licenciatura"
    return None

# ==========================================================
# FUZZY DETECTION: PLANTEL / INCORPORACIÓN
# ==========================================================
def detectar_plantel_fuzzy(pregunta_norm: str) -> Optional[str]:
    # 1) alias directo
    for canon, alias_list in PLANTELES.items():
        for a in alias_list:
            if normalizar(a) in pregunta_norm:
                return canon

    # 2) fuzzy token
    tokens = tokenizar(pregunta_norm)
    mejor = (0.0, None)

    for canon, alias_list in PLANTELES.items():
        for a in alias_list:
            a_norm = normalizar(a)
            for t in tokens:
                s = similitud(t, a_norm)
                if s > mejor[0]:
                    mejor = (s, canon)

    if mejor[0] >= 0.82:
        return mejor[1]
    return None

def detectar_incorporacion_fuzzy(pregunta_norm: str) -> Optional[str]:
    for canon, alias_list in INCORPORACIONES.items():
        for a in alias_list:
            if normalizar(a) in pregunta_norm:
                return canon

    tokens = tokenizar(pregunta_norm)
    mejor = (0.0, None)

    for canon, alias_list in INCORPORACIONES.items():
        for a in alias_list:
            a_norm = normalizar(a)
            for t in tokens:
                s = similitud(t, a_norm)
                if s > mejor[0]:
                    mejor = (s, canon)

    if mejor[0] >= 0.80:
        return mejor[1]
    return None

# ==========================================================
# EXTRAER INTENCIÓN + KEYWORDS DE TXT (GENÉRICO)
# ==========================================================
def extraer_intencion(contenido: str) -> str:
    patrones = [
        r"^\s*intencion_principal:\s*(.+)$",
        r"^\s*intencion:\s*(.+)$",
        r"^\s*intencion principal:\s*(.+)$",
    ]
    for pat in patrones:
        m = re.search(pat, contenido, re.IGNORECASE | re.MULTILINE)
        if m:
            return normalizar(m.group(1).strip())
    return ""

def extraer_keywords(contenido: str) -> List[str]:
    m = re.search(r"(palabras_clave:|palabras clave:|terminos clave:|términos clave:)", contenido, re.IGNORECASE)
    if not m:
        return []
    bloque = contenido[m.end():]
    lineas = bloque.splitlines()
    kws = []
    for ln in lineas:
        ln2 = normalizar(ln.strip())
        if not ln2:
            break
        partes = [p.strip() for p in ln2.split(",") if p.strip()]
        kws.extend(partes)
    return kws

# ==========================================================
# CARGA DOCS + ÍNDICES PARA VELOCIDAD (TOP)
# ==========================================================
def cargar_docs() -> List[dict]:
    docs = []
    if not os.path.exists(BASE_DIR):
        return docs

    for root, _, files in os.walk(BASE_DIR):
        for archivo in files:
            if not archivo.lower().endswith(".txt"):
                continue

            ruta = os.path.join(root, archivo)
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()

            rel_path = os.path.relpath(ruta, BASE_DIR)

            intencion = extraer_intencion(contenido)
            keywords = extraer_keywords(contenido)

            contenido_norm = normalizar(contenido)
            archivo_norm = normalizar(rel_path)

            # índices precalculados
            tokens_doc = set(tokenizar(contenido_norm))
            tokens_int = set(tokenizar(intencion))
            tokens_kw = set()
            for kw in keywords:
                tokens_kw |= set(tokenizar(kw))

            docs.append({
                "archivo": rel_path,
                "archivo_norm": archivo_norm,
                "intencion": intencion,
                "keywords": keywords,
                "contenido": contenido,
                "contenido_norm": contenido_norm,
                "tokens_doc": tokens_doc,
                "tokens_int": tokens_int,
                "tokens_kw": tokens_kw,
            })

    return docs

# ==========================================================
# RANKING DOCS (MEJORADO)
# ==========================================================
def buscar_doc_ranking(pregunta: str, docs: List[dict]) -> Optional[dict]:
    pn = aplicar_sinonimos(normalizar(pregunta))
    ptokens = set(tokenizar(pn))

    mejor_doc = None
    mejor_score = 0

    for doc in docs:
        score = 0

        # match fuerte por intención
        if doc["intencion"] and doc["intencion"] in pn:
            score += 120

        # intersección tokens
        score += len(ptokens & doc["tokens_int"]) * 30
        score += len(ptokens & doc["tokens_kw"]) * 18
        score += len(ptokens & doc["tokens_doc"]) * 1

        # pequeño boost si "rvoe" aparece en el contenido y pregunta lo trae
        if "rvoe" in pn and "rvoe" in doc["contenido_norm"]:
            score += 40

        if score > mejor_score:
            mejor_score = score
            mejor_doc = doc

    if mejor_score >= 10:
        return mejor_doc
    return None

# ==========================================================
# RVOE: AGRUPACIÓN + "RVOE MÁS NUEVO"
# ==========================================================
def rank_rvoe(rvoe: str) -> int:
    r = normalizar(rvoe)

    # SEP numérico: 20230922
    if re.fullmatch(r"\d{8}", r):
        return int(r)

    # UDG: 090/2022
    m = re.fullmatch(r"(\d+)\s*/\s*(\d{4})", rvoe.strip())
    if m:
        num = int(m.group(1))
        year = int(m.group(2))
        return year * 10000 + num

    return 0

def agrupar_programas(programas: list) -> list:
    agrupados = {}

    for it in programas:
        key = (it["programa_norm"], it["incorporacion"])

        if key not in agrupados:
            agrupados[key] = {
                **it,
                "rvoes": [it["rvoe"]]
            }
        else:
            if it["rvoe"] not in agrupados[key]["rvoes"]:
                agrupados[key]["rvoes"].append(it["rvoe"])

            # mantener como principal el más nuevo
            actual = agrupados[key]["rvoe"]
            if rank_rvoe(it["rvoe"]) > rank_rvoe(actual):
                agrupados[key]["rvoe"] = it["rvoe"]

    for k in agrupados:
        agrupados[k]["rvoes"].sort(key=rank_rvoe, reverse=True)

    return list(agrupados.values())

# ==========================================================
# RVOE: PARSEAR TXT
# ==========================================================
def parsear_rvoe(contenido: str) -> Dict[str, list]:
    estructura = {}
    patron_plantel = re.compile(r"📍\s*PLANTEL\s+([A-ZÁÉÍÓÚÑ ]+)", re.IGNORECASE)
    matches = list(patron_plantel.finditer(contenido))

    if not matches:
        return estructura

    def inferir_nivel(programa_norm: str):
        if "bachillerato" in programa_norm:
            return "bachillerato"
        if "maestr" in programa_norm:
            return "maestria"
        if "doctor" in programa_norm:
            return "doctorado"
        return "licenciatura"

    for i, m in enumerate(matches):
        plantel_nombre = m.group(1).strip()
        plantel_norm = normalizar(plantel_nombre)

        plantel_canon = None
        for canonico, alias_list in PLANTELES.items():
            if any(normalizar(a) in plantel_norm for a in alias_list):
                plantel_canon = canonico
                break

        if not plantel_canon:
            plantel_canon = plantel_norm

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(contenido)
        bloque = contenido[start:end].strip()

        lineas = [ln.strip() for ln in bloque.splitlines() if ln.strip()]

        programas = []
        nombre = None
        incorp = None
        rvoe = None

        for ln in lineas:
            if ln.startswith("🎓"):
                # flush anterior
                if nombre and incorp and rvoe:
                    prog_norm = normalizar(nombre)
                    programas.append({
                        "programa": nombre,
                        "programa_norm": prog_norm,
                        "programa_core": limpiar_grado(prog_norm),
                        "incorporacion": incorp.upper(),
                        "rvoe": rvoe,
                        "nivel": inferir_nivel(prog_norm)
                    })

                nombre = ln.replace("🎓", "").strip()
                incorp = None
                rvoe = None

            elif "incorporacion" in normalizar(ln):
                parts = ln.split(":")
                if len(parts) >= 2:
                    incorp = parts[1].strip().upper()

            elif "rvoe" in normalizar(ln):
                parts = ln.split(":")
                if len(parts) >= 2:
                    rvoe = parts[1].strip()

        # flush final
        if nombre and incorp and rvoe:
            prog_norm = normalizar(nombre)
            programas.append({
                "programa": nombre,
                "programa_norm": prog_norm,
                "programa_core": limpiar_grado(prog_norm),
                "incorporacion": incorp.upper(),
                "rvoe": rvoe,
                "nivel": inferir_nivel(prog_norm)
            })

        # AGRUPAR DUPLICADOS
        estructura[plantel_canon] = agrupar_programas(programas)

    return estructura

# ==========================================================
# RVOE: MENÚ, DEFINICIÓN, COMPARATIVA
# ==========================================================
def menu_rvoe():
    return (
        f"👋 Hola, soy {NOMBRE_ASISTENTE}.\n\n"
        "📌 ¿Qué necesitas sobre **RVOE**?\n\n"
        "1) ✅ Buscar un RVOE específico (carrera + plantel)\n"
        "2) 📍 Ver todos los RVOE de un plantel\n"
        "3) 🏛️ Ver solo RVOE por incorporación (UDG / SEP)\n"
        "4) 📘 ¿Qué es el RVOE? (definición rápida)\n"
        "5) ⚖️ Diferencia UDG vs SEP\n\n"
        "Responde con el número (1-5) o escríbemelo directo.\n"
        "Ejemplo:\n"
        "👉 *RVOE Administracion UDG Zapopan*\n"
        "👉 *Lista RVOE Zapopan SEP*"
    )

def respuesta_definicion_rvoe(audiencia: str):
    base = (
        "🎓 **RVOE** = *Reconocimiento de Validez Oficial de Estudios*.\n"
        "Es el acuerdo emitido por la autoridad educativa (SEP o Universidad incorporante) que confirma que un programa tiene **validez oficial** en México.\n\n"
        "✅ Con RVOE, tus documentos académicos (constancias, certificados, título) tienen **reconocimiento legal**.\n"
    )
    if audiencia == "asesor":
        base += "\n🗣️ *Cómo decirlo al prospecto:*\n“Tu carrera tiene validez oficial porque cuenta con RVOE, eso asegura que tu título es reconocido en México.”"
    elif audiencia == "padre":
        base += "\n👨‍👩‍👧 *Para tranquilidad familiar:*\n“Este reconocimiento garantiza que el programa está avalado por autoridad educativa y mantiene validez oficial.”"
    return base

def respuesta_comparativa_udg_sep():
    return (
        "⚖️ **Diferencia UDG vs SEP (incorporación)**\n\n"
        "🏛️ **UDG:**\n"
        "• Programas avalados por Universidad incorporante.\n"
        "• RVOE típico: “090/2022”.\n\n"
        "🏛️ **SEP:**\n"
        "• Programas avalados por SEP.\n"
        "• RVOE típico: “20230931”.\n\n"
        "✅ Ambos tienen validez oficial. Cambia principalmente **quién respalda la incorporación**."
    )

# ==========================================================
# RESPUESTAS PERSONALIZADAS
# ==========================================================
def intro_personalizada(audiencia: str):
    if audiencia == "asesor":
        return f"👋 Hola, soy {NOMBRE_ASISTENTE}. Te lo paso directo y listo para usar ✅"
    if audiencia == "padre":
        return f"👋 Hola, soy {NOMBRE_ASISTENTE}. Te lo explico claro para que tengas seguridad ✅"
    return f"👋 Hola, soy {NOMBRE_ASISTENTE}. Aquí tienes la info ✅"

def responder_formato(mode: str, detail: str, plantel: str, programa: str, incorp: str, rvoe_principal: str, rvoes_extra: List[str]):
    """
    - mode: normal / wpp / llamada
    - detail: corto / completo
    """
    # ---- Corto: solo dato
    if detail == "corto":
        if mode == "wpp":
            return f"📌 *{programa}* ({incorp}) – {titulo_plantel(plantel)} | *RVOE: {rvoe_principal}* ✅"
        if mode == "llamada":
            return f"{programa} ({incorp}) en {titulo_plantel(plantel)} | RVOE {rvoe_principal} ✅"
        return f"🏫 {titulo_plantel(plantel)} | 🎓 {programa} | 🏛️ {incorp} | 📄 RVOE: {rvoe_principal} ✅"

    # ---- Completo: bonito + extras
    extras = ""
    if rvoes_extra:
        extras = f"\n📌 Otros RVOE registrados: {', '.join(rvoes_extra)}"

    if mode == "wpp":
        return f"📌 *{programa}* ({incorp}) – {titulo_plantel(plantel)} | *RVOE: {rvoe_principal}* ✅{extras}"
    if mode == "llamada":
        return f"Claro: en {titulo_plantel(plantel)} {programa} está incorporado a {incorp} y su RVOE es {rvoe_principal} ✅{extras}"

    return (
        f"🏫 **{titulo_plantel(plantel)}**\n"
        f"🎓 **{programa}**\n"
        f"🏛️ Incorporación: **{incorp}**\n"
        f"📄 **RVOE: {rvoe_principal}** ✅"
        f"{extras}"
    )

# ==========================================================
# SELECCIÓN NUMÉRICA (1,2,3...)
# ==========================================================
def es_seleccion_numero(pregunta_norm: str):
    return bool(re.fullmatch(r"[1-9]\d*", pregunta_norm.strip()))

def resolver_seleccion_numero(pregunta_norm: str):
    idx = int(pregunta_norm.strip()) - 1
    if 0 <= idx < len(STATE.last_options):
        return STATE.last_options[idx]
    return None

# ==========================================================
# EXTRAER ENTIDADES SIN DEPENDER DE "EN"
# ==========================================================
def extraer_entidades_orden_libre(pregunta: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Detecta plantel, incorporación y carrera en cualquier orden.
    - Quita plantel/incorp del texto y lo restante lo toma como carrera.
    """
    pn = aplicar_sinonimos(normalizar(pregunta))

    plantel = detectar_plantel_fuzzy(pn)
    incorporacion = detectar_incorporacion_fuzzy(pn)

    # quitar palabras típicas de solicitud
    pn2 = pn
    for w in ["rvoe", "pasame", "pasa", "dame", "necesito", "quiero", "numero", "del", "de", "la", "el", "los", "las"]:
        pn2 = re.sub(rf"\b{re.escape(w)}\b", " ", pn2)

    # quitar plantel detectado del texto
    if plantel:
        for a in PLANTELES.get(plantel, []):
            pn2 = pn2.replace(normalizar(a), " ")

    # quitar incorporacion detectada
    if incorporacion:
        for a in INCORPORACIONES.get(incorporacion, []):
            pn2 = pn2.replace(normalizar(a), " ")

    pn2 = re.sub(r"\s+", " ", pn2).strip()
    carrera = limpiar_grado(pn2)  # quita licenciatura/ingenieria etc

    if not carrera:
        carrera = None

    return plantel, incorporacion, carrera

# ==========================================================
# MATCH INTELIGENTE (BUSCAR CARRERA EN PLANTEL)
# ==========================================================
def buscar_rvoe_especifico(estructura_rvoe, carrera_txt, plantel, incorporacion):
    if not plantel or plantel not in estructura_rvoe:
        return [], []

    carrera_norm = normalizar(carrera_txt or "")
    carrera_norm = aplicar_sinonimos(carrera_norm)
    carrera_core = limpiar_grado(carrera_norm)

    tokens_full = set(tokenizar(carrera_norm))
    tokens_core = set(tokenizar(carrera_core))

    candidatos = []
    rank = []

    for item in estructura_rvoe[plantel]:
        if incorporacion and incorporacion.upper() not in item["incorporacion"].upper():
            continue

        prog_norm = item["programa_norm"]
        prog_core = item["programa_core"]

        tokens_prog = set(tokenizar(prog_norm))
        tokens_prog_core = set(tokenizar(prog_core))

        comunes_full = tokens_full & tokens_prog
        comunes_core = tokens_core & tokens_prog_core

        cobertura_full = len(comunes_full) / max(1, len(tokens_full))
        cobertura_core = len(comunes_core) / max(1, len(tokens_core))

        fuzzy_full = similitud(carrera_norm, prog_norm)
        fuzzy_core = similitud(carrera_core, prog_core)

        # pesos
        score = 0
        score += len(comunes_full) * 18
        score += len(comunes_core) * 28
        score += cobertura_full * 60
        score += cobertura_core * 95
        score += fuzzy_full * 55
        score += fuzzy_core * 90

        candidatos.append((score, item))
        rank.append((score, item))

    candidatos.sort(reverse=True, key=lambda x: x[0])
    rank.sort(reverse=True, key=lambda x: x[0])

    sugerencias = [it for _, it in rank[:6]]

    mejores = []
    if candidatos:
        top = candidatos[0][0]
        for s, it in candidatos:
            if s >= max(160, top * 0.83):
                mejores.append(it)

    return mejores, sugerencias

# ==========================================================
# LISTADOS INTELIGENTES
# ==========================================================
def filtrar_listado(estructura_rvoe, plantel, incorporacion=None, nivel=None):
    if not plantel or plantel not in estructura_rvoe:
        return []
    items = estructura_rvoe[plantel]
    if incorporacion:
        items = [x for x in items if incorporacion.upper() in x["incorporacion"].upper()]
    if nivel:
        items = [x for x in items if x["nivel"] == nivel]
    return items

# ==========================================================
# COMANDOS RÁPIDOS (operación)
# ==========================================================
def ayuda():
    return (
        f"🤖 {NOMBRE_ASISTENTE} | Comandos rápidos\n\n"
        "✅ Consultas RVOE (orden libre):\n"
        "• rvoe administracion udg zapopan\n"
        "• pasame rvoe bg americas\n"
        "• rvoe sep campus negocios digitales\n\n"
        "📍 Listados:\n"
        "• lista rvoe zapopan\n"
        "• lista rvoe campus udg\n"
        "• lista rvoe americas sep\n\n"
        "🧠 Follow-up (memoria):\n"
        "• y en campus?\n"
        "• ahora en sep\n"
        "• en zapopan\n\n"
        "🛠️ Modos:\n"
        "• modo wpp / modo llamada / modo normal\n"
        "• corto (antes de la pregunta)\n"
        "• completo (antes de la pregunta)\n\n"
        "Ejemplo:\n"
        "• corto rvoe admin udg zapopan\n"
        "• wpp rvoe bg americas\n"
    )

def listar_planteles():
    lines = ["📍 Planteles reconocidos:"]
    for p in PLANTELES.keys():
        lines.append(f"• {titulo_plantel(p)}")
    return "\n".join(lines)

def listar_incorporaciones():
    lines = ["🏛️ Incorporaciones reconocidas:"]
    for k in INCORPORACIONES.keys():
        lines.append(f"• {k}")
    return "\n".join(lines)

# ==========================================================
# RESPUESTA PRINCIPAL PARA RVOE
# ==========================================================
def responder_rvoe(pregunta: str, doc_rvoe: dict, cache_estructura: dict) -> str:
    pn = aplicar_sinonimos(normalizar(pregunta))

    # 1) Modos (persistentes)
    nuevo_modo = detectar_modo(pn)
    if nuevo_modo:
        STATE.last_mode = nuevo_modo
        guardar_state()
        return f"✅ Modo activado: **{STATE.last_mode.upper()}**"

    nuevo_detalle = detectar_detalle(pn)
    if nuevo_detalle:
        STATE.last_detail = nuevo_detalle
        # quitar la palabra "corto/completo" para que siga la pregunta
        pn = pn.replace(nuevo_detalle, "").strip()
        guardar_state()

    # 2) audiencia
    audiencia = detectar_audiencia(pn)
    STATE.last_audiencia = audiencia

    # 3) selección por número
    if es_seleccion_numero(pn) and STATE.last_options:
        elegido = resolver_seleccion_numero(pn)
        if not elegido:
            return f"{intro_personalizada(STATE.last_audiencia)}\n\n❌ Ese número no existe. Escribe 1, 2, 3..."
        plantel = STATE.last_plantel
        rvoe_principal = elegido["rvoe"]
        rvoes_extra = [x for x in elegido.get("rvoes", []) if x != rvoe_principal]
        return (
            f"{intro_personalizada(STATE.last_audiencia)}\n\n" +
            responder_formato(
                STATE.last_mode,
                STATE.last_detail,
                plantel,
                elegido["programa"],
                elegido["incorporacion"],
                rvoe_principal,
                rvoes_extra
            )
        )

    # 4) Parseo cache
    if doc_rvoe["archivo"] not in cache_estructura:
        cache_estructura[doc_rvoe["archivo"]] = parsear_rvoe(doc_rvoe["contenido"])
    estructura = cache_estructura[doc_rvoe["archivo"]]

    # 5) intención
    intent = detectar_intencion_rvoe(pn)

    # 6) menú
    if intent == "menu":
        STATE.last_menu = True
        STATE.last_options = []
        return menu_rvoe()

    # 7) si venimos de menú y responde 1-5
    if STATE.last_menu and es_seleccion_numero(pn):
        n = int(pn.strip())
        STATE.last_menu = False
        if n == 4:
            return f"{intro_personalizada(audiencia)}\n\n{respuesta_definicion_rvoe(audiencia)}"
        if n == 5:
            return f"{intro_personalizada(audiencia)}\n\n{respuesta_comparativa_udg_sep()}"
        return (
            f"{intro_personalizada(audiencia)}\n\n"
            "Perfecto ✅\n"
            "Escríbeme así:\n"
            "👉 *rvoe (carrera) (udg/sep) (plantel)*\n"
            "Ejemplos:\n"
            "• rvoe administracion udg zapopan\n"
            "• lista rvoe campus sep"
        )

    if intent == "definicion":
        STATE.last_options = []
        return f"{intro_personalizada(audiencia)}\n\n{respuesta_definicion_rvoe(audiencia)}"

    if intent == "comparar":
        STATE.last_options = []
        return f"{intro_personalizada(audiencia)}\n\n{respuesta_comparativa_udg_sep()}"

    # 8) Extraer entidades orden libre (y usar memoria si faltan)
    plantel, incorporacion, carrera = extraer_entidades_orden_libre(pn)

    plantel = plantel or STATE.last_plantel
    incorporacion = incorporacion or STATE.last_incorporacion
    carrera = carrera or STATE.last_carrera

    # persistir memoria
    STATE.last_plantel = plantel
    STATE.last_incorporacion = incorporacion
    STATE.last_carrera = carrera
    guardar_state()

    # DEBUG
    if DEBUG:
        print("\n🧪 DEBUG")
        print("pn:", pn)
        print("intent:", intent)
        print("plantel:", plantel)
        print("incorp:", incorporacion)
        print("carrera:", carrera)
        print("mode:", STATE.last_mode, "detail:", STATE.last_detail, "aud:", STATE.last_audiencia)

    # 9) LISTAR
    if intent == "listar":
        if not plantel:
            return (
                f"{intro_personalizada(audiencia)}\n\n"
                "✅ Para listar RVOE necesito el **plantel**.\n"
                "Ejemplo:\n"
                "👉 lista rvoe zapopan"
            )

        nivel = detectar_nivel(pn)
        items = filtrar_listado(estructura, plantel, incorporacion=incorporacion, nivel=nivel)

        if not items:
            msg = [
                f"{intro_personalizada(audiencia)}",
                f"🏫 **{titulo_plantel(plantel)}**",
                "",
                "❌ No encontré programas con ese filtro.",
            ]
            if incorporacion:
                msg.append(f"🏛️ Incorporación: **{incorporacion}**")
            if nivel:
                msg.append(f"🎓 Nivel: **{nivel}**")
            msg.append("\n📌 Tip: intenta sin el filtro.")
            return "\n".join(msg)

        header = f"📍 **Listado de RVOE – {titulo_plantel(plantel)}**"
        if incorporacion:
            header += f" | 🏛️ {incorporacion}"
        if nivel:
            header += f" | 🎓 {nivel.upper()}"

        lineas = [header, ""]
        for it in items:
            rvoe_principal = it["rvoe"]
            extras = [x for x in it.get("rvoes", []) if x != rvoe_principal]
            extra_txt = f" (Otros: {', '.join(extras)})" if extras and STATE.last_detail == "completo" else ""
            lineas.append(f"• 🎓 {it['programa']} | 🏛️ {it['incorporacion']} | 📄 {rvoe_principal}{extra_txt}")

        STATE.last_options = []
        return f"{intro_personalizada(audiencia)}\n\n" + "\n".join(lineas)

    # 10) BUSCAR UNO
    if not plantel:
        return (
            f"{intro_personalizada(audiencia)}\n\n"
            "✅ Para pasarte el RVOE exacto dime el **plantel**.\n"
            "Ejemplo:\n"
            "👉 rvoe administracion udg zapopan"
        )

    if not carrera:
        return (
            f"{intro_personalizada(audiencia)}\n\n"
            "✅ Para pasarte el RVOE exacto dime la **carrera**.\n"
            "Ejemplo:\n"
            "👉 rvoe bg americas"
        )

    mejores, sugerencias = buscar_rvoe_especifico(estructura, carrera, plantel, incorporacion)

    # no match exacto → sugerencias
    if not mejores:
        msg = [
            f"{intro_personalizada(audiencia)}",
            f"🏫 **{titulo_plantel(plantel)}**",
            "",
            f"❌ No encontré match exacto para: **{carrera.upper()}**"
        ]
        if incorporacion:
            msg.append(f"🏛️ Incorporación solicitada: **{incorporacion}**")

        msg.append("")
        msg.append("✅ Opciones más parecidas (elige un número):")

        STATE.last_options = sugerencias[:6]
        for i, it in enumerate(STATE.last_options, start=1):
            msg.append(f"{i}) 🎓 {it['programa']} | 🏛️ {it['incorporacion']} | 📄 {it['rvoe']}")

        msg.append("\n📌 Responde con 1, 2, 3... y listo ✅")
        return "\n".join(msg)

    # múltiples → opciones
    if len(mejores) > 1:
        msg = [
            f"{intro_personalizada(audiencia)}",
            f"🏫 **{titulo_plantel(plantel)}**",
            "",
            "Encontré más de una coincidencia ✅ (elige un número):",
            ""
        ]
        STATE.last_options = mejores[:8]
        for i, it in enumerate(STATE.last_options, start=1):
            msg.append(f"{i}) 🎓 {it['programa']} | 🏛️ {it['incorporacion']} | 📄 {it['rvoe']}")

        msg.append("\n📌 Responde con 1, 2, 3... y listo.")
        return "\n".join(msg)

    # único resultado
    it = mejores[0]
    STATE.last_options = []

    rvoe_principal = it["rvoe"]  # ya es el más nuevo por agrupación
    rvoes_extra = [x for x in it.get("rvoes", []) if x != rvoe_principal]

    return (
        f"{intro_personalizada(audiencia)}\n\n" +
        responder_formato(
            STATE.last_mode,
            STATE.last_detail,
            plantel,
            it["programa"],
            it["incorporacion"],
            rvoe_principal,
            rvoes_extra
        )
    )

# ==========================================================
# MAIN
# ==========================================================
def main():
    cargar_state()
    docs = cargar_docs()
    cache_estructura = {}

    print(f"\n🤖 {NOMBRE_ASISTENTE} | Asistente operativo UTEG (PRO MAX v2)")
    print(f"📚 Archivos cargados: {len(docs)}")
    print(f"⚙️ Modo: {STATE.last_mode.upper()} | Detalle: {STATE.last_detail.upper()}")
    print("Escribe SALIR para terminar\n")

    while True:
        pregunta = input("👉 Pregunta: ").strip()
        if not pregunta:
            continue

        pn = normalizar(pregunta)

        # salida
        if pn == "salir":
            guardar_state()
            print("👋 Hasta luego")
            break

        # comandos globales
        if pn in {"ayuda", "help", "comandos"}:
            print("\n" + "-" * 70)
            print(ayuda())
            print("-" * 70)
            continue

        if pn in {"planteles", "lista planteles"}:
            print("\n" + "-" * 70)
            print(listar_planteles())
            print("-" * 70)
            continue

        if pn in {"incorporaciones", "lista incorporaciones"}:
            print("\n" + "-" * 70)
            print(listar_incorporaciones())
            print("-" * 70)
            continue

        # encontrar doc
        doc = buscar_doc_ranking(pregunta, docs)

        if not doc:
            print("\n❌ No encontré un documento que coincida.\n👉 Tip: escribe ayuda\n")
            continue

        # Motor RVOE
        if "rvoe" in doc.get("intencion", "") or "rvoe" in doc.get("contenido_norm", ""):
            respuesta = responder_rvoe(pregunta, doc, cache_estructura)
            print("\n" + "-" * 70)
            print(respuesta)
            print("-" * 70)
        else:
            # fallback: imprime contenido doc
            print(f"\n📄 DOCS.{doc['archivo'].upper()}")
            print("-" * 70)
            print(doc["contenido"])
            print("-" * 70)

if __name__ == "__main__":
    main()
