# Plan de génération du corpus

**Statut au 25 novembre 2026.** Les dix cas du pilote v2 et les seize gabarits du corpus v1 ont été validés par Marc. Les 440 cas synthétiques définitifs et leur manifeste sont dans `data/`. Les vingt cas indépendants ont été contrôlés pour l'absence de recouvrement avec le corpus. La mesure avant LoRA est exécutée sur le test indépendant.

**Mise à jour : 17 novembre 2026.** Marc autorise la rédaction de templates candidats par un LLM, puis leur filtrage et leur validation. Cette décision complète le cadrage initial, qui ne nécessitait pas de LLM externe. Le LLM produit des données textuelles, pas du code à exécuter.

## Priorité après la revue du 18 novembre 2026

Le premier livrable expérimental est une comparaison du modèle initial et du même modèle adapté par LoRA sur des énoncés tenus à l'écart de l'entraînement. Construire le vérificateur sur quelques exemples de développement avant d'élargir la bibliothèque. Réutiliser les deux témoins relus par Marc.

- Pour chaque réponse brute, enregistrer quatre résultats avec tous les exemples au dénominateur : validité du JSON et du schéma, exactitude de la formulation après normalisation documentée, succès du solveur sur le problème prédit, succès de la solution prédite sur le problème de référence. Pour ce dernier, vérifier la faisabilité et calculer l'objectif **de référence** au point prédit. Compter les sorties invalides ou tronquées comme des échecs, sans réparation.
- Éprouver le vérificateur avec un second membre erroné qui laisse l'optimum intact, des lignes réordonnées ou mises à l'échelle, et deux solutions distinctes d'un même problème à optima multiples. Rejeter les clés JSON dupliquées et vérifier qu'un entier impossible à convertir pour le solveur produit un diagnostic sans interrompre le lot.
- Valider le masque de loss sur un lot de longueurs différentes, puis sauvegarder et recharger l'adaptateur dans une session propre. Sélectionner le checkpoint et régler le prompt sur la validation. Figer ensuite le prompt, le décodage et le vérificateur. Comparer les deux modèles sur les mêmes cas et conserver les réponses brutes, les gains et les régressions par exemple.

## Principe et périmètre

D'abord les nombres, ensuite le texte : construire une formulation numérique, la valider avec le schéma et le solveur, puis rendre un template accepté. Le solveur contrôle la référence numérique ; il ne garantit pas que l'énoncé exprime cette référence.

Le LLM aide à produire une bibliothèque de templates à trous. Une fois celle-ci validée et gelée, la génération du corpus est déterministe, sans appel LLM par exemple. Marc valide quelques rendus de chaque template, puis audite un échantillon du corpus final.

Chaque template possède un contexte, des produits, des ressources, des unités et un nombre de contraintes fixes. Seuls les nombres sont remplacés au rendu. `configs/generate_v1.json` décrit le tirage numérique et `configs/template_contract_v1.json` décrit les règles communes. Les deux témoins sont dans `templates/candidates.json`. Les propositions et leurs affectations sont dans `templates/corpus_v1_candidates.json`. La bibliothèque relue figure dans `templates/accepted.json`.

- Énoncés en anglais ; deux variables continues non négatives `x1`, `x2`, explicitement ordonnées.
- Deux ou trois contraintes ; pas d'égalité en v1 ; bornes `[[0, null], [0, null]]`.
- **Production** : maximiser un profit, contraintes de ressources `<=`.
- **Mélange/achat** : minimiser un coût, exigences `>=`. Éviter les proportions, pourcentages et volumes totaux imposés qui ajouteraient des relations hors de ce contrat.
- Petits entiers positifs, unités cohérentes sans conversion.
- Le profil `configs/corpus_v1.json` fixe 300 exemples d'entraînement, 60 de validation et 80 de test synthétique, répartis à parts égales entre les quatre combinaisons famille × nombre de contraintes. Les 20 cas indépendants restent dans leur propre lot.

