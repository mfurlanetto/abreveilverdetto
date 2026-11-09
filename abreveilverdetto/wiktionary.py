"""Estrazione delle definizioni italiane dal wikitext del Wikizionario (it.wiktionary.org).

Il wikitext è pensato per essere letto da MediaWiki, non da un programma: qui si
ricava una versione testuale "abbastanza buona" delle definizioni. Le regole sono
ricavate da voci reali (vedi tests/data/wiktionary_samples.json):

    == {{-it-}} ==                 sezione della lingua italiana
    {{-sost-|it}}                  categoria grammaticale (con |it)
    # [[edificio]] per abitare     definizione
    #* ''una bella casa''          esempio (in corsivo): ignorato
    {{-sill-}} {{-etim-}} ...      sezioni accessorie (senza |it): fine delle definizioni

I contenuti del Wikizionario sono rilasciati con licenza CC BY-SA 4.0:
chi li mostra deve citare la fonte e la licenza.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from urllib.parse import quote

BASE_URL = "https://it.wiktionary.org/wiki/"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/deed.it"

# Codici delle categorie grammaticali visti nelle voci; i codici sconosciuti
# vengono mostrati così come sono.
POS_LABELS = {
    "sost": "sostantivo",
    "sost form": "sostantivo (forma flessa)",
    "verb": "verbo",
    "verb form": "voce verbale",
    "agg": "aggettivo",
    "agg form": "aggettivo (forma flessa)",
    "avv": "avverbio",
    "nome": "nome proprio",
    "loc nom": "locuzione nominale",
    "loc verb": "locuzione verbale",
    "loc agg": "locuzione aggettivale",
    "loc avv": "locuzione avverbiale",
    "inter": "interiezione",
    "art": "articolo",
    "prep": "preposizione",
    "cong": "congiunzione",
    "pron": "pronome",
    "suff": "suffisso",
    "pref": "prefisso",
    "acron": "acronimo",
    "sigla": "sigla",
    "abbr": "abbreviazione",
}

# Template di registro/uso che compaiono all'inizio delle definizioni.
LABEL_TEMPLATES = {
    "fig": "figurato",
    "est": "per estensione",
    "vulg": "volgare",
    "lett": "letterario",
    "raro": "raro",
    "disus": "disusato",
    "spreg": "spregiativo",
    "fam": "familiare",
    "scherz": "scherzoso",
    "pop": "popolare",
    "region": "regionale",
    "arc": "arcaico",
    "antiq": "antiquato",
    "iperb": "iperbolico",
    "eufem": "eufemistico",
}

_LANG_HEADER = re.compile(r"^==\s*\{\{-it-\}\}\s*==\s*$", re.M)
_LEVEL2_HEADER = re.compile(r"^==[^=].*$", re.M)
_SECTION_TEMPLATE = re.compile(r"^\s*\{\{-([^|{}]+)-(\|[^{}]*)?\}\}\s*$")
_INNER_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")
_FILE_LINK = re.compile(r"\[\[(?:File|Immagine|Image|Categoria|Category):", re.I)
_LINK = re.compile(r"\[\[([^\[\]|]*)(?:\|([^\[\]]*))?\]\]")
_EXTERNAL_LINK = re.compile(r"\[https?://\S+(?:\s+([^\]]*))?\]")
_REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


@dataclass(frozen=True)
class Sense:
    pos: str
    definitions: tuple[str, ...]


@dataclass(frozen=True)
class Entry:
    title: str
    senses: tuple[Sense, ...] = field(default_factory=tuple)

    @property
    def url(self) -> str:
        return BASE_URL + quote(self.title.replace(" ", "_"))

    def has_definitions(self) -> bool:
        return any(s.definitions for s in self.senses)


def _remove_file_links(text: str) -> str:
    """Toglie [[File:…]] e [[Categoria:…]], che possono contenere link annidati."""
    while (m := _FILE_LINK.search(text)) is not None:
        depth, i = 0, m.start()
        while i < len(text) - 1:
            pair = text[i : i + 2]
            if pair == "[[":
                depth += 1
                i += 2
            elif pair == "]]":
                depth -= 1
                i += 2
                if depth == 0:
                    break
            else:
                i += 1
        text = text[: m.start()] + text[i:]
    return text


def _render_template(body: str, title: str) -> str:
    parts = [p.strip() for p in body.split("|")]
    name = parts[0].strip().lower()
    if name == "pn":
        return title
    if name == "term" and len(parts) > 1 and parts[1]:
        return f"({parts[1]})"
    if name in LABEL_TEMPLATES:
        return f"({LABEL_TEMPLATES[name]})"
    return ""  # template di servizio o sconosciuto: meglio niente che codice


def clean(text: str, title: str) -> str:
    """Wikitext di una riga -> testo semplice."""
    text = _COMMENT.sub("", text)
    text = _REF.sub("", text)
    text = _remove_file_links(text)
    # Template dall'interno verso l'esterno, per gestire quelli annidati.
    for _ in range(10):
        new = _INNER_TEMPLATE.sub(lambda m: _render_template(m.group(1), title), text)
        if new == text:
            break
        text = new
    text = _LINK.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(1).split("#")[0], text)
    text = _EXTERNAL_LINK.sub(lambda m: m.group(1) or "", text)
    text = text.replace("'''", "").replace("''", "")
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    return text


def _italian_section(wikitext: str) -> str | None:
    start = _LANG_HEADER.search(wikitext)
    if start is None:
        return None
    rest = wikitext[start.end() :]
    end = _LEVEL2_HEADER.search(rest)
    return rest[: end.start()] if end else rest


def _is_definition_line(line: str) -> bool:
    # "# testo" o "#testo", e anche "#* testo" (alcune voci, come "casa", mettono lì le definizioni);
    # non "#**", "#:" e simili, che sono esempi o note.
    return bool(re.match(r"^#(?:\*(?![*:]))?(?![#*:])", line))


def _is_example(raw: str) -> bool:
    body = raw.lstrip("#*").strip()
    return body.startswith("''")


def parse(title: str, wikitext: str) -> Entry:
    section = _italian_section(wikitext)
    if section is None:
        return Entry(title)

    senses: list[Sense] = []
    pos: str | None = None
    definitions: list[str] = []

    def flush() -> None:
        if pos is not None and definitions:
            senses.append(Sense(pos, tuple(definitions)))

    for line in section.splitlines():
        header = _SECTION_TEMPLATE.match(line)
        if header:
            flush()
            definitions = []
            code, args = header.group(1).strip(), header.group(2) or ""
            # {{-sost-|it}} è una categoria grammaticale; {{-etim-}}, {{-sill-}}… no
            pos = POS_LABELS.get(code, code) if args.strip("|").strip() == "it" else None
            continue
        if pos is None or not _is_definition_line(line) or _is_example(line):
            continue
        raw = re.sub(r"^#\*?", "", line)
        if raw.lstrip().lower().startswith("{{pn"):
            continue  # riga di flessione ("{{Pn|w}} ''f sing''"), non una definizione
        text = clean(raw, title)
        if len(text) >= 2 and any(c.isalpha() for c in text):
            definitions.append(text)
    flush()
    return Entry(title, tuple(senses))
