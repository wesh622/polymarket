# pentest-orchestrator

Orchestrateur de tests d'intrusion **pour cibles autorisées uniquement**. Il
pilote des outils existants (nmap, etc.), les enchaîne par phases, et produit un
rapport — en ne laissant **jamais** passer une action sur une cible hors
périmètre.

> ⚠️ **Usage légal strict.** Cet outil ne doit être utilisé que sur des systèmes
> que vous possédez ou que vous êtes **explicitement et par écrit** autorisé à
> tester. En France, l'accès non autorisé à un système est réprimé (art. 323-1
> et suivants du Code pénal), indépendamment de l'intention. Le `scope.yaml`
> doit refléter une autorisation réelle et vérifiable.

Le détail de la conception est dans [`CAHIER_DES_CHARGES.md`](CAHIER_DES_CHARGES.md).

## Principe directeur

**Rien ne s'exécute sans passer par le Scope Guard.** C'est un point de passage
unique, *deny-by-default* : une cible absente de la liste blanche est refusée, et
chaque décision (autorisée, bloquée, échouée) est écrite dans un journal
append-only chaîné par hash.

## État d'avancement

Suit le plan incrémental du cahier des charges (§12) :

- [x] 1. Scope Guard + tests (`src/scope_guard.py`, `tests/test_scope_guard.py`)
- [x] 2. Audit log append-only chaîné (`src/audit_log.py`)
- [x] 3. Adaptateur nmap passant par le Scope Guard (`src/adapters/nmap.py`)
- [x] 4. Moteur de phases recon → scan → web → vuln + CLI (`src/orchestrator.py`, `src/main.py`)
- [x] 5. Parsing JSON normalisé → reporting Markdown (`src/reporting/report.py`)
- [x] 6. Adaptateurs supplémentaires : httpx, nuclei, ffuf, nikto, sqlmap (`src/adapters/`)
- [ ] 7. Module mobile en lab (MobSF)
- [ ] 8. (Optionnel) bot Telegram authentifié

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Les outils externes (nmap...) doivent être présents dans le PATH — idéalement
dans un conteneur/VM Kali dédié (NFR-04).

## Mise en route

```bash
cp scope.yaml.example scope.yaml        # décrivez VOTRE périmètre autorisé
cp config.yaml.example config.yaml      # chemins, timeouts
```

`scope.yaml` et `config.yaml` sont volontairement ignorés par git.

### Vérifier une cible contre le périmètre

```bash
python src/main.py --scope scope.yaml verifier 10.10.10.5
python src/main.py --scope scope.yaml verifier 8.8.8.8      # -> BLOCKED
```

### Lancer une campagne (recon → scan) et produire un rapport

```bash
python src/main.py --scope scope.yaml run \
    --nom "lab-oct" --cibles 10.10.10.5 192.168.56.10 \
    --operateur omar --rapport rapport.md
```

### Lancer une seule phase / reprendre

```bash
python src/main.py --scope scope.yaml run --phase recon --cibles exemple-perso.com
python src/main.py --scope scope.yaml run --nom "lab-oct" --cibles 10.10.10.5 --reprendre
```

### Options des phases web / vuln

```bash
# ffuf (découverte de contenu) : activé en fournissant une wordlist
python src/main.py --scope scope.yaml run --cibles 10.10.10.5 --wordlist /usr/share/wordlists/dirb/common.txt

# sqlmap : test actif, exige intensite_max=agressive dans le scope
python src/main.py --scope scope.yaml --intensite agressive run --cibles http://10.10.10.5/app --sqlmap

# nuclei : ne remonter qu'à partir d'une sévérité
python src/main.py --scope scope.yaml run --cibles 10.10.10.5 --severite-min high
```

La phase **web** ne vise que les cibles dont le scan a révélé un service web ;
la phase **vuln** (nuclei) tourne de préférence sur les URLs vivantes trouvées
par httpx (logique inter-phases §6.1 du cahier).

## Tests

Le Scope Guard est le composant critique ; sa couverture est prioritaire.

```bash
pip install pytest
PYTHONPATH=src pytest -v
```

## Architecture (rappel)

```
Interface (CLI) ─▶ Scope Guard ─▶ Orchestrateur ─▶ Adaptateurs ─▶ Reporting
                        │                              │
                        └────────── Audit log ─────────┘  (append-only)
```

Ajouter un outil = écrire un adaptateur héritant de `BaseAdapter` (la
vérification Scope Guard y est déjà câblée) ; le moteur n'est pas touché (NFR-06).
