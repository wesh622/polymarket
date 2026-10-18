"""Point d'entrée CLI de l'orchestrateur.

Exemples :
    python src/main.py --scope scope.yaml verifier exemple-perso.com
    python src/main.py --scope scope.yaml run --cibles 10.10.10.5 --rapport rapport.md
    python src/main.py --scope scope.yaml run --phase recon --cibles exemple-perso.com

Rien ne s'exécute sans un scope.yaml valide : le Scope Guard est la seule porte.
"""

from __future__ import annotations

import argparse
import sys

from scope_guard import Scope, ScopeGuard, ScopeError
from audit_log import AuditLog
from orchestrator import Campagne, Orchestrateur, PHASES
from reporting.report import generer_markdown


def _construire_guard(chemin_scope: str) -> ScopeGuard:
    scope = Scope.charger(chemin_scope)
    return ScopeGuard(scope)


def cmd_verifier(args) -> int:
    guard = _construire_guard(args.scope)
    decision = guard.verifier(args.cible, intensite=args.intensite)
    marqueur = "AUTORISÉ" if decision else "BLOCKED"
    print(f"[{marqueur}] {args.cible} — {decision.raison}")
    return 0 if decision else 2


def cmd_run(args) -> int:
    guard = _construire_guard(args.scope)
    audit = AuditLog(args.audit, operateur=args.operateur)
    orch = Orchestrateur(guard, audit, dossier_etat=args.dossier_etat)

    phases = (args.phase,) if args.phase else PHASES
    campagne = Campagne(nom=args.nom, cibles=args.cibles, intensite=args.intensite)
    etat = orch.lancer(campagne, phases=phases, reprendre=args.reprendre)

    if args.rapport:
        md = generer_markdown(campagne.nom, etat)
        with open(args.rapport, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(f"Rapport écrit : {args.rapport}")
    else:
        print(generer_markdown(campagne.nom, etat))
    return 0


def construire_parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pentest-orchestrator", description=__doc__)
    p.add_argument("--scope", required=True, help="chemin du scope.yaml")
    p.add_argument("--intensite", default="normale", choices=["passive", "normale", "agressive"])
    sous = p.add_subparsers(dest="commande", required=True)

    v = sous.add_parser("verifier", help="tester une cible contre le périmètre")
    v.add_argument("cible")
    v.set_defaults(func=cmd_verifier)

    r = sous.add_parser("run", help="lancer une campagne")
    r.add_argument("--nom", default="campagne")
    r.add_argument("--cibles", nargs="+", required=True)
    r.add_argument("--phase", choices=list(PHASES), help="lancer une seule phase")
    r.add_argument("--operateur", default="inconnu")
    r.add_argument("--audit", default="logs/audit.log")
    r.add_argument("--dossier-etat", default="logs")
    r.add_argument("--rapport", help="chemin du rapport Markdown à écrire")
    r.add_argument("--reprendre", action="store_true", help="reprendre l'état existant")
    r.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = construire_parseur().parse_args(argv)
    try:
        return args.func(args)
    except ScopeError as exc:
        print(f"[ERREUR SCOPE] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
