"""Tests des adaptateurs : construction de commande (anti-shell) et parsing.

On ne lance pas les vrais outils ; on vérifie que la commande est bien une liste
d'arguments, que le Scope Guard est consulté avant exécution, et que les
parseurs normalisent correctement des sorties d'exemple.
"""

from __future__ import annotations

import os
import sys
from datetime import date, time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scope_guard import Scope, ScopeGuard  # noqa: E402
from audit_log import AuditLog  # noqa: E402
from adapters.base import AdapterError  # noqa: E402
from adapters.httpx import HttpxAdapter  # noqa: E402
from adapters.nuclei import NucleiAdapter  # noqa: E402
from adapters.ffuf import FfufAdapter  # noqa: E402
from adapters.nikto import NiktoAdapter  # noqa: E402
from adapters.sqlmap import SqlmapAdapter  # noqa: E402


def _guard():
    scope = Scope(
        nom="t",
        autorisation_ref="A",
        valide_jusqu_au=date(2099, 1, 1),
        domaines=["exemple-perso.com"],
        ips=["10.10.10.5"],
        exclusions=[],
        intensite_max="agressive",
        heures_autorisees=(time.min, time.max),
    )
    return ScopeGuard(scope, resolveur=lambda h: (h, [], ["10.10.10.5"]))


def _audit(tmp_path):
    return AuditLog(str(tmp_path / "a.log"), operateur="t")


# ---------------------------------------------------------- commandes (liste)

def test_httpx_commande_est_une_liste(tmp_path):
    a = HttpxAdapter(_guard(), _audit(tmp_path))
    cmd = a.construire_commande("exemple-perso.com")
    assert isinstance(cmd, list) and cmd[0] == "httpx" and "-json" in cmd


def test_nuclei_severite_et_templates(tmp_path):
    a = NucleiAdapter(_guard(), _audit(tmp_path))
    cmd = a.construire_commande("https://x", severite_min="high", templates=["cves/"])
    assert "-severity" in cmd
    sev = cmd[cmd.index("-severity") + 1]
    assert "high" in sev and "critical" in sev and "low" not in sev
    assert cmd.count("-t") == 1


def test_ffuf_exige_wordlist(tmp_path):
    a = FfufAdapter(_guard(), _audit(tmp_path))
    with pytest.raises(AdapterError):
        a.construire_commande("https://x")
    cmd = a.construire_commande("https://x", wordlist="/wl.txt")
    assert "FUZZ" in cmd[cmd.index("-u") + 1]


def test_sqlmap_intensite_agressive_et_url(tmp_path):
    a = SqlmapAdapter(_guard(), _audit(tmp_path))
    assert a.intensite == "agressive"
    with pytest.raises(AdapterError):
        a.construire_commande("pas-une-url")
    cmd = a.construire_commande("http://x/vuln?id=1", level=9, risk=9)
    # bornage : level<=5, risk<=3
    assert cmd[cmd.index("--level") + 1] == "5"
    assert cmd[cmd.index("--risk") + 1] == "3"


# ------------------------------------------------------------------ parsing

def test_httpx_parser_jsonl(tmp_path):
    a = HttpxAdapter(_guard(), _audit(tmp_path))
    out = '{"url":"https://exemple-perso.com","status_code":200,"title":"Accueil","tech":["nginx"]}\n'
    res = a.parser(out, "", 0)
    assert res["urls"][0]["statut"] == 200 and res["urls"][0]["technos"] == ["nginx"]


def test_nuclei_parser_findings(tmp_path):
    a = NucleiAdapter(_guard(), _audit(tmp_path))
    out = '{"template-id":"tech-detect","info":{"name":"nginx","severity":"info"},"matched-at":"https://x"}\n'
    res = a.parser(out, "", 0)
    assert res["findings"][0]["severite"] == "info"


def test_ffuf_parser_results(tmp_path):
    a = FfufAdapter(_guard(), _audit(tmp_path))
    out = '{"results":[{"url":"https://x/admin","status":200,"length":42,"words":5}]}'
    res = a.parser(out, "", 0)
    assert res["trouvailles"][0]["url"].endswith("/admin")


def test_sqlmap_parser_detecte_vuln(tmp_path):
    a = SqlmapAdapter(_guard(), _audit(tmp_path))
    out = "Parameter: id (GET)\nback-end DBMS: MySQL >= 5.0\n"
    res = a.parser(out, "", 0)
    assert res["vulnerable"] and "id" in res["parametres_injectables"] and "MySQL" in res["sgbd"]


def test_nikto_parser_liste(tmp_path):
    a = NiktoAdapter(_guard(), _audit(tmp_path))
    out = '[{"vulnerabilities":[{"id":"999","method":"GET","url":"/","msg":"server leak"}]}]'
    res = a.parser(out, "", 0)
    assert res["items"][0]["description"] == "server leak"


# ------------------------------------------------- Scope Guard dans executer()

def test_executer_bloque_hors_perimetre(tmp_path, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda b: "/usr/bin/" + b)  # outil "présent"
    a = HttpxAdapter(_guard(), _audit(tmp_path))
    with pytest.raises(AdapterError) as exc:
        a.executer("8.8.8.8")  # hors périmètre -> jamais lancé
    assert "BLOCKED" in str(exc.value)
