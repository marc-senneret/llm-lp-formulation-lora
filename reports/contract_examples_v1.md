# Étape 1 — Exemples du contrat

Vérification exécutée le 18 novembre 2026. 
Exemples de développement fixes, hors des splits du corpus. Ce contrôle ne constitue ni le pilote de dix exemples ni une admission humaine des templates.

## production_by_product_001

A workshop produces tables and chairs. Let x1 be the number of tables produced and x2 the number of chairs produced. Both quantities may take any nonnegative real value, including fractional values. The profit per table is 37 EUR, and the profit per chair is 43 EUR. Producing each table requires 2 h of labor and 3 kg of wood. Producing each chair requires 1 h of labor and 4 kg of wood. At most 100 h of labor and 180 kg of wood are available. Determine the production quantities that maximize total profit.

Référence (variables continues ; bornes non négatives sans plafond) :

```json
{
  "variables": [
    "x1",
    "x2"
  ],
  "objective": {
    "sense": "max",
    "coefficients": [
      37,
      43
    ]
  },
  "constraints": [
    {
      "coefficients": [
        2,
        1
      ],
      "sense": "<=",
      "rhs": 100
    },
    {
      "coefficients": [
        3,
        4
      ],
      "sense": "<=",
      "rhs": 180
    }
  ],
  "bounds": [
    [
      0,
      null
    ],
    [
      0,
      null
    ]
  ]
}
```

Résultat du solveur :

```json
{
  "status": "optimal",
  "message": "Optimal solution found.",
  "solution": [
    44.0,
    12.000000000000002
  ],
  "objective_value": 2144.0
}
```

## mixing_by_requirement_001

A farm purchases two feed supplements, supplement A and supplement B. Let x1 be the amount of supplement A purchased, measured in kg, and x2 the amount of supplement B purchased, measured in kg. Both amounts may take any nonnegative real value, including fractional values. The cost per kg is 7 EUR for supplement A and 11 EUR for supplement B. Each kg of supplement A supplies 2 g of nutrient P, and each kg of supplement B supplies 5 g of nutrient P. The total amount purchased must supply at least 40 g of nutrient P. Each kg of supplement A supplies 3 g of nutrient Q, and each kg of supplement B supplies 1 g of nutrient Q. The total amount purchased must supply at least 30 g of nutrient Q. Determine the amounts of the two supplements to purchase to minimize total cost.

Référence (variables continues ; bornes non négatives sans plafond) :

```json
{
  "variables": [
    "x1",
    "x2"
  ],
  "objective": {
    "sense": "min",
    "coefficients": [
      7,
      11
    ]
  },
  "constraints": [
    {
      "coefficients": [
        2,
        5
      ],
      "sense": ">=",
      "rhs": 40
    },
    {
      "coefficients": [
        3,
        1
      ],
      "sense": ">=",
      "rhs": 30
    }
  ],
  "bounds": [
    [
      0,
      null
    ],
    [
      0,
      null
    ]
  ]
}
```

Résultat du solveur :

```json
{
  "status": "optimal",
  "message": "Optimal solution found.",
  "solution": [
    8.461538461538462,
    4.615384615384615
  ],
  "objective_value": 110.0
}
```

## Correspondance texte / formulation

- Production : x1 = tables, x2 = chaises ; profit en EUR ; ligne 1 = travail en h, ligne 2 = bois en kg. Chaque coefficient est une consommation par produit ; « at most » exprime les deux limites <=.
- Mélange/achat : x1 = kg de supplément A, x2 = kg de supplément B ; coût en EUR/kg ; ligne 1 = apport de P en g, ligne 2 = apport de Q en g. Les coefficients sont en g/kg et les exigences en g : aucune conversion à effectuer. « At least » exprime les deux exigences >=.
- Les deux textes définissent explicitement les variables, les valeurs réelles non négatives et le sens de l'objectif. Aucun total de masse, proportion, plafond d'achat ou condition entière supplémentaire n'est imposé.
- Chaque rôle numérique reçoit une valeur distincte dans son exemple pour faciliter la relecture. Les champs sont tous remplis et correspondent aux lignes déclarées.

## Contrôle indépendant des résultats

- Production : les sommets admissibles sont (0, 0), (50, 0), (44, 12), (0, 45). Avec les profits unitaires 37 et 43, leurs profits sont respectivement 0, 1850, 2144 et 1935. Le maximum est 2144 pour (44, 12).
- Mélange/achat : les sommets de la frontière inférieure sont (20, 0), (110/13, 60/13), (0, 30). Leurs coûts sont 140, 110 et 330. Les coûts unitaires étant positifs, aucune direction non bornée ne diminue le coût : le minimum vaut 110.

## Limites et suite

L'étape 1 est documentée avec un exemple complet par famille et une vérification technique de correspondance. Les candidats restent `needs_review` et la bibliothèque acceptée reste vide. La qualification de l'étape 4 exige encore les rendus prévus et la relecture de Marc. Le pilote de l'étape 2, ses dix exemples et les templates à trois contraintes ne sont pas réalisés.
