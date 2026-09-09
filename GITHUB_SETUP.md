# Publication sur GitHub

Le projet est déjà initialisé comme dépôt Git local sur la branche `main`.

## Depuis l'interface GitHub

1. Créez un dépôt vide nommé `lidar-cave-scan` sur le compte `MrGesier`.
2. Ne cochez pas l'ajout automatique d'un README, d'un `.gitignore` ou d'une licence, car ils sont déjà fournis ici.
3. Dans ce dossier, lancez :

```bash
git remote add origin https://github.com/MrGesier/lidar-cave-scan.git
git push -u origin main
```

## Si un dépôt existe déjà

Si le dépôt existe sous un autre nom, remplacez l'URL :

```bash
git remote add origin https://github.com/MrGesier/NOM-DU-DEPOT.git
git push -u origin main
```

Si GitHub refuse le push parce que le dépôt distant contient déjà des fichiers, créez plutôt une branche ou clonez le dépôt distant puis copiez ce projet dedans.
