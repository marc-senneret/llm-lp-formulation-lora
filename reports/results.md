# Résultats — SFT LoRA de Qwen2.5-1.5B pour formuler des programmes linéaires

*Itération v1, 25 novembre 2026. Tous les chiffres ci-dessous ont été **exécutés** et mesurés. Rien n'est extrapolé.*

## En bref

Un adaptateur LoRA (r=16, 0,28 % des paramètres) a été entraîné **en 4 min 15 s sur une RTX 4060** (une époque, 300 exemples). La formulation exacte d'un LP à partir d'un énoncé anglais passe de **0/80 à 35/80** sur un test synthétique de gabarits jamais vus, et de **0/20 à 5/20** sur 20 énoncés rédigés indépendamment. La conformité JSON passe de 0 % à 96 % sur le synthétique (77/80) et à 90 % sur l'indépendant (18/20).

Le gain dépasse la mise en forme. Même en retirant les balises Markdown du modèle de base, celui-ci ne formule exactement que 10/80 et 1/20 problèmes.

Une limite nette a été trouvée et expliquée : **0/40 en mélange** sur le synthétique. L'analyse en *teacher forcing* l'attribue à un token de décision sous-appris, aggravé par une pénalité de répétition héritée du décodage ([diagnostic](diagnostic_sens_contraintes.md)).

## Tâche

L'énoncé anglais d'un problème à 2 variables continues non négatives et 2 ou 3 contraintes doit être traduit en JSON de programme linéaire : `variables`, `objective`, `constraints`, `bounds`. Le modèle formule et SciPy `linprog` (HiGHS) résout. Il y a deux familles : production (max profit, plafonds) et mélange (min coût, exigences minimales).

## Protocole

| Élément | Choix |
| --- | --- |
| Modèle | `Qwen/Qwen2.5-1.5B-Instruct`, révision `989aa79…`, BF16, révision épinglée |
| Données | 16 gabarits répartis par lignée **avant** tirage : 8 train, 4 validation, 4 test. Le corpus fait 300 / 60 / 80 exemples, sans doublon de texte ni de formulation normalisée entre splits, avec empreintes SHA-256 dans un manifeste. Les 16 gabarits ont été relus par un humain, et un audit indépendant a été fait par script. |
| Test indépendant | 20 énoncés rédigés hors gabarits, dont 8 mêlent plafonds et minimums ; « linear » est absent de 3 énoncés |
| Entraînement | Boucle PyTorch et PEFT ; loss **uniquement sur le JSON cible** et le token de fin, masque vérifié en décodant les tokens supervisés des 360 exemples ; lr 1e-4, batch effectif 16, 19 pas, gradient checkpointing |
| Évaluation | Même consigne, même décodage glouton et mêmes énoncés avant et après. Notation **stricte** : pas de réparation de sortie, toute sortie invalide compte comme un échec. |
| Vérificateur | 4 niveaux indépendants : (1) JSON conforme au schéma ; (2) formulation exacte après normalisation (ordre des contraintes, `>=`→`<=`, facteurs positifs) ; (3) résolution du problème prédit ; (4) solution prédite faisable et optimale **sur le problème de référence**, avec tolérances relatives. Le niveau 4 ne compare pas les vecteurs solution, car les optima peuvent être multiples. |

## Résultats

### Scores stricts

| Mesure | Synthétique, base | Synthétique, LoRA | Indépendant, base | Indépendant, LoRA |
| --- | ---: | ---: | ---: | ---: |
| JSON conforme au schéma | 0/80 | **77/80** | 0/20 | **18/20** |
| Formulation exacte | 0/80 | **35/80** | 0/20 | **5/20** |
| Problème prédit résolu | 0/80 | 77/80 | 0/20 | 17/20 |
| Solution optimale sur la référence | 0/80 | **37/80** | 0/20 | **8/20** |

Diagnostic hors score officiel : en retirant seulement les balises Markdown, le modèle de base atteint 10/80 et 1/20 formulations exactes.

