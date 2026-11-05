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
