"""Index des dalles MNH LiDAR HD sur le Val-d'Oise (WFS officiel IGN).
Attention: un index de dalles n'est PAS le raster MNH.
"""
import requests,json,pathlib,datetime,hashlib,time
O=pathlib.Path("outputs/vegetation95_lidar");O.mkdir(parents=True,exist_ok=True)
URL="https://data.geopf.fr/wfs/ows"
LAYER="IGNF_MNH_LIDAR-HD:dalle"
bbox="598357,6867922,670393,6905414,EPSG:2154"
s=requests.Session();s.headers["User-Agent"]="DataHubSIG-lidar-index/1.0"
r={"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"layer":LAYER,"bbox":bbox,"status":"failed","rasters_downloaded":0}
try:
    all=[];expected=None;start=0
    while start<20000:
        params={"service":"WFS","version":"2.0.0","request":"GetFeature","typeNames":LAYER,"srsName":"EPSG:2154","bbox":bbox,"outputFormat":"application/json","count":1000,"startIndex":start}
        resp=s.get(URL,params=params,timeout=120);resp.raise_for_status()
        data=resp.json()
        if data.get("type")!="FeatureCollection":raise ValueError("Réponse non GeoJSON "+str(data)[:200])
        features=data.get("features",[])
        if expected is None:
            matched=data.get("numberMatched")
            expected=int(matched) if str(matched).isdigit() else None
        if not features:break
        all.extend(features);start+=len(features)
        if len(features)<1000:break
        time.sleep(.2)
    if expected is not None and len(all)!=expected:raise ValueError(f"Pagination incomplète {len(all)}/{expected}")
    if not all:raise ValueError("Aucune dalle MNH sur l'emprise 95")
    if len(all)>=20000:raise ValueError("Limite de sécurité atteinte")
    p=O/"index_dalles_mnh_lidar_hd_95.geojson"
    p.write_text(json.dumps({"type":"FeatureCollection","features":all},ensure_ascii=False),encoding="utf-8")
    r.update({"status":"index_downloaded_validated","dalles":len(all),"expected":expected,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"file":p.name})
except Exception as e:r["error"]=str(e)
(O/"rapport_lidar.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(r,ensure_ascii=False,indent=2))
if r["status"]!="index_downloaded_validated":raise SystemExit("Index MNH indisponible")
