# Notes

Journal du projet : décisions prises, raisons, ce qui a été réellement exécuté. 
Les valeurs exactes de la machine sont dans `runs/computer_state.json`.

## 25 novembre 2026 — Lot de test indépendant

- Codex a rédigé les 20 cas anglais de `data/human_test.jsonl` sans reprendre les gabarits du pilote. Les quatre combinaisons famille × nombre de contraintes comptent cinq cas chacune. Huit cas mêlent plafonds et minimums, et cinq ont un optimum sur un axe.
- Les références correspondent à la seconde transcription des énoncés. Les 20 passent le vérificateur et un calcul exact aux sommets confirme les résultats de HiGHS. Le contrôle des doublons couvre le lot et les deux pilotes archivés. L'empreinte est consignée dans le README. La relecture par Marc et la comparaison avec le futur corpus restent à faire.
- Marc a retiré « linear » dans trois énoncés de mélange pour voir si le modèle formule correctement le problème sans ce mot dans la consigne. Le contrôle par l'empreinte initiale confirme que les 20 références sont identiques. L'empreinte du lot modifié figure dans le README.

## 21 novembre 2026 — Relecture du PDF par Marc

- Marc a confirmé avoir vérifié les dix problèmes du dossier de validation du pilote v2. Aucune correction supplémentaire signalée. La relecture est consignée dans `reviews/validation_pilote_v2/rapport.md`.

## 20 novembre 2026 — Dossier de validation du pilote v2

- Le vérificateur réutilise le parseur, le schéma et le solveur. Il compare le JSON du pilote à une transcription indépendante des énoncés et contrôle la faisabilité et l'optimalité sur cette référence. Les dix cas passent les quatre contrôles. Une modification volontaire d'un second membre apparaît dans le rapport et bloque la production d'une nouvelle source LaTeX.
- Le rapport dans `reviews/validation_pilote_v2/` réunit les anomalies automatiques et les observations de relecture. Le PDF reprend les dix cas avec l'énoncé, le programme mathématique et son JSON.
- Suite exécutée avec `python -m pytest -q -p no:cacheprovider`. 85 tests réussis et 1 échec attendu.

## 18 novembre 2026 — Validation du pilote v2 par Marc

- Marc a comparé automatiquement les dix énoncés à leurs références JSON, coefficients, seconds membres, sens des contraintes et objectif. Il a résolu de nouveau chaque LP et retrouvé les solutions, objectifs, écarts et contraintes actives consignés. Six cas ont les deux contraintes actives, contre un en v1. Les dix cas sont marqués `reviewed`. Le registre `reviews/pilot_v2.json` attache la validation aux énoncés et références relus. La qualification des templates pour le corpus reste à faire.
- L'écart de travail de `pilot_production_003` valait environ `-2,84e-14`. Le contrôle de faisabilité utilise toujours l'écart calculé et sa tolérance. Le diagnostic ramène ensuite à zéro les valeurs à huit unités d'arrondi près. Le sommet est retrouvé en arithmétique rationnelle. Son objectif exact est `12432/11` et ses deux écarts exacts valent zéro. Les résultats bruts de HiGHS restent disponibles dans `pilot.json`.
- Les cas libres portent `geometry_matches_target: null`. Le rapport explique les 31 rejets géométriques parmi les graines 42 à 82. Le seul tirage numérique commun aux cas retenus des deux versions est celui de la graine 51. Il correspond à `pilot_mixing_005` dans l'archive v1 et à `pilot_production_001` en v2, avec les sens opposés. Conserver la trace de ce recouvrement et compter ce tirage une fois dans un bilan commun.
- En v2, `pilot_mixing_005` a un écart exact de `1270/3` sur le nutriment P. La contrainte Q impose `x1 + x2 >= 194/3`. Avec les bornes non négatives, elle implique `8*x1 + 9*x2 >= 1552/3 > 94`. La ligne P est donc redondante et reste visible comme cas de diagnostic.

## 18 novembre 2026 — Revue du projet

### Vérifications exécutées

