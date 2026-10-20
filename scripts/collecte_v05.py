"""Collecte V0.5 : API Géo, Géorisques et découverte des couches IGN WFS.
Les échecs individuels sont rapportés. Une réponse vide n'est pas une collecte réussie.
"""
import csv, datetime, json, os, pathlib, requests, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
DEP=os.getenv("DEP","95")
OUT=pathlib.Path("outputs/v05"); OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers["User-Agent"]="DataHubSIG/0.5 (+https://github.com/BABW4ter/DataHub-SIG)"
report={"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"departement":DEP,"sources":[]}
def add(name,status,count=0,detail="",files=None):
    report["sources"].append({"source":name,"status":status,"count":count,"detail":detail,"files":files or []})
def request(url,params=None,timeout=75):
    r=S.get(url,params=params,timeout=timeout);r.raise_for_status();return r
try:
    r=request(f"https://geo.api.gouv.fr/departements/{DEP}/communes",{"fields":"nom,code,population","format":"geojson","geometry":"contour"})
    geo=r.json(); features=geo.get("features",[])
    (OUT/"communes.geojson").write_text(json.dumps(geo,ensure_ascii=False),encoding="utf-8")
    add("API Geo","ok" if features else "empty",len(features),"Communes et population API Géo",["communes.geojson"])
except Exception as e:add("API Geo","error",detail=str(e))
try:
    # Service Géorisques : risques recensés commune par commune. Réponse et schéma bruts conservés.
    # L'endpoint peut changer ou refuser certaines requêtes ; le rapport le signale.
    communes=[x["properties"]["code"] for x in features] if "features" in locals() else []
    rows=[]; errors=[]
    def query(code):
        try:
            r=request("https://georisques.gouv.fr/api/v1/gaspar/risques",{"code_insee":code},timeout=25)
            return {"code_insee":code,"response":r.json()},None
        except Exception as e:return None,{"code_insee":code,"error":str(e)}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for item,error in pool.map(query,communes):
            if item:rows.append(item)
            if error:errors.append(error)
    payload={"departement":DEP,"reponses":rows,"erreurs":errors}
    (OUT/"georisques_risques_brut.json").write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
    add("Géorisques GASPAR","ok" if rows and not errors else ("partial" if rows else "error"),len(rows),f"{len(errors)} communes en erreur; réponses brutes non normalisées",["georisques_risques_brut.json"])
except Exception as e:add("Géorisques GASPAR","error",detail=str(e))
try:
    r=request("https://data.geopf.fr/wfs/ows",{"service":"WFS","request":"GetCapabilities","version":"2.0.0"},timeout=90)
    root=ET.fromstring(r.content)
    layers=[]
    for ft in root.findall(".//{http://www.opengis.net/wfs/2.0}FeatureType"):
        name=ft.findtext("{http://www.opengis.net/wfs/2.0}Name")
        title=ft.findtext("{http://www.opengis.net/wfs/2.0}Title")
        if name:layers.append({"name":name,"title":title})
    (OUT/"ign_wfs_couches.json").write_text(json.dumps({"couches":layers,"endpoint":"https://data.geopf.fr/wfs/ows","note":"Catalogue WFS, pas téléchargement des géométries"},ensure_ascii=False,indent=2),encoding="utf-8")
    add("IGN WFS","ok" if layers else "empty",len(layers),"Catalogue des types d'entités, géométries non téléchargées",["ign_wfs_couches.json"])
except Exception as e:add("IGN WFS","error",detail=str(e))
(OUT/"rapport_v05.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
with (OUT/"statut.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f,delimiter=";");w.writerow(["source","status","count","detail"])
    for x in report["sources"]:w.writerow([x["source"],x["status"],x["count"],x["detail"]])
print(json.dumps(report,ensure_ascii=False,indent=2))
if not any(x["status"]=="ok" for x in report["sources"]):raise SystemExit("Aucune source collectée avec succès")
