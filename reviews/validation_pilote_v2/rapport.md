# Contrôle du pilote v2

## Contrôles automatiques

Le JSON du pilote est comparé à une transcription des seuls énoncés. Le pilote fournit des objets JSON, qui sont sérialisés pour ce contrôle.

Les contraintes sont comparées à l'ordre près et à un facteur positif près. Une inégalité peut être écrite dans l'autre sens en changeant les deux signes. L'objectif et les bornes sont comparés dans les unités de l'énoncé.

| Vérification | Cas réussis |
| --- | ---: |
| JSON et schéma | 10/10 |
| Formulation | 10/10 |
| Résolution | 10/10 |
| Succès sur la référence | 10/10 |

### Anomalies automatiques

- Aucune anomalie détectée.

## Relecture de l’assistant

- Les dix énoncés et leurs formulations ont été relus. Les coefficients, les seconds membres, les sens des contraintes, l'objectif et les bornes correspondent.
- Consigne à clarifier avant réutilisation dans le corpus. Les dix énoncés d'origine demandent de déterminer des quantités. Le dossier précise que le travail demandé est de formuler le programme linéaire. Les énoncés d'origine sont reproduits intégralement pour la validation.
- `pilot_production_004` : la limite de bois de 160 kg est redondante. La limite de travail et les bornes impliquent x1 + x2 ≤ 37/2, donc au plus 111 kg de bois.
- `pilot_production_005` : la limite de bois de 59 kg est redondante. La limite de travail impose x1 + x2 ≤ 54/8, donc au plus 40,5 kg de bois.
- `pilot_mixing_004` : le minimum de 24 g de Q est redondant. La ligne P et les bornes impliquent Q ≥ (8/9) × 156 = 416/3 g.
- `pilot_mixing_005` : le minimum de 94 g de P est redondant. La ligne Q et les bornes impliquent P ≥ (8/3) × 194 = 1552/3 g.
- Les quatre contraintes redondantes figurent dans les énoncés et doivent figurer dans les JSON attendus. Elles permettent de vérifier qu'une omission peut passer inaperçue si l'on examine seulement l'optimum.
- `pilot_production_001` partage son tirage numérique avec `pilot_mixing_005` de l'archive v1 (graine 51). Les dix cas de la v2 sont distincts.

## Validation de Marc

Le 21 novembre 2026, Marc a confirmé avoir vérifié les dix problèmes du PDF `validation.pdf`. Aucune correction supplémentaire signalée.
