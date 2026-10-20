"""Découverte de jeux de données data.gouv.fr pour les domaines DataHub SIG."""
import json, os, pathlib, re, sys, time
import requests

QUERIES = {
 "vegetation": ["végétation", "forêt", "arbres", "occupation du sol"],
 "eau": ["cours d'eau", "qualité eau", "zones humides"],
 "environnement": ["biodiversité", "risques naturels"],
 "urbanisme": ["PLU", "bâtiments", "artificialisation"],
 "foncier": ["cadastre", "valeurs foncières"],
 "population": ["recensement population", "population communale"],
 "equipements": ["base permanente équipements", "établissements scolaires"]
}
theme = os.environ.get("THEME", "vegetation").lower()
if theme not in QUERIES and theme != "tous":
    sys.exit("Thème inconnu: " + theme)
dep = os.environ.get("DEP", "95")
if not re.fullmatch(r"(?:0[1-9]|[1-8][0-9]|9[0-5]|97[1-6]|2A|2B)", dep):
    sys.exit("Code département invalide")
out = pathlib.Path("outputs")
out.mkdir(exist_ok=True)
session = requests.Session()
session.headers["User-Agent"] = "DataHubSIG/0.2 (catalogue public)"
terms = [(k,q) for k,qs in QUERIES.items() for q in qs if theme in ("tous",k)]
items, errors = [], []
for category, query in terms:
    try:
        resp = session.get("https://www.data.gouv.fr/api/1/datasets/",params={"q":query,"page_size":10},timeout=35)
        resp.raise_for_status()
        for d in resp.json().get("data",[]):
            resources = d.get("resources") or []
            items.append({"theme":category,"requete":query,"titre":d.get("title"),"id":d.get("id"),"url":d.get("page"),"date_maj":d.get("last_update"),"licence":d.get("license"),"ressources":[{"titre":r.get("title"),"format":r.get("format"),"url":r.get("url")} for r in resources[:15]],"attention":"Résultat national ou régional : vérifier la couverture du département "+dep})
    except (requests.RequestException,ValueError) as e:
        errors.append({"requete":query,"erreur":str(e)})
    time.sleep(.15)
unique = {d["id"]:d for d in items if d["id"]}
result = {"departement_cible":dep,"theme":theme,"nb_resultats":len(unique),"jeux_de_donnees":list(unique.values()),"erreurs":errors,"note":"Catalogue de découverte : fichiers non téléchargés ni découpés au département."}
(out/"catalogue_decouverte.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print("Jeux de données identifiés:",len(unique),"Erreurs:",len(errors))
if not unique:
    sys.exit("Aucun résultat. Vérifier outputs/catalogue_decouverte.json")
