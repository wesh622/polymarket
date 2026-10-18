"""Phase 2 — Scan.

Lance l'adaptateur nmap sur chaque cible validée par la phase recon. Un échec
sur une cible (NFR-05) est consigné et n'interrompt pas les autres.
"""

from __future__ import annotations

from typing import Any

from adapters.base import AdapterError
from adapters.nmap import NmapAdapter
from scope_guard import ScopeGuard
from audit_log import AuditLog


def executer(
    cibles: list[str],
    guard: ScopeGuard,
    audit: AuditLog,
    *,
    intensite: str = "normale",
    timeout: int = 300,
) -> dict[str, Any]:
    nmap = NmapAdapter(guard, audit, intensite=intensite, timeout=timeout)
    resultats: list[dict[str, Any]] = []
    erreurs: list[dict[str, str]] = []
    for cible in cibles:
        try:
            resultats.append({"cible": cible, **nmap.executer(cible)})
        except AdapterError as exc:
            erreurs.append({"cible": cible, "erreur": str(exc)})
    return {"phase": "scan", "resultats": resultats, "erreurs": erreurs}
