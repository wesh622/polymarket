# Cahier des charges — Orchestrateur de tests d'intrusion

> Nom de code : **pentest-orchestrator** (à renommer)
> Version du document : 1.0
> Statut : spécification initiale

---

## 1. Contexte et objectif

Faire un test d'intrusion demande d'enchaîner beaucoup d'outils (reconnaissance,
scan, énumération, test applicatif, reporting), chacun avec sa syntaxe et ses
options. Le faire à la main est lent, répétitif et source d'oublis.

L'objectif de ce projet est de construire un **orchestrateur** : une couche
logicielle qui pilote des outils existants de Kali Linux, les enchaîne par
phases, prend des décisions en fonction de ce qui est découvert, et produit un
rapport exploitable — **uniquement sur des cibles que l'opérateur possède ou est
explicitement autorisé à tester**.

C'est un automate de pilotage.

---

## 2. Cadre légal (contrainte, pas avertissement)

En France, l'accès ou le maintien frauduleux dans un système de traitement
automatisé de données est pénalement réprimé (art. 323-1 et suivants du Code
pénal), **que l'intention soit malveillante ou non**. Tester un système sans
autorisation écrite est une infraction.

Conséquences sur la conception :
- Toute action offensive est **refusée par défaut** si la cible n'est pas dans
  une liste blanche validée.
- Chaque exécution est **journalisée de façon immuable** (qui, quoi, quand, sur
  quelle cible), pour pouvoir prouver le périmètre a posteriori.

---

## 3. Périmètre fonctionnel

### 3.1 Dans le périmètre
- Reconnaissance passive et active (OSINT, DNS, sous-domaines, ports, services).
- Scan de vulnérabilités (templates connus, bannières, versions).
- Test d'applications web (répertoires, injections, mauvaises configs).
- Analyse d'applications mobiles **dont l'opérateur dispose du binaire** (APK/IPA)
  dans un lab — analyse statique/dynamique, pas de ciblage d'appareils tiers.
- Agrégation des résultats et génération d'un rapport.

---

## 4. Architecture générale

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Interface  │────▶│  Scope Guard     │────▶│  Orchestrateur │
│ (CLI / bot) │     │ (liste blanche)  │     │  (moteur phases)│
└─────────────┘     └──────────────────┘     └───────┬────────┘
       ▲                    │                        │
       │                    ▼                        ▼
       │            ┌──────────────┐        ┌──────────────────┐
       │            │ Audit log    │        │ Adaptateurs outils│
       │            │ (immuable)   │        │ nmap, nuclei, ... │
       │            └──────────────┘        └────────┬─────────┘
       │                                             │
       │                                             ▼
       │                                   ┌──────────────────┐
       └───────────────────────────────────│  Reporting (JSON │
                                            │  → MD / PDF)     │
                                            └──────────────────┘
```

**Principe clé : rien ne s'exécute sans passer par le Scope Guard.** C'est un
point de passage unique, pas une vérification dispersée dans le code.

---

## 5. Le Scope Guard (cœur du projet — à coder en premier)

### 5.1 Rôle
Avant **chaque** commande, le Scope Guard vérifie que la cible appartient au
périmètre autorisé. S'il y a le moindre doute, il refuse.

### 5.2 Fichier de périmètre (`scope.yaml`)
Déclaratif, versionné, référencé par une autorisation de test.

```yaml
engagement:
  nom: "Lab personnel - octobre 2026"
  autorisation_ref: "AUTH-2026-001"   # référence du doc signé
  valide_jusqu_au: "2026-12-31"

autorise:
  domaines:
    - "exemple-perso.com"
    - "*.lab.exemple-perso.com"
  ips:
    - "192.168.56.0/24"               # réseau de lab
    - "10.10.10.5"
  exclusions:                          # jamais testé, même si dans une plage
    - "192.168.56.1"                   # passerelle

limites:
  intensite_max: "normale"             # passive | normale | agressive
  heures_autorisees: "00:00-23:59"
