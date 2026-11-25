# LLM Optim LoRA

Traduire des énoncés anglais de programmation linéaire en JSON, puis comparer un modèle initial à son adaptation LoRA. Deux variables continues non négatives, deux ou trois contraintes, production/maximisation du profit et achat/minimisation du coût.

Le contrat de génération est documenté. Marc a validé les dix cas du pilote numérique v2. La qualification des templates pour le corpus, la génération du corpus et l'entraînement principal restent à réaliser. Voir `reports/plan_generate.md` et `reports/learning_notes.md`.

## Pilote de génération (étape 2)

Depuis la racine du dépôt, dans l'environnement Python où les dépendances de `requirements.txt` sont installées, sous PowerShell :

```powershell
$env:PYTHONPATH = 'src'
python -m lp_llm.generate
```

Cette commande produit cinq exemples par famille, à deux contraintes, dans `runs/generation_pilot_v2/` :

- `pilot.json` contient les références, les résultats bruts de HiGHS et les diagnostics de toutes les tentatives. Pour chaque sommet admis que l'on retrouve exactement par ses contraintes actives, `exact_result` donne la solution, l'objectif et les écarts en fractions sous forme de chaînes. Les écarts du diagnostic à quelques unités d'arrondi de zéro sont affichés à zéro après le contrôle de faisabilité.
- `review.md` présente les énoncés, les résultats et le statut de relecture. Le registre `reviews/pilot_v2.json` associe la validation de Marc à l'empreinte de la graine, de l'énoncé et de la référence. Une modification de ces éléments demande une nouvelle relecture.
- `failure.json` : écrit uniquement si le plafond de tentatives est atteint, avec les références tentées et leurs diagnostics.

Le profil `configs/pilot_v2.json` fixe trois exemples ciblés puis deux tirages sans condition géométrique supplémentaire par famille. Les cas ciblés exigent x1 et x2 strictement supérieurs à `1e-6`, ainsi que deux contraintes actives selon les tolérances du contrat. Les quatre cas libres suivent seulement l'admission numérique habituelle et peuvent aussi satisfaire naturellement la géométrie ciblée. Les motifs de rejet distinguent admission numérique et sélection géométrique. Le plafond reste de 100 tentatives par exemple demandé.

`geometry_matches_target` vaut `null` pour un cas libre. `interior_two_active` décrit la géométrie observée sur tout cas admis numériquement. Les tentatives v2 utilisent les graines 42 à 82 dans l'ordre, production puis mélange. Les 31 graines absentes de la liste des exemples ont été rejetées par le filtre géométrique. Chaque tentative utilise son propre `random.Random(seed)`. `--per-family` permet de modifier la taille du pilote et `--pilot-config` permet de choisir un autre profil.

Le premier pilote reste archivé dans `runs/generation_pilot_v1/`. La graine 51 donne le même tirage numérique dans `pilot_mixing_005` de la v1 et `pilot_production_001` de la v2, avec l'objectif et les inégalités de leurs familles respectives. Pour un bilan commun aux deux versions, compter ce tirage une fois.

Les candidats `needs_review` sont utilisables uniquement pour ce développement. Les exemples portent `split: development` et ne sont pas destinés aux tests finaux. Les contraintes inactives sont consignées ; inactivité à l'optimum ne signifie pas redondance. Aucune recherche de redondance générale ni exigence d'optimum unique n'est appliquée.

Marc a comparé les dix énoncés au JSON et recalculé les solutions, les objectifs, les écarts et les contraintes actives. Le rapport signale la redondance de la contrainte P de `pilot_mixing_005`, impliquée par la contrainte Q et les bornes.

## Dossier de validation

Le dossier `reviews/validation_pilote_v2/` contient le rapport d'anomalies et de relecture, le PDF à valider et sa source LaTeX. Chaque page reprend un énoncé, sa formulation mathématique et son JSON. La comparaison se fonde sur une transcription indépendante des énoncés.

Après avoir généré le pilote, régénérer le dossier depuis la racine du dépôt.

```powershell
$env:PYTHONPATH = 'src'
python -m lp_llm.audit_pilot
tectonic --untrusted reviews/validation_pilote_v2/validation.tex
```

Le contrôle écrit le rapport même s'il détecte une anomalie. Compiler la source LaTeX après une exécution réussie du contrôle.

## Lot de test indépendant

`data/human_test.jsonl` contient 20 cas rédigés par Codex sans réutiliser les gabarits du générateur. Le nom du fichier suit le plan initial. Une relecture par Marc reste à consigner.

- 10 cas de production et 10 cas d'achat ou de mélange. Chaque famille compte cinq cas à deux contraintes et cinq à trois contraintes. Huit cas combinent des plafonds et des minimums. Cinq optima sont sur un axe.
- Chaque ligne contient `id`, `split`, `family`, `statement` et `reference`. Seul `statement` est transmis au modèle avec la consigne commune. Le vérificateur utilise `reference` pour la notation. Ce lot est réservé à la comparaison avant/après LoRA.
- Marc a retiré le mot « linear » dans `independent_mixing_004`, `independent_mixing_009` et `independent_mixing_010`. La consigne commune précisera le format JSON attendu sans employer « linear program » ni « LP ». Présenter les résultats de ces trois cas individuellement.
- Les 20 références ont été comparées à une seconde transcription des énoncés et résolues avec HiGHS. Un calcul rationnel par énumération des sommets a retrouvé les 20 solutions et objectifs. Aucun doublon numérique détecté dans le lot ou avec les exemples retenus des pilotes v1 et v2. La comparaison avec le corpus synthétique se fera lorsqu'il sera généré.
- Empreinte SHA-256 de cette version (UTF-8, fins de ligne LF) `9d3ddd8e2d3fd240fa1499991c7b6fa1bbe6155640aea221cd02039ffcc6b5ea`. Toute correction de l'énoncé ou de la référence doit être tracée et appliquée aux deux évaluations.

## Tests

```powershell
python -m pytest -q -p no:cacheprovider
```

Les tests couvrent le schéma, le solveur, le pilote et le vérificateur. Un test montre qu'un second membre erroné sur une contrainte inactive peut conserver le même optimum tout en faisant échouer la comparaison de formulation. Un test du solveur volontairement faux est marqué `xfail`.
