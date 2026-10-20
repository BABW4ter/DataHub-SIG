# DataHub SIG — état réel des connecteurs

**Ne pas confondre** disponibilité d'une page, API testée et moissonnage de données.

| Source | Statut du code | Contrôle |
|---|---|---|
| API Géo | Collecte de communes/population | Vérification de 183 communes |
| OSM Overpass | Collecte de végétation dans collecte.yml | Disponibilité du serveur |
| Hub'Eau hydrométrie | Collecte des stations | Résultat non vide |
| data.gouv.fr | Découverte de ressources | Résultat non vide |
| IGN | Référence seulement | Accès au portail |
| INSEE détaillé | Référence seulement | Accès à la documentation |
| BRGM, Sandre, BNPE, INPN, GPU, Cadastre, DVF, transport, éducation, MOS, Sirene, Mélodi | Référence seulement | Accès aux portails |
| Géorisques | Endpoint de test, pas de collecte intégrée | Disponibilité variable |

La surveillance s'exécute toutes les six heures et publie un rapport comme artifact.
Le moissonnage des connecteurs **déjà opérationnels** s'exécute chaque lundi et publie un artifact.
Ces artifacts expirent après 30 jours : **ce n'est pas une base de données persistante**.
Les workflows planifiés GitHub Actions peuvent être retardés ou désactivés après inactivité prolongée.
Les connecteurs restants nécessitent des implémentations spécifiques, gestion des pages, licences, limites et millésimes.
