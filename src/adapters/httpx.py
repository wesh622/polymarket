"""Adaptateur httpx (ProjectDiscovery) — sonde HTTP, phase recon/web.

Détermine si une cible répond en HTTP(S) et avec quel statut/techno. Sert à
décider si la phase web doit être déclenchée (§6.1 du cahier).
"""

from __future__ import annotations

import json
from typing import Any

from adapters.base import BaseAdapter


class HttpxAdapter(BaseAdapter):
    binaire = "httpx"
    intensite = "normale"

    def construire_commande(self, cible: str, **options: Any) -> list[str]:
        # -json : une ligne JSON par URL ; -silent : pas de bannière.
        return [self.binaire, "-u", cible, "-json", "-silent", "-status-code", "-title", "-tech-detect"]

    def parser(self, stdout: str, stderr: str, code: int) -> dict[str, Any]:
        resultat: dict[str, Any] = {"outil": "httpx", "urls": []}
        for ligne in stdout.splitlines():
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                obj = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            resultat["urls"].append(
                {
                    "url": obj.get("url") or obj.get("input"),
                    "statut": obj.get("status_code") or obj.get("status-code"),
                    "titre": obj.get("title"),
                    "technos": obj.get("tech") or obj.get("technologies") or [],
                }
            )
        if not resultat["urls"] and stderr.strip():
            resultat["erreur"] = stderr.strip()
        return resultat
