"""DataHub SIG V0.3 - interrogation directe de services publics.
Les réponses sont conservées sans supposer qu'un service couvre tout le département.
"""
import csv,json,os,pathlib,re,time
from urllib.parse import urlparse
import requests

DEP=os.getenv("DEP","95").strip()
if not re.fullmatch(r"(?:0[1-9]|[1-8][0-9]|9[0-5]|97[1-6]|2A|2B)",DEP):
    raise SystemExit("Code departement invalide")
THEMES=os.getenv("THEMES","tous").strip().lower()
OUT=pathlib.Path("outputs/connecteurs"); OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session()
S.headers.update({"User-Agent":"DataHubSIG/0.3 (+https://github.com/BABW4ter/DataHub-SIG)","Accept":"application/json"})
rapport={"departement":DEP,"themes":THEMES,"resultats":[],"erreurs":[]}
def fetch_json(url,params=None,timeout=50):
    response=S.get(url,params=params,timeout=timeout)
    response.raise_for_status()
    return response.json()
def save(name,source,data,meta=None):
    (OUT/(name+".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    rapport["resultats"].append({"connecteur":source,"fichier":name+".json",**(meta or {})})
def attempt(name,fn):
    try: fn()
    except Exception as exc:
        rapport["erreurs"].append({"connecteur":name,"erreur":str(exc)})
        print("ERREUR",name,str(exc),flush=True)

def geo():
    # API Géo: contour et population fournie par l'API, sans garantie de millésime INSEE précis.
    data=fetch_json(f"https://geo.api.gouv.fr/departements/{DEP}/communes",{"fields":"nom,code,population","format":"geojson","geometry":"contour"})
    save("communes_population","API Geo",data,{"nb":len(data.get("features",[]))})
    with (OUT/"population_communes.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f,delimiter=";");w.writerow(["code_insee","commune","population"])
        for feature in data.get("features",[]):
            p=feature.get("properties",{})
            w.writerow([p.get("code"),p.get("nom"),p.get("population")])

def hubeau():
    # API publique Hydrométrie v2, référentiel des stations.
    url="https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/stations"
    all_rows=[];page=1
    while page<=5:
        data=fetch_json(url,{"code_departement":DEP,"size":200,"page":page})
        rows=data.get("data",[])
        all_rows.extend(rows)
        if not rows or len(rows)<200:break
        page+=1
    save("hubeau_stations","Hub'Eau hydrometrie",{"data":all_rows,"pagination_limitee_a":5},{"nb":len(all_rows),"note":"Stations hydrometriques, pas toutes les donnees eau"})

def datagouv():
    # Découverte réelle par API, liens conservés, pas de téléchargement aveugle de fichiers lourds.
    themes={
      "vegetation":["arbres","foret"],
      "eau":["cours d'eau","qualite de l'eau"],
      "environnement":["biodiversite","risques naturels"],
      "urbanisme":["urbanisme","occupation du sol"],
      "foncier":["cadastre","DVF"],
      "population":["population communale"],
      "equipements":["equipements publics","etablissements scolaires"]
    }
    selected=[q for key,terms in themes.items() if THEMES in ("tous",key) for q in terms]
    if not selected: raise ValueError("Theme non reconnu")
    datasets=[]
    for term in selected:
        data=fetch_json("https://www.data.gouv.fr/api/1/datasets/",{"q":term,"page_size":10})
        for item in data.get("data",[]):
            datasets.append({"requete":term,"id":item.get("id"),"titre":item.get("title"),"page":item.get("page"),"ressources":[{"titre":r.get("title"),"format":r.get("format"),"url":r.get("url")} for r in (item.get("resources") or [])[:15]]})
        time.sleep(.1)
    save("datagouv_catalogue","data.gouv.fr",{"jeux_de_donnees":datasets},{"nb":len(datasets),"note":"Decouverte, pas encore collecte des ressources"})

def ign():
    # Interroger le catalogue public IGN STAC n'est pas universel pour toutes les bases.
    # On conserve la fiche de source, sans pretendre avoir telecharge BD TOPO/OCS GE.
    save("ign_reference","IGN Geoplateforme",{"catalogue":"https://geoservices.ign.fr/","telechargements":"https://data.geopf.fr/telechargement/","note":"Connecteur telechargement IGN a implementer par jeu de donnees (BD TOPO, OCS GE, BD Foret). Aucun fichier IGN telecharge."},{"statut":"reference_uniquement"})

def insee():
    save("insee_reference","INSEE",{"documentation":"https://www.insee.fr/fr/information/2862759","note":"Les jeux de recensement detailles necessitent une selection du millesime et des variables. Population communale de l'API Geo fournie separement."},{"statut":"reference_uniquement"})

attempt("API Geo",geo)
attempt("Hub'Eau hydrometrie",hubeau)
attempt("data.gouv.fr",datagouv)
attempt("IGN reference",ign)
attempt("INSEE reference",insee)
(OUT/"rapport.json").write_text(json.dumps(rapport,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"resultats":rapport["resultats"],"erreurs":rapport["erreurs"]},ensure_ascii=False,indent=2))
if not any(x.get("nb",0)>0 for x in rapport["resultats"]):
    raise SystemExit("Aucune donnee reelle recuperee, voir rapport.json")