## Étape 1 — Fixer le contrat de génération

**Statut : terminée pour la définition du contrat.** Vérification des champs, correspondances et rendus exécutée sur un exemple par famille ; les deux références ont le statut `optimal`, confirmé par calcul des sommets. Preuves dans `reports/contract_examples_v1.md`. Cela ne vaut pas admission humaine des templates à l'étape 4.

**Contrat défini**

1. Définir une configuration versionnée : plages numériques, graine principale, volumes, répartition par famille, règle de tirage de deux ou trois contraintes, tolérances et plafond de tentatives.
2. Partir des plages suivantes : coefficients de contraintes 1–9, profits/coûts 1–50, seconds membres 20–200. Ces choix initiaux ne garantissent pas à eux seuls la diversité.
3. Définir les champs numériques à trous autorisés, par exemple `{objective_x1}`, `{objective_x2}`, `{constraint_1_x1}`, `{constraint_1_x2}`, `{rhs_1}`, puis les champs des autres contraintes. Les produits, ressources et unités sont écrits directement dans chaque template et décrits dans ses métadonnées. Aucun champ textuel variable en v1.
4. Fixer pour chaque template le nombre de contraintes et la correspondance entre leurs champs, leur ordre dans le texte et les lignes de référence. Une présentation par produit est autorisée si cette correspondance reste explicite.
5. Rendre obligatoires : définition des variables, continuité, non-négativité, objectif, tous les coefficients et toutes les limites. Demander explicitement de formuler le programme linéaire. Corriger les deux témoins qui demandent actuellement de déterminer les quantités, puis relire les nouveaux rendus. Interdire les conditions mathématiques supplémentaires et implicites.
6. Fixer le format des candidats : `template_id`, `lineage_id`, famille, nombre de contraintes, texte à trous numériques, définition et unités des variables, objectif, unités et correspondance des contraintes, ordre de première apparition dans le texte et statut de qualification. Ces métadonnées restent hors de l'énoncé rendu. Chaque candidat est autonome, sans référence à un catalogue de scénarios.

**Livrable :** configuration et contrat documentés, avec un exemple complet par famille.

**Critère de passage :** chaque élément de la formulation correspond à un champ et à une phrase ; aucun choix mathématique n'est confié au LLM lors du rendu.

## Étape 2 — Construire le pilote numérique et deux templates témoins

**Statut : étape terminée, dix exemples v2 relus.** Marc a confirmé la correspondance entre les dix textes et leurs références, puis recalculé les solutions, objectifs, écarts et contraintes actives. Six exemples ont deux contraintes actives, contre un en v1. Les graines 42 à 82 donnent 41 tentatives, dont 31 rejets géométriques et zéro rejet numérique. Le registre `reviews/pilot_v2.json` conserve les empreintes des dix cas relus. Les résultats et diagnostics se trouvent dans `runs/generation_pilot_v2/`. Les tests couvrent aussi les rejets et le plafond de tentatives. Commandes dans `README.md`.

**Travail réalisé**

1. Écrire un échantillonneur simple par famille, avec un `random.Random(seed)` local par instance et une graine enregistrée. Ne pas utiliser le générateur aléatoire global.
2. Construire la référence dans le schéma existant. L'interface actuelle `solve_lp_problem` attend une chaîne JSON : sérialiser explicitement la référence.
3. Exiger le statut `optimal`, une solution et un objectif finis, une solution différente de l'origine et au moins une contrainte active selon les tolérances fixées. Chaque contrainte doit porter sur les variables. Ne pas imposer un optimum unique ni l'activité de toutes les contraintes.
4. Rejeter une instance non admise, enregistrer la raison et passer à la graine suivante. Ne pas réparer silencieusement ses nombres. Arrêter avec un diagnostic au plafond de tentatives.
5. Préparer un template témoin simple par famille, avec un nombre de contraintes fixé. Générer cinq exemples par famille : trois cas ciblés avec deux variables > `1e-6` et deux contraintes actives, puis deux tirages sans filtre géométrique supplémentaire. Cette composition diagnostique ne fixe pas la distribution du corpus final. Marc compare texte, matrice, second membre, objectif et bornes.
6. Conserver graines, références, diagnostics et corrections. Mesurer le taux d'admission. Signaler la redondance éventuelle de contraintes comme propriété du corpus, sans ajouter un filtre complexe en v1.