- `python -m pytest -q -p no:cacheprovider` sous Python 3.13.5 et SciPy 1.16.1 : 79 tests réussis, 1 échec attendu. Les notebooks GPU ont été relus sans nouvelle exécution.
- Diagnostic numérique : pour chaque combinaison famille × nombre de contraintes, tirer une instance pour chacune des graines 10 000 à 10 249 avec `sample_reference` et `configs/generate_v1.json`, puis résoudre et appliquer `check_admission`. Les 1 000 instances ont été admises. Une solution est classée sur un axe si au moins une composante est inférieure ou égale à `1e-6`.

| Famille | Contraintes | Sur un axe | Deux variables positives |
| --- | ---: | ---: | ---: |
| Production | 2 | 220 | 30 |
| Production | 3 | 201 | 49 |
| Mélange | 2 | 219 | 31 |
| Mélange | 3 | 185 | 65 |
| Total | | **825** | **175** |

- Deux défauts reproduits dans la chaîne de validation. Un champ objectif avec `"sense": "min", "sense": "max"` passe et la seconde valeur est retenue. Un coefficient objectif entier égal à `10**320` passe le schéma, puis la conversion pour le solveur lève `OverflowError`.
- Les deux témoins demandent de déterminer des quantités. La consigne de formulation sera rendue explicite avant leur qualification. Le générateur associe systématiquement chaque famille au même sens d'objectif et d'inégalité. Cette association motive des cas humains où les contraintes ont des sens différents dans un même énoncé.

### Suite retenue

- Éprouver le vérificateur sur des cas de développement avant d'élargir le corpus. Distinguer conformité du JSON, exactitude de la formulation, résolution du problème prédit et succès sur la référence. Utiliser des erreurs connues, des formulations équivalentes et des optima multiples. Corriger les deux défauts de validation reproduits.
- Viser une première expérience de 300 exemples d'entraînement, 60 de validation, 80 de test synthétique et 20 cas humains indépendants. Conserver des lignées disjointes et une couverture des deux géométries observées. Ces volumes sont des cibles de planification. Les configurations et fichiers du corpus restent à préparer.
- Réutiliser le smoke test PyTorch. Vérifier le masque avec du padding et des longueurs différentes, sauvegarder puis recharger l'adaptateur. Produire une comparaison appariée sous un protocole figé et examiner les gains et les régressions par exemple.

## 18 novembre 2026 — Simplification du contrat des templates

### Phase 2 — Pilote numérique implémenté et exécuté

#### Révision v2 après retour sur la diversité

- Marc observe que neuf des dix solutions initiales sont sur un axe, avec une seule contrainte active, ce qui masque certaines erreurs dans un contrôle fondé sur l'optimum.
- Profil spécifique `configs/pilot_v2.json` : cinq exemples par famille, dont les trois premiers exigent deux variables > `1e-6` et deux contraintes actives selon la tolérance existante. Les deux suivants n'ont pas de filtre géométrique supplémentaire. Les règles générales et quotas du corpus dans `configs/generate_v1.json` restent inchangés.
- La génération conserve références, graines, profil visé, diagnostic numérique et motif `target_geometry_not_met` pour les rejets géométriques. Le plafond de 100 tentatives s'applique séparément à chaque exemple demandé, y compris les cas ciblés. Aucun nombre n'est réparé.
- **Exécution v2 :** dix exemples sélectionnés sur 41 tentatives, graines tentées 42 à 82 ; 31 rejets géométriques, zéro rejet numérique ; taux de sélection 24,39 %, admission numérique 100 %. Six cas ciblés vérifiés : production aux graines 51, 52, 68 ; mélange aux graines 74, 76, 80. Les quatre cas libres sont sur des axes pour ce tirage.
- Les artefacts v1 restent conservés dans `runs/generation_pilot_v1/`. La commande par défaut écrit désormais `runs/generation_pilot_v2/pilot.json` et `review.md`. La relecture ultérieure de la v2 est consignée ci-dessus. Les identifiants locaux du pilote doivent être interprétés avec leur version.
- **Tests exécutés :** `python -m pytest -q -p no:cacheprovider` : 79 passés, 1 xfailed. Quotas par famille, géométrie sur les références, reproductibilité et progression des graines vérifiés. Un test force l'épuisement du budget géométrique et confirme que les solutions sur un axe restent autorisées pour les cas libres. Un autre montre qu'un second membre incorrect sur une contrainte lâche peut laisser solution et objectif inchangés. Le comparateur de formulation reste à implémenter.

