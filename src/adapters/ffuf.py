"""Adaptateur ffuf — phase 5 (web), découverte de contenu par fuzzing.

Nécessite une wordlist (option ``wordlist``). La sortie JSON de ffuf est
normalisée en liste d'entrées trouvées (chemin, statut, taille).
"""

from __future__ import annotations

import json
from typing import Any

from adapters.base import AdapterError, BaseAdapter


class FfufAdapter(BaseAdapter):
    binaire = "ffuf"
    intensite = "normale"

    def construire_commande(self, cible: str, **options: Any) -> list[str]:
        wordlist = options.get("wordlist")
        if not wordlist:
            raise AdapterError("ffuf : option 'wordlist' obligatoire")
        # FUZZ est le marqueur ffuf ; la cible doit le contenir, sinon on
        # l'ajoute en fin de chemin.
        url = cible if "FUZZ" in cible else cible.rstrip("/") + "/FUZZ"
        cmd = [self.binaire, "-u", url, "-w", str(wordlist), "-of", "json", "-o", "/dev/stdout", "-s"]
        mc = options.get("codes_matches")  # ex. "200,204,301,302,403"
        if mc:
            cmd += ["-mc", str(mc)]
        return cmd

    def parser(self, stdout: str, stderr: str, code: int) -> dict[str, Any]:
        resultat: dict[str, Any] = {"outil": "ffuf", "trouvailles": []}
        stdout = stdout.strip()
        if not stdout:
            if stderr.strip():
                resultat["erreur"] = stderr.strip()
            return resultat
        try:
            obj = json.loads(stdout)
        except json.JSONDecodeError:
            resultat["erreur"] = "sortie ffuf non-JSON"
            return resultat
        for r in obj.get("results", []):
            resultat["trouvailles"].append(
                {
                    "url": r.get("url"),
                    "statut": r.get("status"),
                    "taille": r.get("length"),
                    "mots": r.get("words"),
                }
            )
        return resultat
