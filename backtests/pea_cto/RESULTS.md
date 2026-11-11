# Backtests moyen terme (2 jours → 3 mois) pour PEA / CTO, sous freqtrade, frais inclus

Run du 11/11/2026 : freqtrade 2026.10, bougies journalières, 10 000 € au départ, 5 positions max (1 pour les indices).

## TL;DR

**Aucune des stratégies actives testées ne bat le buy & hold de façon robuste une fois les frais déduits.**
Celles qui semblent gagner sur les actions françaises le doivent à 1 à 3 titres exceptionnels en 2025.
La seule règle qui tient sur 25 à 30 ans est **le filtre SMA200 sur un ETF indiciel**. Elle ne crée pas
de rendement en plus : elle **divise à peu près par deux le drawdown**, à rendement égal (CAC) ou
inférieur (Nasdaq).

## Frais modélisés (par ordre, achat et vente)

| Support | Frais/ordre | Détail |
|---|---|---|
| Actions FR (PEA/CTO) | **0,35 %** | courtage ~0,1 % + spread ~0,05 % + **TTF 0,4 % à l'achat** (grandes capis FR, s'applique aussi en PEA), soit ~0,7 % l'aller-retour |
| ETF (PEA/CTO) | **0,15 %** | courtage ~0,1 % + spread ~0,05 %, pas de TTF |

Ordres au marché, exécutés à l'ouverture de la séance qui suit le signal. Fiscalité non incluse (voir plus bas).

## 1. Univers actions PEA : ~118 actions FR/UE (SBF120 élargi), sept. 2022 → nov. 2026

In-sample = avant le 01/07/2024, out-of-sample (OOS) = après.

| Stratégie | Horizon | CAGR net | Max DD | CAGR IS | CAGR OOS | Trades | CAGR brut (0 frais) |
|---|---|---|---|---|---|---|---|
| PullbackRSI2 (repli RSI2 en tendance) | ~5 j | **-19,5 %** | -61,9 % | -15,4 % | -23,0 % | 817 | +5,6 % |
| TrendBreakout (cassure 55 j / sortie 20 j) | ~42 j | 15,7 % | -17,9 % | 5,5 % | 24,3 % | 122 | 20,1 % |
| MomentumRotation (top 5 momentum 6-1 mois) | ~22 j | 16,8 % | -24,9 % | -4,9 % | 37,0 % | 170 | 23,3 % |
| *Buy & hold équipondéré de l'univers* | – | *12,1 %* | *-14,4 %* | *7,7 %* | *14,8 %* | – | – |
| *CAC 40 (indice prix, sans dividendes)* | – | *7,3 %* | *-16,7 %* | *11,2 %* | *3,9 %* | – | – |

**Pourquoi les +16 % sont trompeurs** (`results/concentration.csv`) : on retire les meilleurs titres et on regarde ce qui reste.

| Stratégie | Tous titres | Sans le meilleur | Sans les 3 meilleurs |
|---|---|---|---|
| MomentumRotation | 16,8 % | **0,2 %** (sans Nanobiotix) | -4,5 % |
| TrendBreakout | 15,7 % | 8,2 % (sans Exail) | 2,6 % |

Par année (`results/yearly.csv`), presque toute la surperformance tombe en **2025** (+89 % et +100 %).
En 2022-2024, les deux stratégies font moins bien que le buy & hold.

Robustesse des paramètres (`results/summary.csv`, lignes GRID, 9 combinaisons par stratégie) :
- **RSI2** : négatif net de frais dans les 9 cas sur 9 (de -13 % à -30 %/an). La TTF plus les allers-retours tuent le court terme sur actions FR.
- **Breakout** : de -4 % à +26 % selon les paramètres, et le in-sample est souvent négatif. Pas d'edge stable.
- **Momentum** : top 3 et top 5 positifs, top 10 négatif, in-sample ≈ 0. Tout repose sur 2025.

