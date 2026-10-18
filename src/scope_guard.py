"""Scope Guard — point de passage unique avant toute action.

Philosophie : *deny-by-default*. Une cible n'est autorisée que si elle
correspond explicitement à une entrée du périmètre et à aucune exclusion.
L'absence de règle vaut toujours refus, jamais autorisation.

Ce module ne lance aucune commande : il répond uniquement à la question
« ai-je le droit de toucher cette cible, maintenant, à cette intensité ? ».
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from datetime import date, datetime, time
from fnmatch import fnmatch
from typing import Iterable

import yaml

# Ordre croissant d'intensité. Sert à borner le profil demandé par le scope.
INTENSITES = ("passive", "normale", "agressive")


class ScopeError(Exception):
    """Périmètre invalide ou illisible : on refuse de démarrer."""


@dataclass(frozen=True)
class Decision:
    """Verdict du Scope Guard pour une cible donnée."""

    autorise: bool
    cible: str
    raison: str

    def __bool__(self) -> bool:  # permet `if guard.verifier(...):`
        return self.autorise


@dataclass
class Scope:
    """Périmètre chargé depuis ``scope.yaml`` (déclaratif, versionné)."""

    nom: str
    autorisation_ref: str
    valide_jusqu_au: date
    domaines: list[str] = field(default_factory=list)
    ips: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    intensite_max: str = "normale"
    heures_autorisees: tuple[time, time] = (time.min, time.max)

    @classmethod
    def charger(cls, chemin: str) -> "Scope":
        try:
            with open(chemin, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        except FileNotFoundError as exc:
            raise ScopeError(f"Fichier de périmètre introuvable : {chemin}") from exc
        except yaml.YAMLError as exc:
            raise ScopeError(f"scope.yaml illisible : {exc}") from exc

        engagement = data.get("engagement") or {}
        autorise = data.get("autorise") or {}
        limites = data.get("limites") or {}

        for cle in ("nom", "autorisation_ref", "valide_jusqu_au"):
            if not engagement.get(cle):
                raise ScopeError(f"engagement.{cle} est obligatoire")

        valide = engagement["valide_jusqu_au"]
        if not isinstance(valide, date):
            valide = date.fromisoformat(str(valide))

        heures = cls._parser_heures(limites.get("heures_autorisees", "00:00-23:59"))
        intensite = limites.get("intensite_max", "normale")
        if intensite not in INTENSITES:
            raise ScopeError(f"intensite_max inconnue : {intensite!r}")

        return cls(
            nom=engagement["nom"],
            autorisation_ref=engagement["autorisation_ref"],
            valide_jusqu_au=valide,
            domaines=list(autorise.get("domaines") or []),
            ips=list(autorise.get("ips") or []),
            exclusions=list(autorise.get("exclusions") or []),
            intensite_max=intensite,
            heures_autorisees=heures,
        )

    @staticmethod
    def _parser_heures(brut: str) -> tuple[time, time]:
        try:
            debut, fin = brut.split("-", 1)
            return time.fromisoformat(debut.strip()), time.fromisoformat(fin.strip())
        except (ValueError, AttributeError) as exc:
            raise ScopeError(f"heures_autorisees invalide : {brut!r}") from exc


class ScopeGuard:
    """Seule porte vers l'exécution. Tout appel d'outil doit la franchir."""

    def __init__(self, scope: Scope, *, resolveur=socket.gethostbyname_ex):
        self._scope = scope
        # Injectable pour les tests : (hostname) -> (name, aliases, [ips]).
        self._resolveur = resolveur

    # ------------------------------------------------------------------ API

    def verifier(
        self,
        cible: str,
        *,
        intensite: str = "normale",
        maintenant: datetime | None = None,
    ) -> Decision:
        """Retourne une :class:`Decision`. Ne lève jamais pour un simple refus."""

        maintenant = maintenant or datetime.now()

        # 1. Validité temporelle de l'engagement.
        if maintenant.date() > self._scope.valide_jusqu_au:
            return self._refus(cible, "engagement expiré")

        # 2. Plage horaire autorisée.
        debut, fin = self._scope.heures_autorisees
        if not (debut <= maintenant.time() <= fin):
            return self._refus(cible, "hors plage horaire autorisée")

        # 3. Intensité bornée par le scope.
        if intensite not in INTENSITES:
            return self._refus(cible, f"intensité inconnue : {intensite!r}")
        if INTENSITES.index(intensite) > INTENSITES.index(self._scope.intensite_max):
            return self._refus(
                cible,
                f"intensité {intensite!r} > max autorisé {self._scope.intensite_max!r}",
            )

        # 4. Exclusions : priorité absolue, avant toute autorisation.
        if self._exclue(cible):
            return self._refus(cible, "cible explicitement exclue")

        # 5. Appartenance au périmètre autorisé.
        if not self._dans_perimetre(cible):
            return self._refus(cible, "cible hors périmètre")

        # 6. Anti-contournement DNS : un domaine autorisé ne doit pas résoudre
        #    vers une IP hors périmètre (ou explicitement exclue).
        souci = self._verifier_resolution(cible)
        if souci is not None:
            return self._refus(cible, souci)

        return Decision(True, cible, "dans le périmètre")

    # -------------------------------------------------------------- internes

    def _refus(self, cible: str, raison: str) -> Decision:
        return Decision(False, cible, raison)

    def _est_ip(self, valeur: str) -> bool:
        try:
            ipaddress.ip_address(valeur)
            return True
        except ValueError:
            return False

    def _ip_dans(self, ip: str, entrees: Iterable[str]) -> bool:
        adresse = ipaddress.ip_address(ip)
        for entree in entrees:
            try:
                if "/" in entree:
                    if adresse in ipaddress.ip_network(entree, strict=False):
                        return True
                elif adresse == ipaddress.ip_address(entree):
                    return True
            except ValueError:
                continue
        return False

    def _domaine_match(self, cible: str, motifs: Iterable[str]) -> bool:
        cible = cible.lower().rstrip(".")
        return any(fnmatch(cible, motif.lower().rstrip(".")) for motif in motifs)

    def _exclue(self, cible: str) -> bool:
        if self._est_ip(cible):
            return self._ip_dans(cible, self._scope.exclusions)
        return self._domaine_match(cible, self._scope.exclusions)

    def _dans_perimetre(self, cible: str) -> bool:
        if self._est_ip(cible):
            return self._ip_dans(cible, self._scope.ips)
        return self._domaine_match(cible, self._scope.domaines)

    def _verifier_resolution(self, cible: str) -> str | None:
        """Pour un domaine : refuse si une IP résolue sort du périmètre."""
        if self._est_ip(cible):
            return None
        try:
            _, _, ips = self._resolveur(cible)
        except (socket.gaierror, OSError):
            return "résolution DNS impossible"
        if not ips:
            return "aucune IP résolue"
        for ip in ips:
            if self._ip_dans(ip, self._scope.exclusions):
                return f"résout vers une IP exclue ({ip})"
            # Si des IPs sont déclarées, la résolution doit y rester confinée.
            if self._scope.ips and not self._ip_dans(ip, self._scope.ips):
                return f"résout hors périmètre ({ip})"
        return None
