"""Découverte générique Opendatasoft + test d'un service ArcGIS REST configuré.
Les résultats sont des métadonnées, pas des couches validées pour le Val-d'Oise.
"""
import csv,datetime,json,os,pathlib,requests
ROOT=pathlib.Path("outputs/portails_v07");ROOT.mkdir(parents=True,exist_ok=True)
cfg=json.loads(pathlib.Path("config/portails-v07.json").read_text(encoding="utf-8"))
s=requests.Session();s.headers["User-Agent"]="DataHubSIG/0.7 (+https://github.com/BABW4ter/DataHub-SIG)"
results=[];checks=[]
for p in cfg["portails"]:
    url=p["url"].rstrip("/")+"/api/explore/v2.1/catalog/datasets"
    try:
        r=s.get(url,params={"limit":100},timeout=35);r.raise_for_status();d=r.json()
        datasets=d.get("results",[])
        for item in datasets:
            meta=item.get("metas") or {}
            default=meta.get("default") or {}
            title=default.get("title") or item.get("dataset_id","")
            desc=default.get("description") or ""
            haystack=(str(title)+" "+str(desc)).lower()
            matches=[x for x in cfg["themes"] if x.lower() in haystack]
            if matches:
                results.append({"portail":p["id"],"dataset_id":item.get("dataset_id"),"titre":title,"correspondances":matches,"url":p["url"].rstrip("/")+"/explore/dataset/"+str(item.get("dataset_id"))+"/","couverture_95_verifiee":False})
        checks.append({"portail":p["id"],"status":"ok","catalogue_total":d.get("total_count"),"page_inspectee":len(datasets),"candidats":sum(x["portail"]==p["id"] for x in results)})
    except Exception as exc:checks.append({"portail":p["id"],"status":"error","detail":str(exc)})
# ArcGIS REST: service configurable. Aucun téléchargement sans couche explicite.
arc=os.getenv("ARCGIS_SERVICE_URL","").strip()
if arc:
    try:
        from urllib.parse import urlsplit
        parsed=urlsplit(arc)
        if parsed.scheme!="https" or not parsed.hostname or not (parsed.path.endswith("/FeatureServer") or parsed.path.endswith("/MapServer")):
            raise ValueError("URL HTTPS ArcGIS FeatureServer/MapServer requise")
        r=s.get(arc,params={"f":"json"},timeout=40);r.raise_for_status();j=r.json()
        if "error" in j:raise ValueError(str(j["error"]))
        layers=[{"id":x.get("id"),"name":x.get("name")} for x in j.get("layers",[])]
        (ROOT/"arcgis_couches.json").write_text(json.dumps({"service":arc,"layers":layers},ensure_ascii=False,indent=2),encoding="utf-8")
        checks.append({"portail":"arcgis_rest","status":"ok","couches":len(layers),"note":"Métadonnées seulement"})
    except Exception as exc:checks.append({"portail":"arcgis_rest","status":"error","detail":str(exc)})
report={"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"checks":checks,"candidats":results,"avertissement":"Découverte limitée aux 100 premiers jeux par portail; recherche textuelle, non preuve de couverture Val-d'Oise."}
(ROOT/"rapport.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
with (ROOT/"candidats.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f,delimiter=";");w.writerow(["portail","dataset_id","titre","correspondances","url","couverture_95_verifiee"])
    for x in results:w.writerow([x["portail"],x["dataset_id"],x["titre"],",".join(x["correspondances"]),x["url"],False])
print(json.dumps({"checks":checks,"nb_candidats":len(results)},ensure_ascii=False,indent=2))
if not any(x["status"]=="ok" for x in checks):raise SystemExit("Aucun catalogue joignable")
