"""Phase 1 — Recon.

Version minimale : résolution des cibles via le Scope Guard. Les adaptateurs
OSINT (subfinder, httpx...) viendront se brancher ici sans toucher au moteur
(NFR-06). Chaque cible passe par le gardien avant toute sonde.
"""

from __future__ import annotations

from typing import Any

from scope_guard import ScopeGuard
from audit_log import AuditLog


def executer(
    cibles: list[str],
    guard: ScopeGuard,
    audit: AuditLog,
    *,
    intensite: str = "normale",
) -> dict[str, Any]:
    vivantes: list[str] = []
    bloquees: list[dict[str, str]] = []
    for cible in cibles:
        decision = guard.verifier(cible, intensite=intensite)
        if decision:
            vivantes.append(cible)
            audit.enregistrer("recon:scope", cible, "OK")
        else:
            bloquees.append({"cible": cible, "raison": decision.raison})
            audit.enregistrer("recon:scope", cible, "BLOCKED", {"raison": decision.raison})
    return {"phase": "recon", "cibles_valides": vivantes, "bloquees": bloquees}
