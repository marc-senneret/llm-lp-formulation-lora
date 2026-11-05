# Notes

Journal du projet : décisions prises, raisons, ce qui a été réellement exécuté. 
Les valeurs exactes de la machine sont dans `runs/computer_state.json`.

## Étape 1A — Diagnostic de l'environnement

**Statut : exécuté** (diagnostic.ipynb, `pip check` et comparaison des versions installées avec `requirements.txt`).

### Décisions

- **Windows natif, pas WSL.** : WSL reste un recours si le smoke test d'entraînement échoue sous Windows. mais c'est quand même plus simple de rester sous windows. On verra si il faut utilisé des machines distantes

- **Miniconda base.** Raison : économiser du disque (torch + CUDA pèse plusieurs Go et serait dupliqué). Torch 2.11+cu128 était déjà dans le base ; seule la pile Hugging Face s'ajoute. (Risque assumé , conflits avec d'autres projets utilisant ce Python. `pip check` propre, `requirements.txt` aligné sur l'installé. )
- **`requirements.txt`** Les 14 paquets listés correspondent exactement aux versions installées (vérifié avec `pip list`). 

### Remarques

- « CUDA installé » n'est pas « `torch.cuda.is_available()` == `True` ». Les wheels PyTorch embarquent leur propre CUDA (ici 12.8, suffixe `+cu128`), indépendant d'un éventuel CUDA Toolkit système. Ce qui compte : un build torch compilé avec CUDA, un driver assez récent pour ce runtime, et un GPU visible. D'ailleurs attention à ca s'il faut compiler une extension, genre flash-attention
- `torch.version.cuda` indique la version avec laquelle torch a été compilé, pas qu'il fonctionne. 


### Points ouverts

- Le chargement du modèle et la génération courte n'ont pas encore été testés.
- La révision exacte du modèle et du tokenizer (`Qwen/Qwen2.5-1.5B-Instruct`) n'est pas encore figée.

## Étape 1B — Validation du schéma (`src/lp_llm/schema.py`)

**Statut : implémenté et exécuté** ( 62 tests passés).

**Périmètre de 1B : la forme seulement.** Le schéma dit si un JSON est une formulation bien formée dans le périmètre. 
Il ne dit ni si elle est correcte par rapport à l'énoncé, ni si elle est faisable ou bornée (rôle de la comparaison et du solveur).
La normalisation et la comparaison de formulations (`>=` → `<=`, ordre des contraintes) sont prévues, non implémentées.

### Décisions

- **Retour `(bool, message)`**, pas d'exception : une sortie invalide du modèle est un résultat de mesure, pas une erreur du programme. Le message sert à compter les types d'échec à l'évaluation. Les tests comparent un **fragment** du message, pas la phrase entière.
- **`null` = borne supérieure infinie, uniquement.** Refusés : `Infinity`, `NaN`, booléens, chaînes, `null` en coefficient ou en `rhs`. Raison : une seule écriture de l'infini, conforme à l'invariant « nombres finis ; `null` = borne infinie seulement ». `json.loads` accepte pourtant `NaN`/`Infinity` : le validateur doit donc les rejeter lui-même.
- **Bornes `[a, b]` : `a` fini avec `a ≥ 0`, `b` = `null` ou fini avec `b ≥ a`.** Choix : `a` peut être strictement positive (`x ≥ a ≥ 0`), pas seulement 0. 
- **Champs en trop refusés** (racine, `objective`, chaque contrainte)
- **Périmètre structurel** : variables exactement `["x1", "x2"]` ; 2 à 3 contraintes ; 2 coefficients partout ; sens `max`/`min` pour l'objectif, `<=`/`>=`/`=` pour les contraintes.
- **`get_valid_json` attrape `ValueError`, `TypeError`, `RecursionError`.** 
- **Tests (`tests/test_schema.py`)** : un seul champ cassé par cas à partir de l'exemple atelier, pour qu'un contrôle n'en masque pas un autre.

### Erreurs rencontrées

- `is_number` : la 1ʳᵉ version appelait `math.isinf` avant le test de type (`TypeError` sur `None` et `"abc"`, `OverflowError` sur `10**400`). Corrigée : test de type d'abord, les `int` sont toujours finis, `math.isfinite` pour les `float`. Une 2ᵉ version avait une condition inversée (le cas valide était rejeté) ; seule une exécution l'a révélé.
- Des cas de test cassaient deux choses à la fois ou en masquaient d'autres (ex. `constraints: [5]` rejeté pour « moins de 2 contraintes »), donc ne testaient pas ce qu'ils annonçaient.
- `src/lp_llm/__init__.py` contenait par erreur le texte de `pytest.ini` ; `pytest.ini` avait des lignes indentées (erreur d'analyse).

### Remarques

- Valide au sens du schéma ne veut pas dire correct : trois niveaux distincts, donc trois lignes de résultats (validité structurelle, exactitude de formulation, succès de résolution).

### Points ouverts

- Les clés dupliquées dans un objet JSON (`{"a":1,"a":2}`) sont écrasées silencieusement par `json.loads` ; le validateur ne peut pas les détecter.
- Comparaison et normalisation de formulations : à faire (nécessaires à la métrique d'exactitude).
- Le message d'erreur est un texte libre : un code court stable (`"rhs_not_number"`) faciliterait le comptage des échecs à l'évaluation.
