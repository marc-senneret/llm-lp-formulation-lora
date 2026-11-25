# Diagnostic — inversion des contraintes `>=` en `<=` après LoRA v1

*Rapport technique, 25 novembre 2026. Statut : diagnostic **exécuté** ; expériences E1 et E2 **prévues**, protocole fixé avant exécution.*

## Résumé

Après une époque de SFT LoRA (`runs/lora_v1`), Qwen2.5-1.5B-Instruct formule exactement 35/40 problèmes de production du test synthétique, mais 0/40 problèmes de mélange. Les 37 JSON de mélange conformes au schéma remplacent toutes les exigences minimales `>=` par des plafonds `<=`.

Une sonde en *teacher forcing* (`src/lp_llm/probe.py`) mesure la probabilité du token de sens de chaque contrainte. Elle montre que l'échec tient à **une seule décision**, le sens de la **première** contrainte, et qu'il combine deux causes :

1. **Sous-apprentissage (H1).** Le modèle de base attribue une probabilité d'environ 0,001 à `>=` sur la première contrainte de mélange. Après 19 pas d'optimisation, l'adaptateur la remonte seulement à 0,54 en moyenne sur les exemples d'entraînement eux-mêmes, et à 0,35 en validation.
2. **Biais de décodage (H2).** La génération hérite d'une `repetition_penalty` de 1,1 de la configuration de Qwen. La pénalité s'applique aussi aux tokens du prompt. Or la consigne système contient le token ` ">` mais pas ` "<`. Au premier sens, seul `>=` est donc pénalisé. Avec la pénalité, P(`>=`) tombe de 0,54 à 0,21 sur le train et de 0,35 à 0,05 en validation. L'argmax devient `<=` dans 30 cas de validation sur 30.

Une fois le premier sens choisi, le modèle recopie ce sens sur les contraintes suivantes avec une probabilité d'au moins 0,99. Une erreur sur un seul token suffit à rendre tout le problème faux.

La loss de validation (0,051) ne pouvait pas révéler ce défaut, car un token raté pèse environ 1 % de la loss par exemple.

## 1. Contexte

