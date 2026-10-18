"""Adaptateur nikto — phase 5 (web), scan de mauvaises configs serveur.

nikto produit du JSON sur stdout via ``-Format json -output /dev/stdout``. On
normalise en liste d'items (id, méthode, URL, description).
"""

from __future__ import annotations

import json
from typing import Any

from adapters.base import BaseAdapter


class NiktoAdapter(BaseAdapter):
    binaire = "nikto"
    intensite = "normale"

    def construire_commande(self, cible: str, **options: Any) -> list[str]:
        return [self.binaire, "-h", cible, "-Format", "json", "-output", "/dev/stdout", "-nointeractive"]

    def parser(self, stdout: str, stderr: str, code: int) -> dict[str, Any]:
        resultat: dict[str, Any] = {"outil": "nikto", "items": []}
        stdout = stdout.strip()
        if not stdout:
            if stderr.strip():
                resultat["erreur"] = stderr.strip()
            return resultat
        try:
            obj = json.loads(stdout)
        except json.JSONDecodeError:
            # nikto peut émettre plusieurs objets ou du bruit ; on reste robuste.
            resultat["brut"] = stdout[:2000]
            return resultat
        # Le JSON nikto peut être une liste d'hôtes ou un objet unique.
        hotes = obj if isinstance(obj, list) else [obj]
        for hote in hotes:
            for v in hote.get("vulnerabilities", []) or []:
                resultat["items"].append(
                    {
                        "id": v.get("id"),
                        "methode": v.get("method"),
                        "url": v.get("url"),
                        "description": v.get("msg") or v.get("description"),
                    }
                )
        return resultat
