"""Tests du journal append-only et de l'intégrité par chaînage de hash."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from audit_log import AuditLog  # noqa: E402


def test_entrees_chainees_et_valides(tmp_path):
    chemin = tmp_path / "audit.log"
    log = AuditLog(str(chemin), operateur="omar")
    log.enregistrer("nmap", "10.10.10.5", "OK")
    log.enregistrer("nmap", "10.10.10.6", "BLOCKED", {"raison": "hors périmètre"})
    assert log.verifier() is True

    lignes = chemin.read_text(encoding="utf-8").strip().splitlines()
    assert len(lignes) == 2
    e1, e2 = (json.loads(x) for x in lignes)
    assert e2["precedent"] == e1["hash"]  # chaînage


def test_alteration_detectee(tmp_path):
    chemin = tmp_path / "audit.log"
    log = AuditLog(str(chemin), operateur="omar")
    log.enregistrer("nmap", "10.10.10.5", "OK")
    log.enregistrer("nmap", "10.10.10.6", "OK")

    lignes = chemin.read_text(encoding="utf-8").splitlines()
    falsifie = json.loads(lignes[0])
    falsifie["resultat"] = "BLOCKED"  # on maquille a posteriori
    lignes[0] = json.dumps(falsifie, sort_keys=True, ensure_ascii=False)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")

    assert log.verifier() is False
