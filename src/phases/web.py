"""Phase 5 — Web.

Ne s'exécute que sur les cibles dont le scan a révélé un service web (§6.1).
Lance httpx (URLs vivantes), puis nikto sur ces URLs. ffuf et sqlmap sont
optionnels : ffuf requiert une wordlist, sqlmap requiert une intensité agressive
(le Scope Guard bloque sinon).

Un échec d'outil sur une cible est consigné sans interrompre les autres (NFR-05).
"""

from __future__ import annotations

from typing import Any

from adapters.base import AdapterError
from adapters.httpx import HttpxAdapter
from adapters.nikto import NiktoAdapter
from adapters.ffuf import FfufAdapter
from adapters.sqlmap import SqlmapAdapter
from scope_guard import ScopeGuard
from audit_log import AuditLog

PORTS_WEB = {80, 443, 8080, 8443, 8000, 8888}
SERVICES_WEB = {"http", "https", "http-alt", "https-alt", "http-proxy"}


def cibles_web(resultat_scan: dict[str, Any]) -> list[str]:
    """Extrait du résultat de scan les hôtes exposant un service web."""
    cibles: list[str] = []
    for res in resultat_scan.get("resultats", []):
        a_du_web = False
        for hote in res.get("hotes", []):
            for p in hote.get("ports", []):
                if p.get("port") in PORTS_WEB or (p.get("service") or "") in SERVICES_WEB:
                    a_du_web = True
        if a_du_web and res.get("cible"):
            cibles.append(res["cible"])
    return cibles


def executer(
    cibles: list[str],
    guard: ScopeGuard,
    audit: AuditLog,
    *,
    intensite: str = "normale",
    timeout: int = 600,
    wordlist: str | None = None,
    sqlmap: bool = False,
) -> dict[str, Any]:
    httpx = HttpxAdapter(guard, audit, timeout=timeout)
    nikto = NiktoAdapter(guard, audit, timeout=timeout)
    ffuf = FfufAdapter(guard, audit, timeout=timeout)
    sqlm = SqlmapAdapter(guard, audit, timeout=timeout)

    resultats: list[dict[str, Any]] = []
    erreurs: list[dict[str, str]] = []
    urls_vivantes: list[str] = []

    for cible in cibles:
        entree: dict[str, Any] = {"cible": cible}

        try:
            httpx_res = httpx.executer(cible)
            entree["httpx"] = httpx_res
            urls_vivantes += [u["url"] for u in httpx_res.get("urls", []) if u.get("url")]
        except AdapterError as exc:
            erreurs.append({"cible": cible, "outil": "httpx", "erreur": str(exc)})

        for nom, adaptateur, opts in _taches_web(cible, ffuf, nikto, sqlm, wordlist, sqlmap):
            try:
                entree[nom] = adaptateur.executer(cible, **opts)
            except AdapterError as exc:
                erreurs.append({"cible": cible, "outil": nom, "erreur": str(exc)})

        resultats.append(entree)

    return {
        "phase": "web",
        "resultats": resultats,
        "erreurs": erreurs,
        "urls_vivantes": sorted(set(urls_vivantes)),
    }


def _taches_web(cible, ffuf, nikto, sqlm, wordlist, avec_sqlmap):
    taches = [("nikto", nikto, {})]
    if wordlist:
        taches.append(("ffuf", ffuf, {"wordlist": wordlist}))
    if avec_sqlmap and cible.lower().startswith(("http://", "https://")):
        taches.append(("sqlmap", sqlm, {}))
    return taches
