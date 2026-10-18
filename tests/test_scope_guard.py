"""Couverture maximale du Scope Guard — c'est le composant critique.

Principe testé partout : deny-by-default. On vérifie autant les cas autorisés
que, surtout, tout ce qui doit être refusé.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scope_guard import Scope, ScopeGuard  # noqa: E402


def faux_resolveur(mapping):
    def _resoudre(hote):
        if hote not in mapping:
            import socket

            raise socket.gaierror("inconnu")
        return (hote, [], mapping[hote])

    return _resoudre


def make_scope(**kw) -> Scope:
    base = dict(
        nom="Lab test",
        autorisation_ref="AUTH-TEST",
        valide_jusqu_au=date(2099, 12, 31),
        domaines=["exemple-perso.com", "*.lab.exemple-perso.com"],
        ips=["192.168.56.0/24", "10.10.10.5"],
        exclusions=["192.168.56.1"],
        intensite_max="normale",
        heures_autorisees=(time.min, time.max),
    )
    base.update(kw)
    return Scope(**base)


_DEFAUT = object()


def guard_avec(mapping=_DEFAUT, **kw) -> ScopeGuard:
    if mapping is _DEFAUT:
        mapping = {
            "exemple-perso.com": ["10.10.10.5"],
            "www.lab.exemple-perso.com": ["192.168.56.10"],
        }
    return ScopeGuard(make_scope(**kw), resolveur=faux_resolveur(mapping))


# --------------------------------------------------------------- autorisés

def test_ip_dans_plage_autorisee():
    assert guard_avec().verifier("192.168.56.10")


def test_ip_unique_autorisee():
    assert guard_avec().verifier("10.10.10.5")


def test_domaine_exact_autorise():
    assert guard_avec().verifier("exemple-perso.com")


def test_wildcard_sous_domaine():
    assert guard_avec().verifier("www.lab.exemple-perso.com")


# ------------------------------------------------------------------ refus

def test_ip_hors_perimetre_refusee():
    d = guard_avec().verifier("8.8.8.8")
    assert not d and "hors périmètre" in d.raison


def test_domaine_inconnu_refuse():
    assert not guard_avec().verifier("google.com")


def test_exclusion_prioritaire_sur_autorisation():
    # 192.168.56.1 est dans la plage autorisée MAIS exclu.
    d = guard_avec().verifier("192.168.56.1")
    assert not d and "exclue" in d.raison


def test_deny_par_defaut_scope_vide():
    g = ScopeGuard(make_scope(domaines=[], ips=[]), resolveur=faux_resolveur({}))
    assert not g.verifier("10.10.10.5")


# ------------------------------------------------------- anti-contournement

def test_domaine_resolvant_hors_perimetre_bloque():
    g = guard_avec(mapping={"exemple-perso.com": ["1.2.3.4"]})
    d = g.verifier("exemple-perso.com")
    assert not d and "hors périmètre" in d.raison


def test_domaine_resolvant_vers_ip_exclue_bloque():
    g = guard_avec(mapping={"exemple-perso.com": ["192.168.56.1"]})
    d = g.verifier("exemple-perso.com")
    assert not d and "exclue" in d.raison


def test_resolution_impossible_bloque():
    g = guard_avec(mapping={})
    assert not g.verifier("exemple-perso.com")


# ------------------------------------------------------- temps & intensité

def test_engagement_expire():
    g = guard_avec(valide_jusqu_au=date(2000, 1, 1))
    assert not g.verifier("10.10.10.5")


def test_hors_plage_horaire():
    g = guard_avec(heures_autorisees=(time(9, 0), time(17, 0)))
    minuit = datetime(2026, 1, 1, 3, 0)
    assert not g.verifier("10.10.10.5", maintenant=minuit)


def test_intensite_superieure_au_max_refusee():
    g = guard_avec(intensite_max="normale")
    assert not g.verifier("10.10.10.5", intensite="agressive")


def test_intensite_dans_la_limite_ok():
    g = guard_avec(intensite_max="agressive")
    assert g.verifier("10.10.10.5", intensite="agressive")


def test_intensite_inconnue_refusee():
    assert not guard_avec().verifier("10.10.10.5", intensite="nucleaire")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