**Livrable :** pilote reproductible et dix exemples relus. Ces exemples de développement ne deviennent pas des exemples de test.

**Critère de passage :** références admises et correspondance texte/formulation validée pour les deux témoins, avant d'élargir la bibliothèque.

## Étape 3 — Faire produire les templates candidats par un LLM

**À faire**

1. Préparer un prompt versionné : contrat, champs autorisés, deux familles et exemples de développement. Ne pas fournir les cas du test humain.
2. Demander des objets structurés contenant uniquement les données du template. Interdire les nombres mathématiques écrits en dur, les champs inventés, les conversions d'unités et les contraintes supplémentaires.
3. Demander de la diversité : présentation par produit ou ressource, ordre des informations, phrases courtes ou regroupées, vocabulaire et contextes plausibles. Changer seulement les noms de produits ne crée pas une nouvelle structure linguistique.
4. Produire les candidats par petits lots et compléter les structures manquantes après la première qualification. Pour chaque combinaison famille × nombre de contraintes, viser deux lignées indépendantes pour le train, une pour la validation et une pour le test.
5. Conserver requêtes et réponses brutes, modèle et version disponibles, date, paramètres et relations parent/enfant. Une paraphrase ou une correction garde la même `lineage_id`. Regrouper aussi les candidats quasi identiques sans parent déclaré.
6. La génération peut se faire en conversation ou via un accès déjà autorisé. Aucun service particulier n'est requis. Un appel payant exige une instruction explicite.

**Livrable :** candidats et provenance, séparés de la bibliothèque acceptée. Garder aussi les rejets et leurs motifs.

**Critère de passage :** format exploitable, provenance connue et matière suffisante pour commencer la qualification. Le nombre de candidats ne vaut pas acceptation.

## Étape 4 — Qualifier chaque template avant admission

**Contrôles déterministes à réaliser**

1. Vérifier format, famille, nombre de contraintes, champs requis et absence de champs inconnus. Définir les occurrences attendues : un champ peut se répéter si le contrat le prévoit.
2. Rendre des instances de diagnostic avec des valeurs distinctes pour tous les rôles numériques, au besoin hors des plages du corpus. Les échanges de coefficients deviennent ainsi visibles ; ces diagnostics ne sont pas des exemples d'entraînement.
3. Modifier un champ numérique à la fois : seules ses occurrences prévues doivent changer. Contrôler séparément les templates à deux et trois contraintes ; chaque template possède un nombre fixe de contraintes, sans branche conditionnelle de texte.
4. Détecter champs non remplacés, nombres mathématiques non prévus et métadonnées dans le texte. Autoriser les mentions nécessaires de `x1` et `x2`.
5. Vérifier les unités par rapport au contrat déclaré. Ce contrôle structurel ne prouve pas la cohérence sémantique des phrases.

**Contrôle sémantique à réaliser**

6. Pour le corpus v1, Marc relit le rendu à valeurs distinctes de chacun des seize gabarits. Le contrôle automatique couvre les 152 substitutions et l'audit indépendant vérifie la présence des valeurs dans les 440 rendus. La lecture vérifie les inégalités, l'association de chaque nombre, les unités et l'objectif.
7. En complément, un LLM vérificateur peut reconstruire la formulation depuis le seul énoncé et le schéma, sans voir la référence. Comparer ensuite à la référence en tolérant l'ordre des contraintes ; archiver les désaccords. Ne pas accepter automatiquement un template sur le seul accord du LLM.
8. Ce filtre LLM est facultatif en v1 : sans accès disponible, conserver la relecture humaine. Il peut partager les erreurs du générateur, même avec un autre prompt ou modèle.
9. Attribuer un statut `accepted`, `rejected` ou `needs_review`. Seul `accepted`, après contrôle humain consigné, est utilisable. Une correction crée une nouvelle version et repasse les contrôles.