```

### 5.3 Règles de validation
1. Une cible est autorisée **seulement si** elle correspond à une entrée de
   `autorise` **et** ne correspond à aucune `exclusion`.
2. Résolution DNS vérifiée : si un domaine autorisé résout vers une IP hors
   périmètre, l'action est bloquée (anti-contournement).
3. L'engagement doit être dans sa période de validité.
4. Par défaut : **deny**. L'absence de règle = refus, jamais autorisation.

### 5.4 Comportement en cas de refus
- Aucune commande lancée.
- Entrée de log : `BLOCKED — cible hors périmètre`.
- Message clair à l'opérateur.

---

## 6. Moteur d'orchestration (phases)

Le moteur suit une logique de phases inspirée de PTES / MITRE ATT&CK. Chaque
phase produit des données qui alimentent la suivante.

| Phase | But | Outils pilotés (exemples) | Entrée → Sortie |
|-------|-----|---------------------------|-----------------|
| 1. Recon / OSINT | Cartographier la surface | subfinder, amass, theHarvester, httpx | domaine → sous-domaines vivants |
| 2. Scan | Découvrir ports/services | nmap, naabu | hôtes → ports/services ouverts |
| 3. Énumération | Détailler les services | nmap -sV, scripts NSE | services → versions, bannières |
| 4. Vuln scan | Repérer failles connues | nuclei (+ templates) | services → vulnérabilités candidates |
| 5. Web | Tester les apps web | ffuf/gobuster, nikto, sqlmap | URL → répertoires, injections |
| 6. Mobile (lab) | Analyser une app | MobSF, objection (statique/dynamique) | APK/IPA → rapport d'app |
| 7. Reporting | Consolider | agrégateur interne | tout → rapport |

### 6.1 Logique entre phases
L'orchestrateur n'exécute pas tout systématiquement : il décide. Exemples :
- un port 443 ouvert en phase 2 → déclenche la phase web sur cette cible ;
- une version de service connue vulnérable → sélectionne les templates nuclei
  correspondants ;
- aucun service web → la phase 5 est sautée.

### 6.2 Profils d'intensité
- **passive** : uniquement OSINT, aucune sonde directe de la cible ;
- **normale** : scans standards, non intrusifs ;
- **agressive** : scans complets (soumis à l'intensité max du scope).

---

## 7. Exigences fonctionnelles (FR)

| ID | Exigence |
|----|----------|
| FR-01 | Charger et valider un `scope.yaml` au démarrage de chaque campagne. |
| FR-02 | Vérifier chaque cible via le Scope Guard avant toute commande. |
| FR-03 | Enchaîner les phases avec passage de données entre elles. |
| FR-04 | Permettre de lancer une phase isolée (ex. « recon seulement »). |
| FR-05 | Choisir un profil d'intensité, borné par le scope. |
| FR-06 | Parser la sortie de chaque outil en structure normalisée (JSON). |
| FR-07 | Générer un rapport final (Markdown + export PDF). |
| FR-08 | Journaliser chaque action (horodatage, opérateur, cible, commande, résultat). |
| FR-09 | Reprendre une campagne interrompue sans tout relancer. |

## 8. Exigences non-fonctionnelles (NFR)

| ID | Exigence |
|----|----------|
| NFR-01 | **Sécurité** : deny-by-default sur le périmètre ; aucun secret en clair. |
| NFR-02 | **Authentification** : si interface distante (bot), accès restreint à une liste d'opérateurs validés + jeton. |
| NFR-03 | **Traçabilité** : logs en append-only (horodatés, non modifiables par l'app). |
| NFR-04 | **Isolation** : exécution des outils dans un conteneur/VM dédié. |
| NFR-05 | **Robustesse** : un outil qui échoue n'interrompt pas toute la campagne. |
| NFR-06 | **Extensibilité** : ajouter un outil = écrire un adaptateur, sans toucher au moteur. |
| NFR-07 | **Configurabilité** : chemins, timeouts, concurrence dans un fichier de config. |

---

## 9. Choix d'interface

Deux options, exclusives ou combinables :

- **CLI** (recommandé pour démarrer) : simple, local, pas de surface d'attaque
  réseau. Idéal pour apprendre l'architecture.
- **Bot Telegram** (optionnel, plus tard) : pratique mais ajoute une surface de
  sécurité. S'il est retenu : authentification par liste d'opérateurs, jeton
  côté serveur, et le Scope Guard reste la seule porte vers l'exécution.

> Conseil : commencer en CLI. N'ajouter le bot qu'une fois le Scope Guard et le
> logging solides et testés.

---

## 10. Stack technique proposée

- **Langage** : Python 3.11+ (riche écosystème, adaptateurs faciles).
- **Config** : YAML (scope) + fichier de config appli.
- **Exécution outils** : `subprocess` encadré, jamais de concaténation de chaîne
  shell brute (éviter l'injection de commande) — arguments en liste.
- **Conteneur** : Docker basé sur une image Kali, ou VM Kali dédiée.
- **Reporting** : templates Jinja2 → Markdown → PDF (ex. via pandoc/weasyprint).
- **Tests** : pytest, avec une batterie de tests dédiée au Scope Guard.

---

## 11. Structure de projet cible

```
pentest-orchestrator/
├── README.md
├── CAHIER_DES_CHARGES.md
├── scope.yaml.example
├── config.yaml.example
├── requirements.txt
├── src/
│   ├── main.py                 # point d'entrée CLI
│   ├── scope_guard.py          # ← à coder et tester en premier
│   ├── orchestrator.py         # moteur de phases
│   ├── audit_log.py            # journalisation immuable
│   ├── adapters/               # un fichier par outil
│   │   ├── base.py
│   │   ├── nmap.py
│   │   ├── nuclei.py
│   │   └── ...
│   ├── phases/
│   │   ├── recon.py
│   │   ├── scan.py
│   │   └── ...
│   └── reporting/
│       └── report.py
├── tests/
│   ├── test_scope_guard.py     # couverture maximale ici
│   └── ...
└── logs/                       # append-only
```

---

## 12. Plan de développement (par incréments)

1. **Scope Guard + tests** — rien d'autre ne commence avant que ça soit solide.
2. **Audit log** — journalisation en place dès le départ.
3. **Un adaptateur simple** (ex. nmap) passant par le Scope Guard.
4. **Moteur de phases minimal** (recon → scan) en CLI.
5. **Parsing → JSON normalisé** puis reporting Markdown.
6. **Ajout progressif d'adaptateurs** (nuclei, ffuf, nikto, sqlmap).
7. **Module mobile en lab** (MobSF) si besoin.
8. **(Optionnel) bot Telegram** avec authentification.

---

## 13. Critères d'acceptation

- [ ] Aucune commande ne s'exécute sur une cible hors `scope.yaml`.
- [ ] Un test hors périmètre produit `BLOCKED` + entrée de log, zéro exécution.
- [ ] Chaque action réelle laisse une trace horodatée.
- [ ] Une campagne recon → scan s'enchaîne et produit un rapport Markdown.
- [ ] La batterie de tests du Scope Guard couvre les cas limites (exclusions,
      wildcard, anti-contournement DNS, expiration, intensité).
