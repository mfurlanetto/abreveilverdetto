"""Rigenera data/mountains.json da Wikidata (dati CC0, nessun obbligo di attribuzione).

Seleziona le montagne e i vulcani (P31 = Q8502 montagna, Q8072 vulcano,
Q169358 stratovulcano) che hanno altitudine (P2044), una foto (P18) e una voce
su Wikipedia in italiano. Per ognuna salva: titolo della voce italiana,
altitudine in metri, nazioni (P17) e catena montuosa (P4552) con etichette in
italiano, nome del file della foto su Wikimedia Commons.

Descrizione, foto e licenza della foto si leggono a runtime da Wikipedia
(vedi abreveilverdetto/mountains.py): qui solo i dati strutturati.

Query service: https://query.wikidata.org (limite 60 s per query; vedi
https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual).

Uso: python scripts/build_mountains.py   (richiede rete verso query.wikidata.org)
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "mountains.json"
ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "abreveilverdetto-build/1.0 (https://github.com/mfurlanetto/abreveilverdetto)"
CLASSES = ("wd:Q8502", "wd:Q8072", "wd:Q169358")

# Query piccole: una per classe con i soli dati di base, poi voci italiane, nazioni,
# catene ed etichette per lotti di ID. Le query uniche superano il limite di 60 secondi
# del query service (HTTP 504 o risposta troncata, verificato il 21/11/2026).
BASE_QUERY = """
SELECT ?m ?h ?img WHERE {
  ?m wdt:P31 %(cls)s ; wdt:P18 ?img ; p:P2044 ?st .
  ?st a wikibase:BestRank ; psn:P2044/wikibase:quantityAmount ?h .
}
"""
TITLES_QUERY = """
SELECT ?m ?title WHERE {
  VALUES ?m { %(ids)s }
  ?article schema:about ?m ; schema:isPartOf <https://it.wikipedia.org/> ; schema:name ?title .
}
"""
# Nazioni e catene per lotti di vette già selezionate: su tutta la classe la query
# supera il limite e il servizio tronca la risposta a metà.
LINKS_QUERY = """
SELECT ?m ?c ?r WHERE {
  VALUES ?m { %(ids)s }
  OPTIONAL { ?m wdt:P17 ?c }
  OPTIONAL { ?m wdt:P4552 ?r }
}
"""
LABELS_QUERY = """
SELECT ?x ?label WHERE {
  VALUES ?x { %(ids)s }
  ?x rdfs:label ?label . FILTER(LANG(?label) = "it")
}
"""
BATCH = 400


def run_query(query: str, attempts: int = 3) -> list[dict[str, dict[str, str]]]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    headers = {"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310 - URL costante
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310 - URL costante
                return json.load(response)["results"]["bindings"]
        except (urllib.error.URLError, json.JSONDecodeError) as exc:  # 5xx, timeout, risposta troncata
            if attempt == attempts:
                raise
            print(f"Query fallita ({exc}), nuovo tentativo tra {10 * attempt} s", file=sys.stderr)
            time.sleep(10 * attempt)
    raise AssertionError("irraggiungibile")


def entity_id(binding: dict[str, str]) -> str:
    return binding["value"].rsplit("/", 1)[1]


def batches(ids: set[str]) -> list[str]:
    """Insiemi di ID -> blocchi "wd:Q1 wd:Q2 ..." per le clausole VALUES."""
    ordered = sorted(ids)
    return [" ".join(f"wd:{x}" for x in ordered[i : i + BATCH]) for i in range(0, len(ordered), BATCH)]


def labels(ids: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for values in batches(ids):
        for row in run_query(LABELS_QUERY % {"ids": values}):
            result[entity_id(row["x"])] = row["label"]["value"]
    return result


def file_name(commons_url: str) -> str:
    """'http://commons.wikimedia.org/wiki/Special:FilePath/Monte%20Bianco.jpg' -> 'Monte Bianco.jpg'."""
    return urllib.parse.unquote(commons_url.rsplit("/", 1)[1])


def main() -> int:
    by_id: dict[str, dict] = {}
    countries: dict[str, set[str]] = {}
    ranges: dict[str, set[str]] = {}
    for cls in CLASSES:
        rows = run_query(BASE_QUERY % {"cls": cls})
        print(f"{cls}: {len(rows)} righe", file=sys.stderr)
        for row in rows:
            qid = entity_id(row["m"])
            elevation = round(float(row["h"]["value"]))
            # Quote fuori scala (errori di unità su Wikidata) o nulle: scartate.
            if not 0 < elevation <= 8849:
                continue
            # Solo le altitudini di rango migliore (BestRank: "preferred" se c'è, altrimenti
            # "normal"); se restano più valori o più foto si tiene la quota più alta.
            if qid not in by_id or elevation > by_id[qid]["elevation"]:
                by_id[qid] = {"id": qid, "elevation": elevation, "image": file_name(row["img"]["value"])}

    titles = {}
    for values in batches(set(by_id)):
        for row in run_query(TITLES_QUERY % {"ids": values}):
            titles[entity_id(row["m"])] = row["title"]["value"]
    by_id = {qid: {**item, "title": titles[qid]} for qid, item in by_id.items() if qid in titles}
    print(f"{len(by_id)} con voce su it.wikipedia", file=sys.stderr)

    for values in batches(set(by_id)):
        for row in run_query(LINKS_QUERY % {"ids": values}):
            qid = entity_id(row["m"])
            if "c" in row:
                countries.setdefault(qid, set()).add(entity_id(row["c"]))
            if "r" in row:
                ranges.setdefault(qid, set()).add(entity_id(row["r"]))

    wanted = {x for qid in by_id for x in countries.get(qid, set()) | ranges.get(qid, set())}
    names = labels(wanted)
    for qid, item in by_id.items():
        item["countries"] = sorted({names[c] for c in countries.get(qid, ()) if c in names})
        item["ranges"] = sorted({names[r] for r in ranges.get(qid, ()) if r in names})

    fields = ("id", "title", "elevation", "countries", "ranges", "image")
    mountains = sorted(
        ({k: item[k] for k in fields} for item in by_id.values()), key=lambda m: (-m["elevation"], m["title"])
    )
    # Una montagna per riga: file compatto ma con diff leggibili a ogni rigenerazione.
    lines = ",\n".join(json.dumps(m, ensure_ascii=False, separators=(",", ":")) for m in mountains)
    OUTPUT.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    print(f"{len(mountains)} montagne in {OUTPUT.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