**Éprouver les contrôles**

10. Injecter des défauts connus : champ manquant, coefficient échangé, objectif inversé, « at least » remplacé par « at most », contrainte omise et unité incompatible.
11. Associer chaque défaut au contrôle censé le détecter. Les mutations sémantiques peuvent échapper aux tests déterministes : consigner les limites observées du filtre LLM et de la relecture, sans prétendre les éliminer.

**Livrable :** bibliothèque acceptée versionnée et tableau de qualification : contrôles, rendus relus, décision de Marc, motifs de rejet, résultats des mutations.

**Critère de passage :** tous les templates retenus passent les contrôles obligatoires et la relecture ; les défauts structurels injectés font échouer les tests prévus. Les limites sémantiques restent explicites.

## Étape 5 — Affecter les lignées aux splits et geler la bibliothèque

**À faire**

1. Examiner les ressemblances entre candidats : même construction avec synonymes, même ordre des faits, substitutions de contexte. Regrouper les variantes dans une même lignée. Cette revue réduit le risque de fuite sans prouver une indépendance linguistique totale.
2. Affecter les lignées acceptées aux splits **avant de générer le corpus**, avec les cibles par famille et par nombre de contraintes définies à l'étape 3. Toutes les variantes d'une lignée vont dans le même split.
3. Écrire l'affectation dans un registre versionné ; vérifier que chaque `template_id` et chaque `lineage_id` possède un seul split.
4. Équilibrer autant que possible contextes, deux/trois contraintes et présentations. Le vocabulaire des contextes peut rester partagé entre splits ; documenter cette limite.
5. Geler registre, templates et configuration avec leurs SHA-256. Ne plus modifier les templates de test à partir des performances du modèle.

**Livrable :** registre des templates, lignées, versions et splits avec empreintes.

**Critère de passage :** aucune lignée ne traverse les splits ; quotas satisfaits ou réduction explicite du corpus documentée avant génération.

## Étape 6 — Assembler le corpus déterministe

**À faire**

1. Fixer l'ordre de parcours des splits, familles et templates et une règle reproductible d'allocation des graines. Répartir les exemples aussi également que possible entre lignées d'un même split et d'une même famille.
2. Pour chaque exemple : tirage numérique → filtre d'admission → rendu du template gelé → contrôles de rendu → dédoublonnage → enregistrement.
3. Conserver au minimum `{id, family, template_id, lineage_id, seed, statement, reference, split}`. La version de bibliothèque peut figurer dans le manifeste commun. Respecter l'ordre des contraintes annoncé par le template.
4. Dédoublonner sur le texte normalisé et une clé canonique de formulation, dans et entre splits. Pour les entiers v1 : conserver ordre des variables et bornes, normaliser chaque contrainte par son PGCD positif, trier les contraintes et normaliser l'objectif par un facteur positif. Inclure les sens dans la clé. Cela ne prouve pas l'équivalence générale de deux LP, notamment avec contraintes redondantes.
5. En cas de collision, rejeter l'instance et avancer à la graine suivante ; ne pas déplacer un exemple entre splits. Compter collisions et rejets, et respecter le plafond de tentatives.
6. Écrire un JSONL par split et un manifeste : configuration, versions, empreintes de bibliothèque, graines, ordre de génération, nombres demandés/obtenus, répartitions, motifs de rejet, dépendances pertinentes et SHA-256 des fichiers.
7. Fixer sérialisation, encodage UTF-8 et fins de ligne. Les horodatages du manifeste ne doivent pas changer les octets des JSONL.
8. Dans le test synthétique, prévoir dans chacune des quatre combinaisons famille × nombre de contraintes des cas dont la solution de référence est sur un axe et des cas avec deux variables positives. Utiliser le seuil du pilote (`1e-6`) pour distinguer les groupes. Consigner les effectifs, les éventuels filtres et la distribution obtenue. Rapporter les résultats par géométrie et préciser la composition du test dans le score global. Le diagnostic de 1 000 tirages a donné 825 solutions sur un axe. Les effectifs détaillés figurent dans les notes d'apprentissage.

