"""Contenuti statici: frasi JSON in data/ e immagini in media/.

Tutto viene letto una volta sola all'avvio, così un file mancante o malformato
fa fallire subito il deploy invece di un comando a caso in produzione.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import DATA_DIR, MEDIA_DIR

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

TEXT_LISTS = ("saluti", "conte", "cts_list", "dpcm", "ghesboro", "giurato", "lercio", "santi_frasi")

MAGIC_DECKS = {
    "special": ("⭐", "Special", "magic_cards/special"),
    "artifact": ("💎", "Artifact", "magic_cards/artifacts"),
    "creature": ("🦄", "Creature", "magic_cards/creatures"),
    "land": ("⛰", "Land", "magic_cards/lands"),
    "sorcery": ("🪄", "Sorcery", "magic_cards/sorceries"),
}


def _load_json(name: str, data_dir: Path) -> Any:
    with (data_dir / f"{name}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _list_images(directory: Path) -> list[Path]:
    images = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise FileNotFoundError(f"Nessuna immagine in {directory}")
    return images


@dataclass(frozen=True)
class Content:
    texts: dict[str, list[str]]
    santi: list[dict[str, str]]
    regions: list[dict[str, Any]]
    countries: list[dict[str, Any]]
    images: dict[str, list[Path]]
    media_dir: Path

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR, media_dir: Path = MEDIA_DIR) -> Content:
        texts = {name: _load_json(name, data_dir) for name in TEXT_LISTS}
        for name, items in texts.items():
            if not items or not all(isinstance(i, str) for i in items):
                raise ValueError(f"data/{name}.json deve essere una lista non vuota di stringhe")

        santi = _load_json("santi", data_dir)
        for santo in santi:
            photo = media_dir / "santi" / f"{santo['photo']}.jpg"
            if not photo.is_file():
                raise FileNotFoundError(photo)

        image_dirs = ["tortamele", "conte", "bimbe"] + [d for _, _, d in MAGIC_DECKS.values()]
        images = {d: _list_images(media_dir / d) for d in image_dirs}

        return cls(
            texts=texts,
            santi=santi,
            regions=_load_json("regions_ita", data_dir),
            countries=_load_json("countries", data_dir),
            images=images,
            media_dir=media_dir,
        )

    def pick_text(self, name: str, rng: random.Random) -> str:
        return rng.choice(self.texts[name])

    def pick_image(self, directory: str, rng: random.Random) -> Path:
        return rng.choice(self.images[directory])

    def media(self, relative: str) -> Path:
        return self.media_dir / relative

    def country_by_code(self, cca3: str) -> dict[str, Any] | None:
        return next((c for c in self.countries if c["cca3"] == cca3), None)

    def severity_color(self, region_name: str, province_name: str) -> str | None:
        """Colore della zona COVID (dati statici storici, inverno 2020-21)."""
        region = next((r for r in self.regions if r["name"] == region_name), None)
        if region is None:
            return None
        if "province" in region:
            province = next((p for p in region["province"] if p["name"] == province_name), None)
            return province["covid_severity_color"] if province else None
        return region.get("covid_severity_color")