#### Première exécution v1 (conservée)

- Étape 1 commitée sous `634450a` avant les changements de phase 2.
- `src/lp_llm/generate.py` : quatre fonctions principales, échantillonnage, admission, rendu et assemblage du pilote, avec une CLI. Générateur `random.Random(seed)` local par tentative ; ordre production puis mélange ; graine incrémentée après chaque tentative. JSON explicitement sérialisé pour le solveur existant.
- Admission : statut optimal, solution et objectif finis, hors origine, non-négativité et faisabilité selon les tolérances, au moins une contrainte active. Ni unicité de l'optimum ni activité de toutes les contraintes exigées. Chaque rejet conserve sa raison, sa graine et sa référence. Au plafond, arrêt explicite et sauvegarde des tentatives dans `failure.json` via la CLI.
- **Exécuté :** `$env:PYTHONPATH = 'src'` puis `python -m lp_llm.generate`. Cinq exemples par famille, dix tentatives, graines 42 à 51, taux d'admission numérique 100 %, aucun rejet observé. Le test du plafond force des rejets séparément. Les artefacts `runs/generation_pilot_v1/pilot.json` et `review.md` restent hors Git, régénérables par cette commande.
- Neuf exemples ont une seule contrainte active et un en a deux (graine 51). Ce constat ne prouve pas la redondance ; aucun filtre de redondance n'a été ajouté. Le taux d'admission de dix cas n'est pas une preuve de diversité du futur corpus.
- **Tests exécutés :** `python -m pytest -q -p no:cacheprovider` : 77 passés, 1 xfailed (test volontairement faux du solveur). Reproductibilité du pilote et absence de modification du générateur global vérifiées ; cas d'optima multiples, contrainte inactive, résultats non finis, origine, violation d'une exigence >=, absence de contrainte active, champ manquant et plafond de trois tentatives couverts.
- La v1 a servi au diagnostic de diversité. Les dix cas soumis ensuite à la validation de Marc sont ceux de la v2.

### Complément — Étape 1 terminée pour la définition du contrat

- Ajout du candidat `mixing_by_requirement_001` : achats continus de deux suppléments, coût minimal et deux exigences `>=` sur des apports de nutriments. Aucun total imposé ni proportion. Texte et unités fixes.
- Vérification exécutée des deux candidats : JSON lisible, champs requis présents sans champ inconnu, ordre des variables et correspondance des lignes, sens par famille, rendu sans champ restant. Les valeurs sont distinctes pour les huit rôles numériques de chaque exemple.
- Les références passent le schéma et `solve_lp_problem` : production `[44, 12]`, profit 2144 ; mélange `[110/13, 60/13]`, coût 110. Résultats contrôlés indépendamment par les sommets et consignés avec textes et références dans `reports/contract_examples_v1.md`.
- Pendant la préparation du diagnostic production, une première attente de maximum à l'intersection était erronée : l'assertion l'a détectée. Le diagnostic final utilise des profits 37 et 43, avec les quatre sommets explicitement comparés. Aucun filtre ni solveur n'a été modifié.
- L'étape 1 dispose de ses livrables. L'étape 2 (échantillonneur et dix exemples), les templates à trois contraintes et la qualification humaine restent à faire. Les deux candidats restent `needs_review`, `templates/accepted.json` reste vide.

### Changement d'organisation initial

**Statut : organisation des fichiers modifiée ; génération et qualification non implémentées.**

