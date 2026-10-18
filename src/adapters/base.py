"""Socle commun des adaptateurs d'outils.

Un adaptateur encapsule un outil externe (nmap, nuclei, ...). Règles :

* la commande est TOUJOURS passée en liste d'arguments à ``subprocess`` —
  jamais de chaîne shell concaténée (anti-injection, NFR-01) ;
* aucun adaptateur n'exécute quoi que ce soit sans décision favorable du
  Scope Guard : la vérification est faite ici, dans la classe mère, pour que le
  passage obligé ne puisse pas être oublié dans un adaptateur ;
* la sortie est normalisée en JSON par ``parser`` (FR-06) ;
* un échec d'outil lève ``AdapterError`` mais n'interrompt pas la campagne
  (NFR-05) : c'est l'orchestrateur qui décide quoi en faire.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from scope_guard import ScopeGuard
from audit_log import AuditLog


class AdapterError(Exception):
    """Échec d'exécution ou outil absent."""


class BaseAdapter(ABC):
    #: nom de l'exécutable attendu dans le PATH
    binaire: str = ""
    #: intensité requise par l'outil (bornée par le scope)
    intensite: str = "normale"

    def __init__(self, guard: ScopeGuard, audit: AuditLog, *, timeout: int = 300):
        self._guard = guard
        self._audit = audit
        self._timeout = timeout

    @abstractmethod
    def construire_commande(self, cible: str, **options: Any) -> list[str]:
        """Retourne la commande sous forme de liste d'arguments."""

    @abstractmethod
    def parser(self, stdout: str, stderr: str, code: int) -> dict[str, Any]:
        """Normalise la sortie brute de l'outil en dict JSON-sérialisable."""

    # ------------------------------------------------------------------ run

    def executer(self, cible: str, **options: Any) -> dict[str, Any]:
        decision = self._guard.verifier(cible, intensite=self.intensite)
        if not decision:
            self._audit.enregistrer(
                action=f"{self.binaire}:BLOCKED",
                cible=cible,
                resultat="BLOCKED",
                details={"raison": decision.raison},
            )
            raise AdapterError(f"BLOCKED — {decision.raison} ({cible})")

        if shutil.which(self.binaire) is None:
            self._audit.enregistrer(
                action=f"{self.binaire}:MISSING",
                cible=cible,
                resultat="ERROR",
                details={"raison": f"binaire {self.binaire!r} introuvable"},
            )
            raise AdapterError(f"Outil introuvable dans le PATH : {self.binaire}")

        commande = self.construire_commande(cible, **options)
        try:
            proc = subprocess.run(
                commande,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self._audit.enregistrer(
                action=f"{self.binaire}:TIMEOUT",
                cible=cible,
                resultat="ERROR",
                details={"commande": commande, "timeout": self._timeout},
            )
            raise AdapterError(f"Timeout après {self._timeout}s : {self.binaire}") from exc

        resultat = self.parser(proc.stdout, proc.stderr, proc.returncode)
        self._audit.enregistrer(
            action=self.binaire,
            cible=cible,
            resultat="OK" if proc.returncode == 0 else "NONZERO",
            details={"commande": commande, "code": proc.returncode},
        )
        return resultat
