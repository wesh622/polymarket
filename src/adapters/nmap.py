"""Adaptateur nmap — premier adaptateur de référence (cf. plan §12.3).

Pilote nmap en sortie XML et la normalise en structure JSON : liste des ports
ouverts avec service et version quand disponible.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from adapters.base import BaseAdapter

# Profil d'intensité -> arguments nmap. Le Scope Guard borne déjà le choix.
_PROFILS = {
    "passive": ["-sn"],               # découverte d'hôte uniquement
    "normale": ["-sV", "--top-ports", "1000"],
    "agressive": ["-sV", "-p-", "-T4"],
}


class NmapAdapter(BaseAdapter):
    binaire = "nmap"

    def __init__(self, *args, intensite: str = "normale", **kwargs):
        super().__init__(*args, **kwargs)
        self.intensite = intensite

    def construire_commande(self, cible: str, **options: Any) -> list[str]:
        profil = _PROFILS.get(self.intensite, _PROFILS["normale"])
        # -oX - : XML sur stdout ; arguments en liste, jamais de shell.
        return [self.binaire, *profil, "-oX", "-", cible]

    def parser(self, stdout: str, stderr: str, code: int) -> dict[str, Any]:
        resultat: dict[str, Any] = {"outil": "nmap", "hotes": []}
        if not stdout.strip():
            resultat["erreur"] = stderr.strip() or "sortie vide"
            return resultat
        try:
            racine = ET.fromstring(stdout)
        except ET.ParseError as exc:
            resultat["erreur"] = f"XML illisible : {exc}"
            return resultat

        for host in racine.findall("host"):
            addr_el = host.find("address")
            hote = {"adresse": addr_el.get("addr") if addr_el is not None else "?", "ports": []}
            for port in host.findall("./ports/port"):
                etat = port.find("state")
                if etat is None or etat.get("state") != "open":
                    continue
                svc = port.find("service")
                hote["ports"].append(
                    {
                        "port": int(port.get("portid")),
                        "protocole": port.get("protocol"),
                        "service": svc.get("name") if svc is not None else None,
                        "produit": svc.get("product") if svc is not None else None,
                        "version": svc.get("version") if svc is not None else None,
                    }
                )
            resultat["hotes"].append(hote)
        return resultat
