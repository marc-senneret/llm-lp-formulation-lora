# Templates du corpus

- `../configs/generate_v1.json` : plages numériques, quotas, graine et tolérances.
- `../configs/template_contract_v1.json` : règles communes et format des candidats. Ce fichier décrit un contrat ; il ne constitue pas un validateur JSON Schema exécuté.
- `candidates.json` : liste des templates proposés, à qualifier.
- `corpus_v1_candidates.json` : seize gabarits préparés par Codex pour l'aperçu du corpus. Les deux gabarits du pilote sont repris avec une consigne de formulation et leur lignée d'origine. Chaque entrée porte son affectation.
- `accepted.json` : les seize gabarits admis après les contrôles et la relecture de Marc. Ce registre sert à générer les lots définitifs.

Chaque template contient un énoncé anglais complet. Produits, ressources, unités, nombre de contraintes et sens mathématiques sont fixes. Seuls les coefficients et seconds membres sont remplacés par des nombres. Aucun tirage de ressources et aucune concaténation de fragments textuels ne sont nécessaires.

Les métadonnées décrivent le sens des variables, de l'objectif et de chaque ligne de contrainte. Les tableaux de coefficients suivent toujours l'ordre `x1`, `x2`. La position de contrainte commence à 1 pour les noms de champs ; `reference_constraint_index` commence à 0 pour la liste JSON de référence. `constraint_order_in_text` décrit l'ordre de première apparition, y compris lorsque les coefficients sont présentés par produit.

Dans `required_holes`, `{i}` est une notation de règle : pour chaque indice de 1 à `constraint_count`, les trois champs correspondants sont requis. Ce n'est pas un champ autorisé dans le texte. Les champs de la troisième contrainte sont interdits dans un template à deux contraintes. Un champ requis peut apparaître plusieurs fois.

Seul le champ `text`, une fois rendu, devient l'énoncé. Les métadonnées ne sont pas ajoutées au prompt. Les unités abrégées (`h`, `kg`, `EUR`) évitent les accords singulier/pluriel dépendant des nombres.

Le candidat atelier provient de l'exemple rédigé dans la conversation du projet, puis simplifié le 18 novembre 2026. Sa lignée est conservée. Il reste `needs_review` : aucun contrôle humain d'admission n'est enregistré. Une paraphrase ou un changement de contexte de cette même structure garde la même lignée.

Le candidat mélange/achat a été rédigé dans la conversation du projet le 18 novembre 2026 : achat de deux suppléments, coût à minimiser, exigences minimales de deux nutriments. Son statut reste `needs_review`.

Les deux exemples complets (rendus, références et résultats du solveur) sont consignés dans `../reports/contract_examples_v1.md`. Ils documentent le contrat de l'étape 1. Marc a validé les dix exemples du pilote v2 dans `../runs/generation_pilot_v2/review.md`, dont six avec deux variables positives et deux contraintes actives. La v1 est conservée séparément. Le dossier `../runs/corpus_v1_preview/` présente les rendus des seize gabarits du corpus, y compris ceux à trois contraintes, pour la relecture.