- Chaque template possède un texte anglais complet, un contexte, des produits, des ressources, des unités et un nombre de contraintes fixes. Seuls les coefficients et seconds membres sont remplacés.
- Suppression du catalogue de scénarios et du tirage de ressources : éviter les associations incohérentes et les accords grammaticaux liés aux substitutions textuelles.
- `configs/template_contract_v1.json` contient les champs numériques autorisés, les règles de présence et le format commun des candidats. `configs/generate_v1.json` reste inchangé.
- L'exemple production est déplacé de `configs/candidate_example_production.json` vers `templates/candidates.json`, avec métadonnées fixes de variables, d'unités et de correspondance. Sa lignée est conservée et son statut est `needs_review`. Les unités abrégées évitent les variations singulier/pluriel.
- `templates/accepted.json` est vide : aucune admission humaine n'est présumée. Le témoin mélange/achat, les templates à trois contraintes et le pilote restent à faire.
- **Vérification ponctuelle exécutée :** lecture JSON des deux configurations et des deux bibliothèques ; présence exacte des champs numériques requis pour le candidat à deux contraintes ; cohérence des indices, de l'ordre des variables et des sens ; rendu avec huit valeurs distinctes sans champ restant. Contrôles réussis. Ce contrôle structurel ne remplace pas la qualification sémantique ni le pilote numérique.

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

- Le chargement du modèle est exécuté (2A). La génération courte est exécutée une fois (2A) : sortie `invalid`.
- La révision du modèle et du tokenizer est figée dans le code (2A) : `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`.

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

## Étape 1C — Compilation JSON → `linprog` (`src/lp_llm/solver.py`)

**Statut : implémenté et exécuté** (`tests/test_solver.py` : 6 tests passés + 1 xfail ; suite complète 68 passés, 1 xfailed).

**Rôle.** `solve_lp_problem(json_string)` valide le JSON (`get_valid_json` puis `respect_problem_perimeter`), le traduit pour `scipy.optimize.linprog` (méthode `highs`) et renvoie un dict `{status, message, solution, objective_value}`. Aucune exécution de code issu du modèle.

### Décisions