Biais qui **gonflent** ces résultats :
- **Survivorship** : l'univers contient les membres *actuels* du SBF120, donc les titres qui ont monté. Ça favorise surtout le momentum et le breakout.
- Fractions d'action autorisées.

## 2. Historique long sur indices (proxy ETF éligibles PEA), frais ETF

| Série | Stratégie | CAGR | Max DD | CAGR 1re moitié | CAGR 2e moitié | Expo | Trades |
|---|---|---|---|---|---|---|---|
| Nasdaq-100 2001-2026 | PullbackRSI2 | 1,5 % | -14,7 % | 0,9 % | 1,9 % | 13 % | 202 |
| | TrendBreakout | 4,6 % | -19,3 % | 1,5 % | 7,2 % | 45 % | 69 |
| | **IndexSMA200** | **8,6 %** | **-32,3 %** | 2,9 % | 13,4 % | 62 % | 29 |
| | *Buy & hold* | *13,2 %* | *-53,7 %* | 6,1 % | 19,4 % | 100 % | – |
| CAC 40 1991-2023 | PullbackRSI2 | -0,3 % | -29,3 % | 0,4 % | -1,1 % | 12 % | 208 |
| | TrendBreakout | -1,7 % | -62,6 % | 0,5 % | -3,7 % | 35 % | 87 |
| | **IndexSMA200** | **4,3 %** | **-34,7 %** | 8,0 % | 0,8 % | 55 % | 32 |
| | *Buy & hold* | *4,4 %* | *-65,3 %* | 7,5 % | 1,4 % | 100 % | – |

Indices *prix*, donc sans dividendes, et le cash hors marché ne rapporte rien ici. En réel, un ETF
capitalisant récupère les dividendes (~2-3 %/an sur le CAC) quand il est investi, et le cash peut être
placé sur un fonds monétaire. Ça rapproche un peu le SMA200 du buy & hold. Les données CAC 1991-2023
n'ont que les clôtures (ouverture approximée par la clôture de la veille).

## Conclusion pratique

1. **Pas de trading court terme (2-10 j) sur actions françaises** : la TTF de 0,4 % plus le spread
   absorbent tout l'edge (+0,17 %/trade brut, -0,53 % net).
2. **Breakout et momentum sur actions** : rien de prouvé. Le backtest sur 4 ans est porté par 1 à 3 titres
   et souffre du biais du survivant. À ne pas déployer sur cette base.
3. **Ce qui tient : un ETF large (CAC 40 / MSCI World / S&P 500 / Nasdaq éligibles PEA) + règle SMA200
   avec bande de 2 %.** C'est une stratégie de **gestion du risque** : environ 1 trade par an, durée
   médiane de 3 à 5 mois, drawdown divisé par ~2. Le prix à payer est un rendement égal ou inférieur au
   buy & hold. Si l'objectif est le rendement max sur 10 ans et plus, le buy & hold de l'ETF reste
   meilleur.
4. **Enveloppe** : stratégie active, donc **PEA** (pas d'impôt à chaque vente ; prélèvements sociaux
   seulement à la sortie après 5 ans). Sur CTO, chaque vente gagnante est taxée à la flat tax (~30 %),
   ce qui pénalise encore plus les stratégies qui tradent.

## Reproduire

```bash
pip install freqtrade
python fetch_data.py               # télécharge + convertit les données
python analyze.py                  # lance tous les backtests -> results/
# un backtest seul :
python ft.py backtesting --config config_pea.json --strategy TrendBreakout --fee 0.0035 --timerange 20220101-
```

`ft.py` fait tourner freqtrade hors ligne sur des actions. Il injecte des marchés synthétiques à la place
de l'API d'exchange et **désactive le remplissage des week-ends**. Par défaut freqtrade crée des bougies
samedi/dimanche (pensé pour la crypto 24/7), ce qui fausse SMA, RSI et prix d'exécution sur actions.
Les métriques « wallet » du rapport freqtrade restent faussées par l'absence de week-ends : utiliser
`analyze.py`, qui recalcule une equity mark-to-market journalière.
