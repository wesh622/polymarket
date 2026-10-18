"""Moteur d'orchestration par phases.

Minimal pour l'instant : recon → scan. La logique inter-phases (§6.1) est déjà
amorcée — seules les cibles jugées vivantes par la recon sont scannées. L'état
de campagne est persisté en JSON pour permettre une reprise (FR-09).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from scope_guard import ScopeGuard
from audit_log import AuditLog
from phases import recon, scan, web, vuln

PHASES = ("recon", "scan", "web", "vuln")


def _repli(campagne: "Campagne") -> list[str]:
    """Cibles de repli : celles validées par la recon, sinon les cibles brutes."""
    return campagne.etat.get("recon", {}).get("cibles_valides", campagne.cibles)


@dataclass
class Campagne:
    nom: str
    cibles: list[str]
    intensite: str = "normale"
    etat: dict[str, Any] = field(default_factory=dict)

    def chemin_etat(self, dossier: str) -> str:
        slug = "".join(c if c.isalnum() else "_" for c in self.nom)
        return os.path.join(dossier, f"campagne_{slug}.json")


class Orchestrateur:
    def __init__(self, guard: ScopeGuard, audit: AuditLog, *, dossier_etat: str = "logs"):
        self._guard = guard
        self._audit = audit
        self._dossier = dossier_etat
        os.makedirs(dossier_etat, exist_ok=True)

    def lancer(
        self,
        campagne: Campagne,
        *,
        phases: tuple[str, ...] = PHASES,
        reprendre: bool = False,
        wordlist: str | None = None,
        sqlmap: bool = False,
        severite_min: str | None = None,
    ) -> dict[str, Any]:
        chemin = campagne.chemin_etat(self._dossier)
        if reprendre and os.path.exists(chemin):
            with open(chemin, "r", encoding="utf-8") as fh:
                campagne.etat = json.load(fh).get("etat", {})

        self._audit.enregistrer("campagne:start", campagne.nom, "OK", {"phases": list(phases)})

        if "recon" in phases and "recon" not in campagne.etat:
            campagne.etat["recon"] = recon.executer(
                campagne.cibles, self._guard, self._audit, intensite=campagne.intensite
            )
            self._sauver(campagne, chemin)

        if "scan" in phases and "scan" not in campagne.etat:
            cibles = campagne.etat.get("recon", {}).get("cibles_valides", campagne.cibles)
            campagne.etat["scan"] = scan.executer(
                cibles, self._guard, self._audit, intensite=campagne.intensite
            )
            self._sauver(campagne, chemin)

        # §6.1 — logique inter-phases : la phase web ne vise que les cibles
        # ayant un service web détecté au scan ; sinon elle est sautée.
        if "web" in phases and "web" not in campagne.etat:
            scan_res = campagne.etat.get("scan")
            cibles_w = web.cibles_web(scan_res) if scan_res else _repli(campagne)
            if cibles_w:
                campagne.etat["web"] = web.executer(
                    cibles_w,
                    self._guard,
                    self._audit,
                    intensite=campagne.intensite,
                    wordlist=wordlist,
                    sqlmap=sqlmap,
                )
            else:
                campagne.etat["web"] = {"phase": "web", "saute": "aucun service web détecté"}
            self._sauver(campagne, chemin)

        # nuclei préfère les URLs vivantes trouvées par httpx ; repli sur cibles.
        if "vuln" in phases and "vuln" not in campagne.etat:
            urls = campagne.etat.get("web", {}).get("urls_vivantes") or _repli(campagne)
            campagne.etat["vuln"] = vuln.executer(
                urls,
                self._guard,
                self._audit,
                intensite=campagne.intensite,
                severite_min=severite_min,
            )
            self._sauver(campagne, chemin)

        self._audit.enregistrer("campagne:end", campagne.nom, "OK")
        return campagne.etat

    def _sauver(self, campagne: Campagne, chemin: str) -> None:
        with open(chemin, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "nom": campagne.nom,
                    "maj": datetime.now(timezone.utc).isoformat(),
                    "etat": campagne.etat,
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