- **Traductions** : `max` → minimiser `−c` puis remettre le signe sur la valeur de l'objectif ; `a·x ≥ b` → `−a·x ≤ −b` dans `A_ub` ; `=` → `A_eq` ; bornes `[a, null]` → `(a, None)`.
- **Statuts** : `"optimal"` (code 0), `"infeasible"` (2), `"unbounded"` (3), `"unsolved"` (1 = limite d'itérations, 4 = difficultés numériques, tout autre code). `"invalid"` est réservé aux entrées rejetées par le schéma. Raison : une sortie mal formée est une faute du modèle, un échec de HiGHS n'en est pas une ; les confondre fausserait les métriques.
- **Le solveur re-valide l'entrée** au lieu de lui faire confiance : une entrée invalide renvoie `status: "invalid"` avec le message du validateur, sans exception.
- **`get_valid_json` renvoie `tuple[bool, Any]`** : `json.loads` peut renvoyer dict, liste, nombre, chaîne ou `None`. Le message d'échec est une chaîne, comme les autres rejets.
- **Tests** : valeurs attendues calculées à la main (commentaire dans chaque test), pas recopiées du solveur. Données choisies pour que l'optimum soit unique et que l'erreur visée change le résultat. Cas : exemple atelier (`[40, 20]`, 2000), `>=` actif (`[4, 6]`, 16), minimisation (`[9, 1]`, 21), borne inférieure `[1, null]` (`[1, 0]`, 2), borne supérieure `[0, 1]` (`[4, 1]`, 11), problème infaisable. Un test `xfail(strict=True)` à valeur attendue fausse vérifie que pytest détecte un écart.

### Erreurs volontaires (tests de mutation, exécutés à la main puis annulés)

- **`>=` sans le signe du `rhs`** (`b_ub.append(rhs)`) : 3 tests échouent (`>=`, minimisation, infaisable). La contrainte devient `a·x ≥ −b`, donc inactive.
- **`max` sans négation de `c`** : 3 tests échouent (exemple atelier, `>=`, borne supérieure). Le solveur minimise et renvoie l'origine.
- Les tests qui passent malgré la mutation sont ceux qui n'utilisent pas la partie modifiée (pas de `>=`, ou minimisation). Ces mutations ne sont pas conservées dans la suite de tests.


### Points ouverts

- Pas encore de test conservé pour : problème non borné, contrainte `=` (optima multiples : comparer la valeur de l'objectif, pas le vecteur), entrées invalides passées au solveur. Vérifiés une fois à la main.
- L'évaluation devra calculer l'**objectif de référence** sur la solution prédite (tolérances `1e-6*(1+|rhs|)` et `1e-5*(1+|f_opt|)`) : pas encore implémenté.

## Étape 2A — Smoke test du modèle (`smoke_test.ipynb`)

**Statut : chargement et génération courte exécutés, une fois chacun, kernel redémarré avant la mesure. La sortie du modèle est `invalid`. Le solveur a été testé séparément sur un JSON corrigé à la main : c'est un test du solveur, pas une sortie du modèle.**

### Mesures (exécutées)

Chargement propre (kernel redémarré, révision figée) :
- Avant chargement : VRAM allouée par torch 0,00 Go, réservée 0,00 Go, libre 6,94 Go sur 8.
- Après chargement : allouée 2,88 Go, réservée 2,93 Go, libre 4,01 Go.
- Devices des paramètres : `{device(type='cuda', index=0)}` (aucun paramètre sur CPU). `model.hf_device_map` est absent (`getattr` renvoie `None`) : la répartition est vérifiée par les devices des paramètres.
- Temps de chargement : 7,02 s et 7,44 s pour deux chargements propres ; 24,41 s pour un chargement ultérieur, avec le même cache. Variabilité du disque ou du cache, pas du modèle.
- Paramètres : 1 543 714 304 (≈ 1,54 B), 28 couches, `hidden_size` 1536, contexte max 32 768. Vocabulaire `len(tokenizer)` = 151 665 ; EOS `<|im_end|>` (151645) ; PAD `<|endoftext|>` (151643).

Génération (prompt v2) :
- Prompt : système avec un exemple JSON, règles 1 à 13, interdiction des fences et des `//`, consigne « Answer only with the valid JSON ». Utilisateur : énoncé de la boulangerie avec les chiffres (farine 20 kg/jour, 8 h/jour, 500 g et 200 g de farine, 30 et 10 min, profit 12 € et 4 €). Ce prompt est celui mesuré ; les versions précédentes ne sont pas conservées.
- Template : avec `tokenize=False`, le texte rendu contient `<|im_start|>`, les deux messages et `<|im_start|>assistant` en fin de chaîne.
- Décodage glouton, `max_new_tokens=256` : 122 nouveaux tokens, dernier token `<|im_end|>` (151645), fin par EOS, donc pas de troncature.
- Sortie brute (non nettoyée) : bloc ` ```json `, `variables` correct, objectif `max` `[12, 4]` correct, contrainte de farine `[500, 200] ≤ 20` (grammes avec des kilogrammes : erreur de formulation), contrainte de temps `[30, 10] ≤ 8 * 60` (expression, pas un nombre), commentaire `//`.
- `solve_lp_problem(sortie brute)` : `{'status': 'invalid', 'message': 'Invalid JSON: Expecting value: line 1 column 1 (char 0)'}`. Le JSON est rejeté au premier caractère, à cause de la fence.

Solveur sur un JSON corrigé à la main (test du solveur) :
- Coefficients ramenés à des kilogrammes et des minutes : `[0.5, 0.2] ≤ 20`, `[30, 10] ≤ 480`.
- Résultat : `optimal`, objectif `192.0`, solution `[16.0, 0.0]`.
- Calcul à la main : l'objectif vaut 0,4 × (30·x1 + 10·x2), la contrainte de farine n'est jamais active, et la valeur 192 est atteinte sur tout le segment entre (16, 0) et (0, 48). Le solveur renvoie un point parmi ces optima : pour l'évaluation, on compare la valeur de l'objectif, pas le vecteur.

### Décisions

- **Cache Hugging Face dans le dépôt** : `HF_HOME = <dépôt>/.hf_cache` (2,9 Go), défini avant l'import de `transformers`. `.hf_cache/` est ignoré par Git.
- **Révision figée** : `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, passée à `from_pretrained` pour le tokenizer et pour le modèle.
- **Import du solveur** : `sys.path.insert(0, <dépôt>/src)`, puis `from lp_llm.solver import solve_lp_problem`.
- **Prompt v2 figé** pour le baseline. La sortie n'est pas réparée : elle compte comme `invalid`.
- **Pas de décodage contraint à ce stade** : il garantirait le format et masquerait exactement ce que la métrique de validité structurelle doit mesurer.

### Remarques

- **L'écart nvidia-smi / torch de 1A est expliqué.** Avant tout chargement, 8 − 6,94 = 1,06 Go sont déjà occupés (contexte CUDA et autres processus). Après chargement, torch réserve 2,93 Go, et il reste 4,01 Go libres : 1,06 + 2,93 ≈ 4,0 Go de moins que 8 Go. Pas de surcoût float32 : 2,88 Go = 1,54·10⁹ × 2 octets.
- **Marge pour l'entraînement : 4,01 Go libres.** Les activations et l'état de l'optimiseur LoRA devront tenir là-dedans : à mesurer au smoke test d'entraînement.
- **Une mesure faite sur un kernel qui contient déjà le modèle est fausse.** Un second chargement par-dessus donne VRAM libre 0,68 Go et réservée 5,81 Go. Toujours redémarrer le kernel avant une mesure de chargement.
- **Piège f-string** : `f"{{p.device for p in ...}}"` affiche le texte littéral au lieu du résultat. Il faut `{set(p.device for p in model.parameters())}`.
- `pad_token` ≠ `eos_token` : masquer le padding ne masquera pas la fin de réponse. À vérifier lors de l'inspection des masques.
- `len(tokenizer)` (151 665) peut être inférieur à `config.vocab_size` (matrice d'embeddings arrondie) : normal, ne pas redimensionner.

### Points ouverts

- Smoke test d'entraînement : fonctionnel mais déborde de la VRAM (voir 2B).
- Génération : une seule exécution, sur un seul énoncé. Aucune statistique.
- Le baseline doit être répété sur le jeu de validation avant toute conclusion.
- Comparaison de formulations et objectif de référence : pas encore implémentés (voir 1C).

## Étape 2B — Smoke test d'entraînement LoRA (`train_smoke_test.ipynb`)

**Statut : exécuté (kernel redémarré, graine fixée). La boucle, le masque et les gradients fonctionnent. Sans checkpointing de gradient, la mémoire déborde de la VRAM (≈ 1,5 Go en mémoire GPU partagée) ; avec, le pic tombe à 4,62 Go.** Un seul exemple, répété 5 pas : c'est un test de plomberie, pas un résultat d'entraînement.

### Tokenisation et masque (exécuté)

- **Paire d'entraînement** : prompt v2 (même `system` et même `user` que 2A) + cible `json.dumps(json.loads(lp_json))`, soit le JSON corrigé à la main de 2A sur une seule ligne. La cible est un exemple de test de la plomberie, pas une donnée du corpus ; elle passe `solve_lp_problem` (`optimal`, assertion dans la cellule).
- **Méthode** : `apply_chat_template(messages, tokenize=False, add_generation_prompt=True)` pour le prompt, `apply_chat_template(messages + [assistant: cible], tokenize=False)` pour la conversation complète, puis `tokenizer(..., add_special_tokens=False)` sur les deux (les balises spéciales sont déjà dans le texte).
- **Contrôles (assertions)** : le texte complet commence par le texte du prompt ; les ids du prompt sont un préfixe exact des ids complets (la frontière ne coupe pas de token) ; `len(labels) == len(full_ids)`.
- **Labels** : `-100` sur les 705 tokens du prompt ; partie entraînable de 100 tokens = la cible + `<|im_end|>`. Total : 805 tokens.
- **Vérification par décodage** des seuls tokens entraînables : exactement la cible suivie de `<|im_end|>`, rien du prompt.

### LoRA et boucle (exécuté)

- `peft==0.21.2` : `LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], bias="none", task_type="CAUSAL_LM")`, puis `get_peft_model`.
- Noms des modules vérifiés sur le modèle : `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`.
- **Paramètres entraînables : 4 358 144 (0,28 %)**, vérifié à la main : par couche, `q_proj` et `o_proj` 16 × (1536 + 1536) = 49 152 chacun, `k_proj` et `v_proj` 16 × (1536 + 256) = 28 672 chacun (sortie 256 : attention à têtes K/V groupées), soit 155 648 × 28 couches.
- Boucle à la main, sans `trl` : `peft_model.train()`, `AdamW` sur les paramètres `requires_grad`, lr 1e-4, batch 1, 5 pas, `torch.manual_seed(42)` avant la boucle.
- **Pertes** (calculées avant la mise à jour de chaque pas) : 0,1837 → 0,1565 → 0,1096 → 0,0684 → 0,0382. La baisse sur un exemple répété montre que les gradients atteignent les adaptateurs ; c'est de la mémorisation, pas une mesure de qualité.
- **VRAM pic** (`max_memory_allocated`) : **7,83 Go**, alors que 6,94 Go seulement sont libres avant chargement. Le Gestionnaire des tâches montre ≈ 1,5 Go de mémoire GPU partagée pendant la boucle : le pilote Windows déborde en RAM système au lieu d'échouer.

### Checkpointing de gradient (exécuté, même kernel)

- Protocole : après le run standard, adaptateurs LoRA remis à leur état initial (`state_dict` sauvegardé avant le premier run), nouvel optimiseur, `gc.collect()` + `torch.cuda.empty_cache()` + `reset_peak_memory_stats()`, même graine, puis `peft_model.gradient_checkpointing_enable()` (valeurs par défaut).
- **Pertes identiques** aux deux runs (0,1837 → 0,1541 → 0,1090 → 0,0672 → 0,0365) : la remise à zéro fonctionne, le checkpointing ne change pas le calcul et les gradients atteignent bien les adaptateurs.
- **VRAM pic : 7,84 Go → 4,62 Go**, sous les 6,94 Go libres.
- **Temps moyen par pas sur cinq pas : 9,95 s → 3,11 s.** La boucle retourne `sum(times) / len(times)` avec synchronisation CUDA, malgré le libellé « tps 5 boucles » dans le notebook. L'ordre des essais laisse un effet d'échauffement possible. La baisse du temps est compatible avec une réduction du débordement en RAM système. Le protocole ne permet pas d'isoler la contribution de ces deux effets.
- L'avertissement `use_cache=True is incompatible with gradient checkpointing. Setting use_cache=False` confirme que le checkpointing est actif ; sans conséquence.

### Décisions

- **`<|im_end|>` est entraînable** : c'est lui qui apprend au modèle à s'arrêter.
- **Le `\n` final du template est retiré** de l'entrée et des labels : la séquence s'arrête sur `<|im_end|>`. L'entrée diffère donc du texte rendu par le template de ce seul caractère ; sans effet à l'inférence, qui s'arrête sur `<|im_end|>`.
- **LoRA sur l'attention seulement** (q, k, v, o) pour le smoke test ; le MLP n'est pas adapté.
- **Boucle écrite à la main** pour voir chaque étape ; `trl` plus tard.
- **Checkpointing de gradient activé pour l'entraînement** : il fait tenir l'entraînement en VRAM sur la RTX 4060, ce qui évite le débordement en RAM ; QLoRA n'est pas nécessaire à ce stade.


### Remarques

- **Checkpointing de gradient (API vérifiée dans le code installé, transformers 5.22.1)** : `gradient_checkpointing_enable(gradient_checkpointing_kwargs=None, every_n_layers=1, offload=False)`. Par défaut `use_reentrant=False` (passé à `torch.utils.checkpoint.checkpoint`), et `enable_input_require_grads()` est appelé automatiquement pour un modèle à `input_ids`. `use_cache` est un argument du `forward` (`Qwen2Model`, `Qwen2ForCausalLM`), forcé à `False` avec un avertissement quand le checkpointing est actif. `PeftModel` transmet l'appel au modèle de base (`__getattr__`). Le checkpointing réduit les activations, pas les poids, l'optimiseur ni les logits.

### Points ouverts

- Mesuré pour batch 1 et 805 tokens. Le batch effectif ≈ 16 prévu (accumulation de gradient ou vrai batch) reste à vérifier en mémoire.
- Le smoke test utilise un seul exemple ; le corpus (`generate.py`) et les splits restent à faire.