**Livrable :** `data/train.jsonl`, `data/validation.jsonl`, `data/test.jsonl` et manifeste.

**Critère de passage :** volumes atteints, aucune collision conservée et régénération identique des JSONL avec les mêmes entrées et le même environnement.

## Étape 7 — Vérifier les splits et auditer le corpus

**À faire**

1. Ajouter les contrôles de templates dans `tests/test_templates.py` et ceux du corpus dans `tests/test_splits.py`. Garder des fonctions simples.
2. Vérifier disjonction des templates **et des lignées**, identifiants uniques, splits déclarés, quotas, absence de doublons et empreintes.
3. Revalider schéma et statut `optimal` de toutes les références, ainsi que les règles d'admission de l'étape 2.
4. Vérifier que l'énoncé ne contient ni référence JSON, ni identifiant de template, ni graine, ni nom de split. L'assemblage du prompt devra recevoir seulement les champs prévus : refaire ce contrôle à l'étape entraînement.
5. Tester la reproductibilité sur un petit corpus et les défauts injectés : lignée partagée malgré deux `template_id` distincts, doublon numérique avec contraintes réordonnées ou proportionnelles, rendu incomplet et plafond de tentatives atteint.
6. Marc inspecte au moins un exemple de chaque template utilisé, les cas à deux/trois contraintes et quelques valeurs extrêmes. Consigner distributions et défauts observés dans un compte rendu de qualification.
7. Si un défaut est trouvé avant l'entraînement, corriger la bibliothèque, la requalifier et régénérer une nouvelle version complète. Archiver l'ancienne version et la raison ; ne pas retirer silencieusement quelques cas gênants.

**Livrable :** tests exécutés, audit consigné et corpus final gelé. Reporter les exécutions effectives dans `reports/learning_notes.md`.

**Critère de passage :** contrôles obligatoires réussis, mutations ciblées détectées et audit humain consigné. Un simple passage du solveur ne suffit pas.

## Étape 8 — Préparer et isoler le test indépendant

**À faire**

1. Les vingt problèmes en anglais ont été rédigés par Codex à la demande de Marc, indépendamment de la bibliothèque. Le lot compte dix cas par famille, avec deux ou trois contraintes et plusieurs présentations. Huit cas combinent des plafonds et des minimums. Présenter leurs résultats par cas.
2. Construire et relire les références ; vérifier schéma, faisabilité et bornitude avec le solveur, puis l'absence de doublons avec le corpus synthétique.
3. Geler `data/human_test.jsonl`, ses références et son empreinte avant le fine-tuning. Ne pas utiliser ces cas pour les prompts du générateur, les templates, le checkpoint ou les réglages.
4. Réserver ces cas à l'évaluation finale avant/après, avec le même protocole pour les deux modèles. Ne jamais transférer un échec vers l'entraînement. Tracer toute correction ultérieure d'annotation et l'appliquer aux deux évaluations.

**Livrable :** vingt cas indépendants validés et gelés, avec provenance et empreinte.

**Critère de passage :** test indépendant disponible avant l'entraînement, séparé des décisions de développement. Sa rédaction peut avancer pendant les étapes 3–7, sans réutiliser leurs templates.

## Ordre de travail et définition de terminé

Prochain cycle. Préparer le lot d'entraînement avec le chat template de Qwen, vérifier le masque de loss, lancer l'entraînement principal et réaliser la comparaison appariée avant/après.

Cette partie est terminée lorsque bibliothèque et splits sont gelés, JSONL régénérables, tests et audits exécutés, limites documentées et test indépendant isolé.
