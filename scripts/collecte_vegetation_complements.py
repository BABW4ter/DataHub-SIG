"""Collecte des jeux de végétation 95 absents du bundle IGN local.
Contrôle des volumes, SHA256, GeoJSON et pages WFS. Les échecs restent explicites.
"""
import datetime as dt,hashlib,json,pathlib,time,requests
OUT=pathlib.Path("outputs/vegetation95_complements");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers.update({"User-Agent":"DataHubSIG-vegetation95/2.0","Accept":"application/json, */*"})
R={"date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"sources":[]}
def log(name,status,**kw):
    R["sources"].append({"name":name,"status":status,**kw});print(name,status,kw,flush=True)
def get(url,params=None,timeout=(25,90)):
    error=None
    for attempt in range(4):
        try:
            r=S.get(url,params=params,timeout=timeout)
            r.raise_for_status();return r
        except requests.RequestException as exc:
            error=exc
            if attempt<3:time.sleep(2**attempt)
    raise error
def check_geojson(p,expected=None):
    data=json.loads(p.read_text(encoding="utf-8-sig"))
    if data.get("type")!="FeatureCollection":raise ValueError("Pas de FeatureCollection")
    ft=data.get("features",[])
    if not ft or any(not f.get("geometry") or not f["geometry"].get("coordinates") for f in ft):raise ValueError("Géométries vides")
    if expected is not None and len(ft)!=expected:raise ValueError(f"Nombre {len(ft)} != {expected}")
    return {"count":len(ft),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
mos="https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/mos-occupation-du-sol-2025-and-2021-en-79-postes-de-la-region-ile-de-france"
try:
    where="insee >= 95000 AND insee < 96000"
    count=get(mos+"/records",{"where":where,"limit":1}).json().get("total_count")
    if not isinstance(count,int) or count<1000:raise ValueError(f"Nombre MOS suspect: {count}")
    p=OUT/"mos_2021_2025_95.geojson"
    with S.get(mos+"/exports/geojson",params={"where":where},timeout=(30,600),stream=True) as response:
        response.raise_for_status();size=0
        with p.open("wb") as f:
            for chunk in response.iter_content(1024*1024):
                if not chunk:continue
                size+=len(chunk)
                if size>650*1024*1024:raise ValueError("MOS >650 MiB, interrompu")
                f.write(chunk)
    log("MOS 2021/2025","downloaded_validated",expected=count,file=p.name,**check_geojson(p,count))
except Exception as exc:log("MOS 2021/2025","failed",error=str(exc))
arbre="https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/arbre_remarquable"
try:
    count=get(arbre+"/records",{"limit":1}).json().get("total_count")
    if not isinstance(count,int) or count<1:raise ValueError("Nombre d'arbres suspect")
    p=OUT/"arbres_remarquables_idf.geojson";p.write_bytes(get(arbre+"/exports/geojson",timeout=(30,150)).content)
    log("Arbres remarquables IDF","downloaded_validated",expected=count,file=p.name,**check_geojson(p,count))
except Exception as exc:log("Arbres remarquables IDF","failed",error=str(exc))
wfs="https://data.geopf.fr/wfs/ows"
bbox="598357,6867922,670393,6905414,EPSG:2154"
def collect_wfs(layer,filename,limit=60000):
    features=[];start=0;expected=None;pages=0
    while start<limit:
        params={"service":"WFS","version":"2.0.0","request":"GetFeature","typeNames":layer,"srsName":"EPSG:2154","bbox":bbox,"outputFormat":"application/json","count":1000,"startIndex":start}
        data=get(wfs,params,timeout=(30,150)).json()
        if data.get("type")!="FeatureCollection":raise ValueError("Réponse WFS non GeoJSON: "+str(data)[:200])
        part=data.get("features",[])
        if expected is None:
            matched=data.get("numberMatched")
            expected=int(matched) if str(matched).isdigit() else None
        if not part:break
        features.extend(part);start+=len(part);pages+=1
        if len(part)<1000:break
        time.sleep(.2)
    if expected is not None and len(features)!=expected:raise ValueError(f"WFS incomplet: {len(features)}/{expected}")
    if len(features)>=limit:raise ValueError("Limite de sécurité WFS atteinte")
    if not features:raise ValueError("0 objet WFS")
    p=OUT/filename;p.write_text(json.dumps({"type":"FeatureCollection","features":features},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    return p,check_geojson(p),expected,pages
for name,layer,filename in [
    ("BD TOPO végétation","BDTOPO_V3:zone_de_vegetation","bd_topo_vegetation_95.geojson"),
    ("Index LiDAR HD MNH","IGNF_LIDAR-HD_TA:mnh-dalle","lidar_mnh_dalles_95.geojson")
]:
    try:
        p,info,expected,pages=collect_wfs(layer,filename)
        log(name,"downloaded_validated",file=p.name,expected=expected,pages=pages,**info)
    except Exception as exc:log(name,"failed",error=str(exc))
log("LiDAR HD MNH rasters 0,5m","not_downloaded",reason="Volumes multi-Go : seul un index WFS est recherché; aucun TIFF n'est collecté")
(OUT/"rapport_complements.json").write_text(json.dumps(R,ensure_ascii=False,indent=2),encoding="utf-8")
if not any(x["status"]=="downloaded_validated" for x in R["sources"]):raise SystemExit("Aucune nouvelle source validée")
