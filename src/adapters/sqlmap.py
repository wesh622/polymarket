"""Adaptateur sqlmap — phase 5 (web), test d'injection SQL.

C'est un test **actif** : il est volontairement rattaché à l'intensité
``agressive``, donc il ne s'exécute que si le ``scope.yaml`` autorise ce niveau
(sinon le Scope Guard bloque avant tout lancement).

sqlmap n'offre pas de JSON propre sur stdout ; on tourne en ``--batch`` (aucune
question interactive) avec des valeurs par défaut conservatrices, et on extrait
l'essentiel de la sortie texte (points d'injection détectés, SGBD).
"""

from __future__ import annotations

import re
from typing import Any

from adapters.base import AdapterError, BaseAdapter

_PARAM_VULN = re.compile(r"Parameter:\s*(.+?)\s*\(", re.IGNORECASE)
_SGBD = re.compile(r"back-end DBMS:\s*(.+)", re.IGNORECASE)


class SqlmapAdapter(BaseAdapter):
    binaire = "sqlmap"
    intensite = "agressive"  # test actif -> exige un scope agressif

    def construire_commande(self, cible: str, **options: Any) -> list[str]:
        if not cible.lower().startswith(("http://", "https://")):
            raise AdapterError("sqlmap : la cible doit être une URL http(s)")
        cmd = [self.binaire, "-u", cible, "--batch", "--disable-coloring"]
        # Niveau/risque laissés aux défauts sqlmap sauf demande explicite bornée.
        niveau = int(options.get("level", 1))
        risque = int(options.get("risk", 1))
        cmd += ["--level", str(max(1, min(niveau, 5))), "--risk", str(max(1, min(risque, 3)))]
        return cmd

    def parser(self, stdout: str, stderr: str, code: int) -> dict[str, Any]:
        texte = stdout + "\n" + stderr
        params = sorted(set(_PARAM_VULN.findall(texte)))
        sgbd = _SGBD.search(texte)
        vulnerable = bool(params) or "is vulnerable" in texte.lower()
        return {
            "outil": "sqlmap",
            "vulnerable": vulnerable,
            "parametres_injectables": params,
            "sgbd": sgbd.group(1).strip() if sgbd else None,
        }
