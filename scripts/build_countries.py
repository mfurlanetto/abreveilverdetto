"""Rigenera data/countries.json e media/flags/*.png.

Fonti:
- mledoze/countries (dataset da cui deriva REST Countries): nomi, traduzioni,
  capitali, regioni, valute, lingue, confini, area, bandiere SVG.
  https://github.com/mledoze/countries
- IANA tz database (zone1970.tab/zone.tab installato nel sistema): fusi orari per paese.
- samayo/country-json (NON ufficiale, dati World Bank ~2018): popolazione.
  https://github.com/samayo/country-json

Uso: python scripts/build_countries.py   (richiede rete e playwright;
     CHROMIUM_PATH opzionale per usare un Chromium già installato)
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MLEDOZE = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
FLAG_SVG = "https://raw.githubusercontent.com/mledoze/countries/master/data/{}.svg"
POPULATION = "https://raw.githubusercontent.com/samayo/country-json/master/src/country-by-population.json"
ZONE_TAB = Path("/usr/share/zoneinfo/zone.tab")
FLAG_WIDTH = 640


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - URL costanti
        return response.read()


def load_timezones() -> dict[str, list[str]]:
    zones: dict[str, list[str]] = {}
    for line in ZONE_TAB.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cc, _coords, tz, *_ = line.split("\t")
        zones.setdefault(cc, []).append(tz)
    return zones


class FlagRenderer:
    """Rende gli SVG delle bandiere in PNG con Chromium (Playwright).

    cairosvg non gestisce correttamente alcuni SVG del dataset (ricorsione su <use>,
    matrici non invertibili), quindi si usa un browser reale.
    """

    def __enter__(self) -> FlagRenderer:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        self._page = self._browser.new_page(viewport={"width": FLAG_WIDTH, "height": FLAG_WIDTH})
        return self

    def __exit__(self, *exc: object) -> None:
        self._browser.close()
        self._pw.stop()

    def render(self, svg: bytes, target: Path) -> None:
        src = "data:image/svg+xml;base64," + base64.b64encode(svg).decode()
        img = f"<img id='f' src='{src}' style='width:{FLAG_WIDTH}px;display:block'>"
        self._page.set_content(f"<html><body style='margin:0'>{img}</body></html>")
        self._page.wait_for_function("document.getElementById('f').complete")
        self._page.locator("#f").screenshot(path=str(target))


def main() -> int:
    countries = json.loads(fetch(MLEDOZE))
    population_raw = json.loads(fetch(POPULATION))
    population = {p["country"].casefold(): p["population"] for p in population_raw if p.get("population")}
    zones = load_timezones()

    flags_dir = ROOT / "media" / "flags"
    flags_dir.mkdir(parents=True, exist_ok=True)

    out = []
    unmatched = []
    missing_flags: list[tuple[str, Path]] = []
    for c in countries:
        cca3 = c["cca3"]
        names = {c["name"]["common"].casefold(), c["name"]["official"].casefold()}
        names |= {s.casefold() for s in c.get("altSpellings", [])}
        pop = next((population[n] for n in names if n in population), None)
        if pop is None:
            unmatched.append(c["name"]["common"])
        out.append(
            {
                "cca3": cca3,
                "name": c["name"]["common"],
                "name_it": c.get("translations", {}).get("ita", {}).get("common"),
                "capital": c.get("capital", []),
                "region": c.get("region", ""),
                "subregion": c.get("subregion", ""),
                "population": pop,
                "area": c.get("area"),
                "currencies": [{"code": k, "name": v.get("name", k)} for k, v in c.get("currencies", {}).items()],
                "languages": list(c.get("languages", {}).values()),
                "timezones": zones.get(c["cca2"], []),
                "borders": c.get("borders", []),
                "flag_emoji": c.get("flag", ""),
            }
        )
        png = flags_dir / f"{cca3.lower()}.png"
        if not png.exists():
            missing_flags.append((cca3, png))

    if missing_flags:
        with FlagRenderer() as renderer:
            for cca3, png in missing_flags:
                renderer.render(fetch(FLAG_SVG.format(cca3.lower())), png)

    out.sort(key=lambda x: x["cca3"])
    target = ROOT / "data" / "countries.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} paesi scritti in {target}; popolazione mancante per {len(unmatched)}:")
    print(", ".join(sorted(unmatched)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
