# LLM Optim LoRA

Traduire des énoncés anglais de programmation linéaire en JSON, puis comparer un modèle initial à son adaptation LoRA. Deux variables continues non négatives, deux ou trois contraintes, production/maximisation du profit et achat/minimisation du coût.

Le contrat de génération est documenté. Le pilote numérique est implémenté ; la qualification humaine des templates, le corpus et l'entraînement principal restent à réaliser. Voir `reports/plan_generate.md` et `reports/learning_notes.md` pour les statuts et preuves.

## Pilote de génération (étape 2)

Depuis la racine du dépôt, dans l'environnement Python où les dépendances de `requirements.txt` sont installées, sous PowerShell :

```powershell
$env:PYTHONPATH = 'src'
python -m lp_llm.generate
```

Cette commande produit cinq exemples par famille, à deux contraintes, dans `runs/generation_pilot_v2/` :

- `pilot.json` : configurations et templates utilisés, graines, exemples, références, résultats du solveur, diagnostics de toutes les tentatives et taux d'admission.
- `review.md` : dix énoncés avec leurs références et résultats pour relecture par Marc.
- `failure.json` : écrit uniquement si le plafond de tentatives est atteint, avec les références tentées et leurs diagnostics.

Le profil `configs/pilot_v2.json` fixe trois exemples ciblés puis deux tirages sans condition géométrique supplémentaire par famille. Les cas ciblés exigent x1 et x2 strictement supérieurs à `1e-6`, ainsi que deux contraintes actives selon les tolérances du contrat. Les quatre cas libres suivent seulement l'admission numérique habituelle et peuvent aussi satisfaire naturellement la géométrie ciblée. Les motifs de rejet distinguent admission numérique et sélection géométrique. Le plafond reste de 100 tentatives par exemple demandé.

L'ordre est production puis mélange, avec une graine incrémentée après chaque tentative, admise ou rejetée. Chaque tentative utilise son propre `random.Random(seed)`. Aucun appel LLM au rendu. Les quotas et règles d'admission du corpus final sont inchangés ; le profil géométrique s'applique au pilote uniquement. `--per-family` permet de modifier sa taille, avec un total au moins égal au nombre ciblé ; `--pilot-config` permet de choisir un autre profil.

Le premier pilote (graines 42 à 51, neuf solutions sur un axe) reste conservé dans `runs/generation_pilot_v1/`. La version 2 ne le remplace pas silencieusement.

Les candidats `needs_review` sont utilisables uniquement pour ce développement. Les exemples portent `split: development` et ne sont pas destinés aux tests finaux. Les contraintes inactives sont consignées ; inactivité à l'optimum ne signifie pas redondance. Aucune recherche de redondance générale ni exigence d'optimum unique n'est appliquée.

Pour relire : comparer le sens de l'objectif, les deux coefficients de chaque ligne, le sens des inégalités, les limites, les unités et les bornes avec chaque énoncé. La relecture humaine reste en attente, même lorsque le solveur renvoie `optimal`.

## Tests

```powershell
python -m pytest -q -p no:cacheprovider
```

Les tests couvrent le schéma, le solveur et le pilote, notamment sa reproductibilité, les résultats numériques inadmissibles, les champs manquants, les quotas géométriques et l'arrêt au plafond de tentatives. Un exemple montre qu'un second membre erroné sur une contrainte lâche peut conserver le même optimum : la comparaison de formulation entière reste nécessaire et reste à implémenter. Un test du solveur volontairement faux est marqué `xfail`.
