"""Reporting — consolide l'état de campagne en Markdown (FR-07).

L'export PDF (pandoc/weasyprint) se branche en aval du Markdown ; on garde ici
le cœur sans dépendance lourde, pour que le rapport texte soit toujours
produisible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def generer_markdown(nom: str, etat: dict[str, Any]) -> str:
    lignes: list[str] = [
        f"# Rapport — {nom}",
        "",
        f"_Généré le {datetime.now(timezone.utc).isoformat()}_",
        "",
    ]

    recon = etat.get("recon")
    if recon:
        lignes += ["## Phase 1 — Recon", ""]
        lignes.append(f"- Cibles valides : {len(recon.get('cibles_valides', []))}")
        for c in recon.get("cibles_valides", []):
            lignes.append(f"  - `{c}`")
        bloquees = recon.get("bloquees", [])
        if bloquees:
            lignes.append(f"- Cibles bloquées : {len(bloquees)}")
            for b in bloquees:
                lignes.append(f"  - `{b['cible']}` — {b['raison']}")
        lignes.append("")

    scan = etat.get("scan")
    if scan:
        lignes += ["## Phase 2 — Scan", ""]
        for res in scan.get("resultats", []):
            lignes.append(f"### `{res.get('cible')}`")
            for hote in res.get("hotes", []):
                ports = hote.get("ports", [])
                if not ports:
                    lignes.append(f"- {hote.get('adresse')} : aucun port ouvert")
                    continue
                lignes.append(f"- {hote.get('adresse')} :")
                for p in ports:
                    svc = p.get("service") or "?"
                    ver = f" {p.get('produit')} {p.get('version')}".rstrip()
                    lignes.append(f"  - `{p['port']}/{p['protocole']}` {svc}{ver}")
            lignes.append("")
        for err in scan.get("erreurs", []):
            lignes.append(f"- ⚠️ `{err['cible']}` — {err['erreur']}")
        lignes.append("")

    web = etat.get("web")
    if web:
        lignes += ["## Phase 5 — Web", ""]
        if web.get("saute"):
            lignes += [f"_Sautée : {web['saute']}_", ""]
        else:
            urls = web.get("urls_vivantes", [])
            if urls:
                lignes.append(f"- URLs vivantes : {len(urls)}")
                for u in urls:
                    lignes.append(f"  - `{u}`")
            for res in web.get("resultats", []):
                nikto = res.get("nikto", {})
                items = nikto.get("items", [])
                if items:
                    lignes.append(f"- nikto `{res.get('cible')}` : {len(items)} item(s)")
                    for it in items[:20]:
                        lignes.append(f"  - {it.get('methode')} `{it.get('url')}` — {it.get('description')}")
                ffuf = res.get("ffuf", {})
                for t in ffuf.get("trouvailles", [])[:20]:
                    lignes.append(f"  - ffuf `{t.get('url')}` [{t.get('statut')}]")
                sqlmap = res.get("sqlmap")
                if sqlmap and sqlmap.get("vulnerable"):
                    params = ", ".join(sqlmap.get("parametres_injectables", [])) or "?"
                    lignes.append(f"- 🔴 sqlmap `{res.get('cible')}` injectable : {params} (SGBD {sqlmap.get('sgbd')})")
            for err in web.get("erreurs", []):
                lignes.append(f"- ⚠️ `{err['cible']}` [{err.get('outil')}] — {err['erreur']}")
        lignes.append("")

    vuln = etat.get("vuln")
    if vuln:
        lignes += ["## Phase 4 — Vulnérabilités (nuclei)", ""]
        total = 0
        for res in vuln.get("resultats", []):
            findings = res.get("findings", [])
            total += len(findings)
            for f in findings:
                sev = (f.get("severite") or "?").upper()
                lignes.append(f"- [{sev}] `{f.get('template')}` — {f.get('emplacement')}")
        if total == 0:
            lignes.append("- Aucun finding.")
        for err in vuln.get("erreurs", []):
            lignes.append(f"- ⚠️ `{err['cible']}` — {err['erreur']}")
        lignes.append("")

    return "\n".join(lignes)
