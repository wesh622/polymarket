"""Journal d'audit append-only.

Chaque action (autorisée, bloquée, échouée) laisse une trace horodatée et
chaînée : chaque entrée embarque le hash de la précédente, de sorte qu'une
modification ou une suppression a posteriori devient détectable (``verifier``).

L'application n'ouvre le fichier qu'en ajout (``"a"``) et ne réécrit jamais une
ligne existante.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

GENESIS = "0" * 64


def _hash(payload: str, precedent: str) -> str:
    return hashlib.sha256(f"{precedent}{payload}".encode("utf-8")).hexdigest()


@dataclass
class AuditLog:
    chemin: str
    operateur: str

    def __post_init__(self) -> None:
        os.makedirs(os.path.dirname(self.chemin) or ".", exist_ok=True)

    def _dernier_hash(self) -> str:
        dernier = GENESIS
        if not os.path.exists(self.chemin):
            return dernier
        with open(self.chemin, "r", encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if ligne:
                    dernier = json.loads(ligne)["hash"]
        return dernier

    def enregistrer(
        self,
        action: str,
        cible: str,
        resultat: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ajoute une entrée. Retourne l'entrée écrite (avec son hash)."""
        precedent = self._dernier_hash()
        corps = {
            "horodatage": datetime.now(timezone.utc).isoformat(),
            "operateur": self.operateur,
            "action": action,
            "cible": cible,
            "resultat": resultat,
            "details": details or {},
            "precedent": precedent,
        }
        payload = json.dumps(corps, sort_keys=True, ensure_ascii=False)
        entree = {**corps, "hash": _hash(payload, precedent)}
        with open(self.chemin, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entree, sort_keys=True, ensure_ascii=False) + "\n")
        return entree

    def verifier(self) -> bool:
        """Vérifie l'intégrité de la chaîne. ``False`` = journal altéré."""
        precedent = GENESIS
        if not os.path.exists(self.chemin):
            return True
        with open(self.chemin, "r", encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                entree = json.loads(ligne)
                attendu = entree.pop("hash")
                if entree["precedent"] != precedent:
                    return False
                payload = json.dumps(entree, sort_keys=True, ensure_ascii=False)
                if _hash(payload, precedent) != attendu:
                    return False
                precedent = attendu
        return True
