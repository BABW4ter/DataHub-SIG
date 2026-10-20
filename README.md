# DataHub SIG
Plateforme de collecte de données publiques territoriales pour QGIS.

## Domaines
Végétation, eau/environnement, urbanisme/foncier, population, équipements.

## Première version
- Interface de sélection des données dans `docs/index.html`.
- Collecte Overpass : arbres, alignements, espaces verts.
- Collecte population communale : API geo.api.gouv.fr (population municipale disponible dans sa réponse).
- Export GeoJSON et CSV, avec rapport de collecte.
- Lancement manuel dans **Actions → Collecte DataHub SIG → Run workflow**.

Les résultats sont téléchargeables dans les **Artifacts** du workflow. Les données OSM peuvent être incomplètes. Les services externes peuvent limiter les requêtes.

## Lancement
1. Ouvrir Actions, activer les workflows si GitHub le demande.
2. Ouvrir « Collecte DataHub SIG », choisir le département et les thèmes.
3. Cliquer Run workflow puis télécharger l'artifact à la fin.

Aucune clé nécessaire pour les connecteurs initiaux. Les connecteurs nécessitant des clés seront ajoutés avec GitHub Actions Secrets. Ne jamais mettre de jeton GitHub dans un site statique.
