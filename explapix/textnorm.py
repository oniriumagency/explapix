"""Texto para la voz: normaliza (números, unidades, siglas) y lo parte en frases con su pausa.

Chatterbox lee de corrido e ignora la puntuación, así que sintetizamos frase por frase e
insertamos silencios explícitos según el signo que la cierra.
"""
from __future__ import annotations

import re

from num2words import num2words

PAUSES = {",": 0.18, ".": 0.35, ";": 0.35, ":": 0.35, "?": 0.45, "!": 0.45, "…": 0.4}
END_PAUSE = 0.5

ABBR = [
    (r"\bp\.\s?ej\.", "por ejemplo"), (r"\baprox\.", "aproximadamente"), (r"\betc\.", "etcétera"),
    (r"\bEE\.\s?UU\.", "Estados Unidos"), (r"\bDr\.", "doctor"), (r"\bDra\.", "doctora"),
    (r"\bvs\.?", "contra"), (r"\bnúm\.", "número"),
]
UNITS = [
    (r"(\d)\s?°\s?C\b", r"\1 grados"), (r"(\d)\s?°\s?F\b", r"\1 grados Fahrenheit"), (r"(\d)\s?°", r"\1 grados"),
    (r"(\d)\s?%", r"\1 por ciento"), (r"(\d)\s?km/h\b", r"\1 kilómetros por hora"),
    (r"(\d)\s?km\b", r"\1 kilómetros"), (r"(\d)\s?cm\b", r"\1 centímetros"), (r"(\d)\s?mm\b", r"\1 milímetros"),
    (r"(\d)\s?kg\b", r"\1 kilos"), (r"(\d)\s?g\b", r"\1 gramos"), (r"(\d)\s?GHz\b", r"\1 gigahercios"),
    (r"(\d)\s?MHz\b", r"\1 megahercios"), (r"(\d)\s?kWh\b", r"\1 kilovatios hora"), (r"(\d)\s?W\b", r"\1 vatios"),
    (r"(\d)\s?m/s\b", r"\1 metros por segundo"), (r"(\d)\s?m\b", r"\1 metros"), (r"(\d)\s?s\b", r"\1 segundos"),
    (r"(\d)\s?[x×]\b", r"\1 veces"), (r"~\s?", "unos "),
]
ACRONYMS = {
    "GPS": "ge pe ese", "QR": "cu erre", "UV": "u ve", "UVA": "u ve a", "UVB": "u ve be", "ADN": "a de ene",
    "ARN": "a erre ene", "NFC": "ene efe ce", "CO2": "ce o dos", "CO₂": "ce o dos", "USB": "u ese be",
    "IA": "i a", "LCD": "ele ce de", "SPF": "ese pe efe", "FPS": "efe pe ese", "CDMX": "Ciudad de México",
    "SASMEX": "sasmex", "TV": "tele",
}


def _num(m: re.Match) -> str:
    s = m.group(0)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):          # 5.000.000 -> 5000000
        return num2words(int(s.replace(".", "")), lang="es")
    if "," in s:                                        # decimales con coma: 2,45
        a, b = s.split(",", 1)
        return f"{num2words(int(a), lang='es')} coma {num2words(int(b), lang='es')}"
    return num2words(int(s), lang="es")


def normalize(text: str) -> str:
    t = " " + text.strip() + " "
    for pat, rep in ABBR:
        t = re.sub(pat, rep, t)
    for pat, rep in UNITS:
        t = re.sub(pat, rep, t)
    for k, v in ACRONYMS.items():
        t = re.sub(rf"(?<![\w]){re.escape(k)}(?![\w])", v, t)
    t = re.sub(r"\d{1,3}(?:\.\d{3})+|\d+,\d+|\d+", _num, t)
    t = t.replace("—", ", ").replace("–", ", ").replace("…", "…")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def chunks(text: str, min_words: int = 3) -> list[tuple[str, float]]:
    """[(frase, pausa_después)]. Corta en . ? ! ; : … y en comas cuando ambos lados son largos."""
    t = normalize(text)
    parts = re.findall(r"[^.?!;:…]+[.?!;:…]*", t)
    out: list[tuple[str, float]] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        end = p[-1] if p[-1] in PAUSES else "."
        sub = [s.strip() for s in re.split(r"(?<=,)\s+", p)]
        # une trozos de coma demasiado cortos con el siguiente
        merged, buf = [], ""
        for s in sub:
            buf = f"{buf} {s}".strip()
            if len(buf.split()) >= min_words or s is sub[-1]:
                merged.append(buf)
                buf = ""
        if buf:
            merged.append(buf)
        for k, s in enumerate(merged):
            last = k == len(merged) - 1
            pause = PAUSES.get(end, 0.35) if last else PAUSES[","]
            if s.startswith("¿") and not s.endswith("?") and last:
                s += "?"
            out.append((s, pause))
    if out:
        out[-1] = (out[-1][0], END_PAUSE)
    # frases de 1-2 palabras sueltas suenan raras: pégalas a la anterior
    fixed: list[tuple[str, float]] = []
    for s, pz in out:
        if fixed and len(s.split()) < 2:
            prev, _ = fixed[-1]
            fixed[-1] = (f"{prev} {s}", pz)
        else:
            fixed.append((s, pz))
    return fixed
