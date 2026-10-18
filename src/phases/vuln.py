"""Phase 4 — Scan de vulnérabilités (nuclei).

Tourne sur les URLs vivantes découvertes par la phase web quand elles existent,
sinon sur les cibles fournies. Les templates peuvent être restreints par
l'appelant (§6.1).
"""

from __future__ import annotations

from typing import Any

from adapters.base import AdapterError
from adapters.nuclei import NucleiAdapter
from scope_guard import ScopeGuard
from audit_log import AuditLog


def executer(
    cibles: list[str],
    guard: ScopeGuard,
    audit: AuditLog,
    *,
    intensite: str = "normale",
    timeout: int = 600,
    severite_min: str | None = None,
    templates: list[str] | None = None,
) -> dict[str, Any]:
    nuclei = NucleiAdapter(guard, audit, timeout=timeout)
    resultats: list[dict[str, Any]] = []
    erreurs: list[dict[str, str]] = []
    for cible in cibles:
        try:
            res = nuclei.executer(cible, severite_min=severite_min, templates=templates or [])
            resultats.append({"cible": cible, **res})
        except AdapterError as exc:
            erreurs.append({"cible": cible, "erreur": str(exc)})
    return {"phase": "vuln", "resultats": resultats, "erreurs": erreurs}
