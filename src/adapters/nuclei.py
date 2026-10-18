"""Adaptateur nuclei (ProjectDiscovery) — phase 4, scan de vulnérabilités.

Pilote nuclei avec ses templates. La sortie JSONL est normalisée en liste de
findings (template, sévérité, emplacement). Le choix des templates peut être
restreint via l'option ``templates`` passée par l'orchestrateur (§6.1 : par ex.
templates correspondant à une version de service détectée).
"""

from __future__ import annotations

import json
from typing import Any

from adapters.base import BaseAdapter

_SEVERITES = ("info", "low", "medium", "high", "critical")


class NucleiAdapter(BaseAdapter):
    binaire = "nuclei"
    intensite = "normale"

    def construire_commande(self, cible: str, **options: Any) -> list[str]:
        cmd = [self.binaire, "-u", cible, "-jsonl", "-silent", "-no-color"]
        # Sévérité minimale (bornée côté appelant).
        severite_min = options.get("severite_min")
        if severite_min in _SEVERITES:
            # inclut severite_min et au-dessus
            idx = _SEVERITES.index(severite_min)
            cmd += ["-severity", ",".join(_SEVERITES[idx:])]
        # Templates ciblés (liste de chemins/ids) — un flag -t par entrée.
        for tpl in options.get("templates", []) or []:
            cmd += ["-t", str(tpl)]
        return cmd

    def parser(self, stdout: str, stderr: str, code: int) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        for ligne in stdout.splitlines():
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                obj = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            info = obj.get("info") or {}
            findings.append(
                {
                    "template": obj.get("template-id") or obj.get("templateID"),
                    "nom": info.get("name"),
                    "severite": info.get("severity"),
                    "emplacement": obj.get("matched-at") or obj.get("host"),
                }
            )
        resultat: dict[str, Any] = {"outil": "nuclei", "findings": findings}
        if not findings and stderr.strip():
            resultat["note"] = stderr.strip()
        return resultat
