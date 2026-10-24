import datetime as dt,hashlib,json,pathlib,re,time,xml.etree.ElementTree as ET
from urllib.parse import urljoin,urlparse
import requests
OUT=pathlib.Path("outputs/vegetation95");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers["User-Agent"]="DataHubSIG-vegetation95/1.0 (+https://github.com/BABW4ter/DataHub-SIG)"
report={"date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"scope":"Val-d'Oise 95","results":{},"downloaded":[]}
def status(key,state,detail,**kw):
 report["results"][key]={"status":state,"detail":detail,**kw};print(key,state,detail,flush=True)
def get(url,params=None,timeout=80):
 for i in range(3):
  try:
   r=S.get(url,params=params,timeout=timeout);r.raise_for_status();return r
  except requests.RequestException:
   if i==2:raise
   time.sleep(2**i)
def save(name,data):
 p=OUT/name;p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");return p
def register(source,p,count):
 b=p.read_bytes();report["downloaded"].append({"source":source,"file":p.name,"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"count":count})
try:
 geo=get("https://geo.api.gouv.fr/departements/95/communes",{"fields":"nom,code,population","format":"geojson","geometry":"contour"},100).json()
 ff=geo.get("features",[]);codes=[str(f.get("properties",{}).get("code","")) for f in ff]
 ok=len(ff)==183 and len(set(codes))==183 and all(x.startswith("95") for x in codes) and all(f.get("geometry",{}).get("type") in ("Polygon","MultiPolygon") for f in ff)
 if ok:register("communes",save("communes_95.geojson",geo),len(ff))
 status("communes","verified" if ok else "invalid",f"{len(ff)} communes, géométries contrôlées: {ok}")
except Exception as e:status("communes","error",str(e)[:400])
try:
 ds="mos-occupation-du-sol-2025-and-2021-en-79-postes-de-la-region-ile-de-france"
 metadata=get(f"https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/{ds}").json()
 save("mos_metadata.json",metadata)
 status("mos","metadata_only","Métadonnées disponibles, export complet non confirmé")
except Exception as e:status("mos","error",str(e)[:400])
def entries(content,base):
 root=ET.fromstring(content);ns={"a":"http://www.w3.org/2005/Atom"};out=[]
 for e in root.findall(".//a:entry",ns):
  links=[]
  for l in e.findall("a:link",ns):
   if l.get("href"):links.append({"url":urljoin(base,l.get("href")),"rel":l.get("rel","")})
  out.append({"title":e.findtext("a:title",default="",namespaces=ns),"links":links})
 return out
for key,prod in {"bd_foret":"BDFORET","bd_topo_vegetation":"BDTOPO","ocs_ge":"OCSGE","rpg_2025":"RPG","lidar_hd_mnh":"MNH-LIDARHD"}.items():
 try:
  base="https://data.geopf.fr/telechargement/resource/"+prod
  r=get(base,{"limit":50,"page":1},100);items=entries(r.content,r.url)
  matching=[x for x in items if re.search("95|D095|VAL.D.OISE|ILE.DE.FRANCE|ÎLE.DE.FRANCE|R11|2025",x["title"],re.I)]
  sub=[]
  for x in (matching[:3] if matching else items[:2]):
   for l in x["links"]:
    u=l["url"]
    if urlparse(u).hostname=="data.geopf.fr" and "/resource/" in u and u!=r.url:
     try:
      rr=get(u,{"limit":50,"page":1},100);sub+=entries(rr.content,rr.url)
     except Exception as e:sub.append({"error":str(e)[:150],"url":u})
  save("ign_"+key+"_catalogue.json",{"resource":prod,"entries":items,"children":sub})
  status(key,"metadata_only",f"{len(items)} entrées, {len(sub)} sous-entrées ; aucun fichier lourd téléchargé",product=prod)
 except Exception as e:status(key,"error",str(e)[:400],product=prod)
try:
 wfs="https://data.geopf.fr/wfs/ows"
 root=ET.fromstring(get(wfs,{"service":"WFS","request":"GetCapabilities","version":"2.0.0"},120).content)
 types=[]
 for ft in root.findall(".//{http://www.opengis.net/wfs/2.0}FeatureType"):
  n=ft.findtext("{http://www.opengis.net/wfs/2.0}Name","");t=ft.findtext("{http://www.opengis.net/wfs/2.0}Title","")
  if re.search("vegetation",n+" "+t,re.I):types.append({"name":n,"title":t})
 save("wfs_vegetation_types.json",types)
 if not types:status("bdtopo_wfs_extrait","unavailable","Aucune couche végétation trouvée")
 else:
  layer=next((x for x in types if "BDTOPO" in x["name"].upper()),types[0])
  obj=get(wfs,{"service":"WFS","version":"2.0.0","request":"GetFeature","typeNames":layer["name"],"outputFormat":"application/json","count":1000,"srsName":"EPSG:4326","bbox":"1.45,48.75,2.65,49.27,EPSG:4326"},160).json()
  ff=obj.get("features",[])
  if ff:register("bdtopo_wfs_extrait",save("bdtopo_vegetation_extrait.geojson",obj),len(ff))
  status("bdtopo_wfs_extrait","sample_only" if ff else "empty",f"{len(ff)} objets WFS, extrait bbox non exhaustif",layer=layer["name"])
except Exception as e:status("bdtopo_wfs_extrait","error",str(e)[:400])
try:
 query='[out:json][timeout:120];area["name"="Val-d\'Oise"]["admin_level"="6"]->.a;(node["natural"="tree"](area.a);way["natural"="tree_row"](area.a););out center;'
 last=None
 for url in ["https://overpass.kumi.systems/api/interpreter","https://overpass-api.de/api/interpreter"]:
  try:
   r=S.post(url,data={"data":query},timeout=(20,180));r.raise_for_status();elements=r.json().get("elements",[])
   if not elements:raise ValueError("Aucun objet")
   features=[]
   for e in elements:
    lon=e.get("lon") or e.get("center",{}).get("lon");lat=e.get("lat") or e.get("center",{}).get("lat")
    if lon is None or lat is None or not (1.4<float(lon)<2.7 and 48.7<float(lat)<49.4):continue
    features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},"properties":{"osm_type":e.get("type"),"osm_id":e.get("id"),**e.get("tags",{})}})
   register("arbres_osm",save("arbres_osm_95.geojson",{"type":"FeatureCollection","features":features}),len(features))
   status("arbres_osm","verified_partial",f"{len(features)} arbres OSM, inventaire participatif non exhaustif")
   break
  except Exception as e:last=e
 else:raise last
except Exception as e:status("arbres_osm","error",str(e)[:400])
try:
 catalog=[]
 for q in ["arbres remarquables Val-d'Oise","inventaire arbres 95"]:
  d=get("https://www.data.gouv.fr/api/1/datasets/",{"q":q,"page_size":20}).json()
  for x in d.get("data",[]):catalog.append({"title":x.get("title"),"id":x.get("id"),"resources":[{"title":a.get("title"),"url":a.get("url"),"format":a.get("format")} for a in x.get("resources",[])]})
 save("arbres_catalogue.json",catalog)
 status("inventaires_arbres","metadata_only",f"{len(catalog)} candidats ; couverture 95 non vérifiée")
except Exception as e:status("inventaires_arbres","error",str(e)[:400])
report["complete"]=len(report["results"])==10 and all(x["status"]=="verified" for x in report["results"].values())
save("bilan_collecte.json",report)
print(json.dumps({"complete":report["complete"],"statuses":{k:v["status"] for k,v in report["results"].items()}},ensure_ascii=False))