### Ventilations de la formulation exacte

| Sous-ensemble | Avant | Après |
| --- | ---: | ---: |
| Synthétique, production | 0/40 | 35/40 |
| Synthétique, mélange | 0/40 | **0/40** |
| Synthétique, optimum sur un axe | 0/40 | 17/40 |
| Synthétique, optimum à deux variables positives | 0/40 | 18/40 |
| Indépendant, production | 0/10 | 3/10 |
| Indépendant, mélange | 0/10 | 2/10 |
| Indépendant, sens homogènes | 0/12 | 4/12 |
| Indépendant, plafonds et minimums mêlés | 0/8 | 1/8 |

## Analyse des erreurs

- **Format.** Le modèle de base entoure presque toutes ses réponses de balises Markdown malgré la consigne, et 16/20 réponses décrivent mal les bornes. Après LoRA, il n'y a plus aucune balise.
- **Inversion `>=` → `<=` en mélange.** Les 37 JSON de mélange conformes ont des coefficients justes mais remplacent les minimums par des plafonds. Une sonde en teacher forcing (`src/lp_llm/probe.py`) montre trois choses :
  1. tout se joue sur le **sens de la première contrainte**, les suivantes recopiant ce sens avec P ≥ 0,99 ;
  2. au premier sens, P(`>=`) passe de 0,001 (base) à seulement 0,54 sur le train lui-même, ce qui indique un **sous-apprentissage** que la loss moyenne (0,029) masque ;
  3. la `repetition_penalty` de 1,1 héritée de Qwen pénalise le token ` ">`, présent dans la consigne, et pas ` "<`, qui en est absent. L'argmax tombe alors à 0/30 en validation.

  La sonde pénalisée prédit le sens généré dans 78/78 cas du test synthétique.
- **Autres erreurs sur l'indépendant.** On observe des contraintes omises, une permutation complète de x1 et x2, et une confusion entre limites et consommations. Trois cas atteignent l'optimum de référence malgré une contrainte omise. C'est exactement ce que le niveau 4 du vérificateur sépare du niveau 2.

## Limites

- Échelle jouet : 2 variables, 2 ou 3 contraintes, 300 exemples d'entraînement et une seule graine. Avec 20 cas indépendants, une différence de quelques cas n'est pas significative.
- Le corpus v1 associe toujours une famille à un seul sens d'inégalité. L'adaptateur a appris cette corrélation, ce qui pénalise les énoncés à sens mixtes (1/8).
- Le test synthétique a été généré par lots de 8 avec padding à gauche, et le test indépendant cas par cas. Sur 8 cas de contrôle, les scores sont identiques, mais 2 textes sur 8 diffèrent.
- Le diagnostic a été établi après lecture des sorties de test. Une v2 réévaluée sur ces tests serait une itération, pas une mesure à l'aveugle.
- L'effet du mot « linear » n'est pas isolé, faute d'énoncés appariés.

## Prochaine itération (prévue, non exécutée)

Le protocole est fixé avant exécution dans [diagnostic_sens_contraintes.md](diagnostic_sens_contraintes.md#7-protocole-des-expériences-suivantes-fixé-avant-exécution) :

- E1 : décodage sans pénalité, mesuré sur la validation ;
- E2 : 3 époques avec un checkpoint par époque, sélection sur la formulation exacte en validation, puis une seule évaluation finale.

## Reproductibilité

Environnement : Windows 11, RTX 4060 (8 Go), torch 2.8.0+cu128, transformers 5.22.1, peft 0.21.2, SciPy 1.16.1. Les commandes sont dans le [README](../README.md). Le journal complet des décisions et des mesures est dans [learning_notes.md](learning_notes.md). Les prédictions brutes et les journaux sont versionnés dans `runs/` : `base_*_v1.json`, `lora_*_v1.json`, `lora_v1/training.json` et `probe_sense_lora_v1.json`. Les poids de l'adaptateur (17 Mo) ne le sont pas.