| Élément | Valeur |
| --- | --- |
| Modèle | `Qwen/Qwen2.5-1.5B-Instruct`, révision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, BF16 |
| Adaptateur | `runs/lora_v1` : r=16, alpha=32, dropout 0,05, modules `q,k,v,o_proj`, lr 1e-4 constant, 1 époque, 300 exemples, batch effectif 16, soit 19 pas |
| Loss | 0,0292 en entraînement (moyenne sur l'époque), 0,0512 en validation |
| Corpus | `data/corpus_v1_manifest.json` : 300 / 60 / 80, gabarits disjoints entre splits |
| Décodage d'évaluation | glouton, 256 nouveaux tokens au maximum, `repetition_penalty` non fixée dans `evaluate.py`, donc héritée de Qwen (1,1) |

Résultats v1 sur la formulation exacte, en notation stricte (voir `learning_notes.md`) :

| Lot | Avant LoRA | Après LoRA |
| --- | ---: | ---: |
| Test synthétique, production | 0/40 | 35/40 |
| Test synthétique, mélange | 0/40 | **0/40** |
| Test indépendant (20) | 0/20 | 5/20 |

## 2. Observations initiales

- **Test synthétique, mélange.** 35 des 38 JSON lisibles ont `min` et uniquement des `<=`. Les coefficients et les seconds membres sont corrects et positifs. Le problème prédit est trivialement résolu par x = 0. Deux réponses utilisent `None` et une a 3 coefficients par contrainte.
- **Test indépendant.** La première contrainte de mélange est générée en `>=` dans 2 cas sur 10 : `mixing_003` et `mixing_004`, qui sont les deux formulations exactes de mélange. Les trois `>=` des cas de production sont perdus : deux sont remplacés par `<=` et un est omis.
- **Les données d'entraînement ne sont pas en cause.** Les 150 exemples de mélange du train ont `min` et uniquement des `>=`. La cible supervisée est `json.dumps(reference)` (`train.py:36`) et son décodage est vérifié token par token (`train.py:47`).
- **Tokenisation.** Dans la cible, le sens est décidé par un seul token, ` ">` (`>=`) ou ` "<` (`<=`), suivi du token commun `=",`. Dans la consigne système, la liste `("<=", ">=", or "=")` est tokenisée en ` ("<`, `=",`, ` ">`, … Le token ` ">` figure donc dans le prompt, alors que ` "<` n'y figure pas.

## 3. Hypothèses

- **H1, sous-apprentissage.** Une époque à lr 1e-4 ne suffit pas à renverser l'a priori du modèle de base en faveur de `<=` sur la première contrainte.
- **H2, biais de décodage.** La pénalité de répétition de 1,1 pénalise ` ">` (présent dans le prompt) et pas ` "<`. Elle fait basculer la décision quand P(`>=`) est modérée.
- **H3, généralisation lexicale (alternative).** L'adaptateur aurait appris `>=` pour les tournures du train (« at least », « cover ») sans le transférer à celles du test (« Minimum total », « no less than »).

## 4. Méthode

`python -m lp_llm.probe --adapter runs/lora_v1 --output runs/probe_sense_lora_v1.json`

Pour chaque exemple, la sonde construit la séquence d'entraînement : consigne, énoncé et JSON de référence (`encode_example`). Elle fait une seule passe avant et lit, à chaque position de token de sens, la distribution du token suivant de deux façons :

- **brute** : softmax des logits ;
- **pénalisée** : la règle de `RepetitionPenaltyLogitsProcessor` (logit / 1,1 si positif, × 1,1 sinon) est appliquée à tous les tokens du préfixe, prompt compris, comme le fait `generate`. Le code de fusion de configuration de Transformers 5.22.1 a été lu : les champs `None` de la `GenerationConfig` passée sont complétés par `model.generation_config`.

La sonde enregistre P(sens de référence), P(` ">`), P(` "<`) et la correction de l'argmax sur tout le vocabulaire. Elle tourne avec l'adaptateur désactivé (base) puis activé (LoRA), sur les 4 lots (1 150 positions de sens), en environ 2 minutes sur RTX 4060.

**Limite.** Le préfixe est celui de la référence et non celui que génère le modèle. Pour la première contrainte, il ne diffère de la génération que par les coefficients déjà écrits.

## 5. Résultats

### 5.1 Première contrainte, famille mélange (sens de référence `>=`)

| Lot | n | Base, P brute | LoRA, P brute | LoRA, argmax brut correct | LoRA, P pénalisée | LoRA, argmax pénalisé correct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | 150 | 0,001 | 0,542 | 87/150 | 0,208 | 32/150 |
| Validation | 30 | 0,001 | 0,353 | 11/30 | 0,054 | **0/30** |
| Test synthétique | 40 | 0,001 | 0,265 | 0/40 | 0,030 | **0/40** |
| Test indépendant | 10 | 0,001 | 0,540 | 6/10 | 0,218 | **2/10** |

### 5.2 Contraintes suivantes (sens identique à la première dans le corpus)

| Lot | LoRA, P brute en mélange (`>=`) | LoRA, P brute en production (`<=`) |
| --- | ---: | ---: |
| Train | 1,000 | 0,995 |
| Validation | 0,999 | 0,998 |
| Test synthétique | 0,999 | 0,995 |

Sachant le premier sens, les suivants sont quasi certains. Sur le test indépendant, les contraintes suivantes de sens **opposé** à la première sont rares (6 `<=` en mélange, 1 `>=` en production). P vaut 0,741 pour les premières et 0,003 pour la seconde : l'adaptateur a appris « tous les sens identiques », une régularité du corpus v1.

### 5.3 Première contrainte, famille production (`<=`)

En production, LoRA donne P = 0,84 à 0,94 en brut et 0,98 à 0,99 en pénalisé. L'argmax est correct dans 100 % des cas sur tous les lots. La pénalité **aide** ici, car elle affaiblit le concurrent ` ">`.

### 5.4 Concordance avec la génération réelle

Pour le premier sens, la prédiction de l'argmax pénalisé correspond au sens effectivement généré dans **78/78** JSON lisibles du test synthétique et **19/20** du test indépendant. L'argmax brut atteint 78/78 et 16/20. La pénalité explique mieux le comportement observé.

## 6. Discussion

- **H1 est confirmée.** Même sans pénalité et sur les exemples d'entraînement, P(`>=`) vaut seulement 0,54 en moyenne au premier sens, avec un argmax correct dans 58 % des cas. Le modèle n'a pas fini d'apprendre cette décision, ce qui n'est pas un défaut de généralisation. La loss moyenne basse est dominée par les quelque 100 tokens faciles de chaque cible.
- **H2 est confirmée comme facteur aggravant.** La pénalité retire environ 1 à 2 nats de log-odds à `>=`. Elle fait passer l'argmax correct de 87 à 32 cas sur 150 en entraînement et de 11 à 0 cas sur 30 en validation. Ce biais est un artefact du décodage, pas du modèle. Il provient d'un paramètre hérité, et non d'un choix de conception documenté comme tel.
- **H3 est partiellement soutenue.** La probabilité baisse du train (0,54) à la validation (0,35) puis au test synthétique (0,27), ce qui indique un écart de généralisation entre gabarits. L'écart reste secondaire tant que le train lui-même n'est pas appris.
- **Pourquoi l'erreur est catastrophique.** Le corpus v1 associe toujours mélange, `min` et uniquement des `>=`, et production, `max` et uniquement des `<=`. L'adaptateur exploite cette corrélation en recopiant le premier sens. Une seule décision incertaine, amplifiée par le décodage glouton, renverse donc tout le problème. Le même mécanisme pénalise les énoncés indépendants à sens mixtes.
- **La loss de validation ne suffit pas pour sélectionner un checkpoint.** Il faut une mesure qui voit les décisions rares mais critiques : exactitude de formulation en génération, ou argmax du premier sens.

## 7. Protocole des expériences suivantes (fixé avant exécution)

Règles communes : le test synthétique et le test indépendant ne servent **qu'une fois**, après le gel des choix sur la validation. La consigne système reste inchangée. Les résultats v1, obtenus avec la pénalité de 1,1, restent publiés tels quels.

### E1 — Décodage sans pénalité (aucun entraînement)

- **Question** : quelle part de l'échec vient de H2 ?
- **Action** : ajouter à `evaluate.py` une option `--repetition-penalty`, enregistrée dans le JSON de sortie, puis évaluer `runs/lora_v1` sur la **validation** (60 cas) avec 1,1 et avec 1,0.
- **Prédiction** : la formulation exacte en mélange de validation passe de 0 à au plus 11/30, borne donnée par l'argmax brut. La production ne se dégrade pas, ou peu.
- **Décision** : le décodage final est **glouton sans pénalité (1,0)**. Ce choix repose sur le mécanisme démontré ci-dessus : la pénalité biaise une sortie structurée dont les tokens se répètent par construction. Il ne repose pas sur un score de test. Le modèle de base sera réévalué avec ce décodage pour garder une comparaison appariée.

### E2 — Entraîner plus longtemps

- **Question** : H1 se corrige-t-elle avec plus d'optimisation ?
- **Variable unique** : le nombre d'époques passe de 1 à **3** (57 pas). Graine, lr constant 1e-4, LoRA, données et ordre de mélange par époque restent ceux de `train.py`.
- **Modifications de code** : sauvegarder l'adaptateur et la loss de validation **à la fin de chaque époque** (`runs/lora_v2/epoch_{1,2,3}`). L'époque 1 doit reproduire `lora_v1` aux écarts numériques GPU près, avec le même ordre d'exemples (contrôle de déterminisme).
- **Mesures par époque, sur la validation uniquement** :
  1. sonde : P et argmax du premier sens, brut et pénalisé, par famille ;
  2. génération avec le décodage final : format, formulation exacte, solution de référence, par famille ;
  3. loss de validation.
- **Critère de sélection, fixé maintenant** : la formulation exacte en validation (60 cas) la plus élevée. En cas d'égalité, la plus petite époque.
- **Prédiction** : P(`>=`) au premier sens dépasse 0,9 sur le train et l'argmax brut est correct sur au moins 90 % de la validation à l'époque 2 ou 3. Le risque est le surapprentissage des gabarits du train (H3), à surveiller par l'écart entre train et validation dans la sonde.
- **Évaluation finale, une seule fois** : le checkpoint retenu et le modèle de base, avec le décodage final, sur le test synthétique (80) et le test indépendant (20). Rapport par famille et par géométrie, avec gains et régressions cas par cas.

### Ce qui reste hors protocole

Il n'y aura ni recherche d'hyperparamètres, ni changement de lr ou de rang, ni rééquilibrage du corpus dans cette itération. Si E2 ne suffit pas, la piste suivante est la donnée : des exemples d'entraînement à sens mixtes (plafond et minimum dans un même problème), qui casseraient la corrélation famille ↔ sens. Elle fera l'objet d'un rapport séparé.

## 8. Menaces à la validité

- **Préfixe de référence et préfixe généré.** La sonde utilise le préfixe de référence. La concordance mesurée en 5.4 (78/78 et 19/20) limite ce risque pour la première contrainte.
- **Mode d'exécution.** Le test synthétique v1 a été généré par lots de 8 avec padding à gauche, et 6 sorties sur 8 de contrôle étaient identiques au texte près. E1 et E2 garderont le même mode pour les deux modèles comparés.
- **Taille de la validation.** Avec 30 cas par famille, une différence de quelques cas n'est pas significative. Le critère de sélection reste grossier, et c'est assumé.
- **Effet du mot « linear ».** Il n'est toujours pas isolé, car aucun appariement n'existe dans le test indépendant.

## 9. Reproductibilité

| Artefact | Contenu |
| --- | --- |
| `src/lp_llm/probe.py` | sonde du sens par teacher forcing, brute et pénalisée |
| `runs/probe_sense_lora_v1.json` | 1 150 positions × {base, LoRA} × {brut, pénalisé} |
| `runs/lora_synthetic_v1.json`, `runs/lora_independent_v1.json` | générations v1 utilisées pour la concordance |
| Environnement | RTX 4060, torch 2.8.0+cu128, transformers 5.22.1, peft 0.21.2 (voir `runs/lora_v1/training.json`) |

Commande : `$env:PYTHONPATH = 'src'; python -m lp_llm.probe --adapter runs/lora_v1 --output runs/probe_sense_lora_v1.json`
