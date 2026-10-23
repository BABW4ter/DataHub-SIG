"""Collecte contrôlée des données végétation du Val-d'Oise.
Ne déclare 'collecté' qu'après validation du fichier et de son contenu.
Les couches volumineuses (RPG, IGN, LiDAR) restent à télécharger via les interfaces dédiées.
"""
import datetime,hashlib,json,os,pathlib,requests,zipfile,io
from urllib.parse import urlparse
OUT=pathlib.Path("outputs/vegetation95");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers.update({"User-Agent":"DataHubSIG-vegetation95/1.0","Accept":"application/json, */*"})
MAX_BYTES=25*1024*1024
report={"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"department":"95","sources":[]}
def record(name,state,**kw):
    report["sources"].append({"name":name,"status":state,**kw})
def get(url,params=None,timeout=70):
    r=S.get(url,params=params,timeout=timeout);r.raise_for_status();return r
# GeoJSON contours administratifs, contrôle du nombre, codes uniques et géométries.
try:
    url="https://geo.api.gouv.fr/departements/95/communes"
    data=get(url,{"fields":"nom,code,population","format":"geojson","geometry":"contour"}).json()
    ft=data.get("features",[])
    codes=[str(x.get("properties",{}).get("code","")) for x in ft]
    assert len(ft)==183 and len(set(codes))==183
    assert all(c.startswith("95") and x.get("geometry",{}).get("type") in ("Polygon","MultiPolygon") for c,x in zip(codes,ft))
    p=OUT/"communes_95.geojson";p.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    record("Limites des 183 communes","downloaded_validated",features=len(ft),file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source=url)
except Exception as e:record("Limites des 183 communes","failed",error=str(e))
# MOS : contrôle exhaustivité du résultat compté, sans prétendre que l'export complet a été téléchargé.
try:
    base="https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/mos-occupation-du-sol-2025-and-2021-en-79-postes-de-la-region-ile-de-france"
    params={"where":"insee >= 95000 AND insee < 96000","limit":1}
    data=get(base+"/records",params=params).json()
    count=data.get("total_count")
    assert isinstance(count,int) and count>0
    record("MOS 2021/2025","accessible_not_downloaded",count=count,source=base,reason="Export départemental volumineux; workflow MOS dédié disponible")
except Exception as e:record("MOS 2021/2025","failed",error=str(e))
# Métadonnées officielles et ressources compactes du catalogue data.gouv.fr.
datasets=[
("Massifs forestiers du Val-d'Oise","les-massifs-forestiers-du-val-doise"),
("Forêts domaniales et publiques","forets-domaniales-et-publiques"),
("Forêts soumises au régime forestier","frt95-soumise"),
("Arbres remarquables","arbres-remarquables-2014-idf"),
]
for name,slug in datasets:
    try:
        api="https://www.data.gouv.fr/api/1/datasets/"+slug+"/"
        meta=get(api).json()
        resources=meta.get("resources",[])
        candidates=[]
        for r in resources:
            url=r.get("url") or ""
            fmt=(r.get("format") or "").lower()
            size=r.get("filesize") or 0
            if url.startswith("https://") and (not size or size<MAX_BYTES) and fmt in ("zip","shp","geojson","json","csv"):
                candidates.append((r,url,fmt))
        entry={"metadata_source":api,"dataset_id":meta.get("id"),"resources":len(resources)}
        done=False;last=""
        for r,url,fmt in candidates[:5]:
            try:
                with S.get(url,timeout=(20,90),stream=True) as resp:
                    resp.raise_for_status()
                    buf=io.BytesIO()
                    for chunk in resp.iter_content(1024*256):
                        if chunk:buf.write(chunk)
                        if buf.tell()>MAX_BYTES:raise ValueError("Fichier trop volumineux")
                raw=buf.getvalue()
                if len(raw)<30:raise ValueError("Fichier vide")
                ext="zip" if zipfile.is_zipfile(io.BytesIO(raw)) else fmt
                if ext=="zip":
                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        names=z.namelist()
                        if z.testzip() is not None:raise ValueError("ZIP corrompu")
                        if not any(x.lower().endswith((".shp",".geojson",".json",".csv")) for x in names):raise ValueError("ZIP sans données SIG ou tabulaires")
                elif ext in ("json","geojson"):
                    json.loads(raw.decode("utf-8-sig"))
                elif ext=="csv":
                    if b"\n" not in raw:raise ValueError("CSV sans lignes")
                else:raise ValueError("Format non validable")
                p=OUT/(slug+"."+ext);p.write_bytes(raw)
                record(name,"downloaded_validated",file=p.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),**entry)
                done=True;break
            except Exception as exc:last=str(exc)
        if not done:record(name,"metadata_only",reason=last or "Aucune ressource compatible et compacte",**entry)
    except Exception as exc:record(name,"failed",error=str(exc))
# Inventaire : ces sources ne sont PAS téléchargées par ce collecteur.
for name,reason in [
("RPG 2025","Produit SIG national/départemental volumineux; pas de téléchargement automatisé vérifié"),
("BD Forêt IGN","Téléchargement produit IGN à configurer et vérifier"),
("BD TOPO végétation","Extraction des couches végétation à configurer"),
("OCS GE","Téléchargement du millésime local à configurer"),
("LiDAR HD / MNH","Dalles raster volumineuses; stockage et mosaïquage nécessaires"),
("Inventaires d'arbres communaux","Sources multiples, couverture inégale; inventaire non exhaustif")]:
    record(name,"not_downloaded",reason=reason)
(OUT/"rapport.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"states":{x:sum(s["status"]==x for s in report["sources"]) for x in sorted(set(s["status"] for s in report["sources"]))},"report":"outputs/vegetation95/rapport.json"},ensure_ascii=False))
