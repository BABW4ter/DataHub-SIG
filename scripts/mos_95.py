"""Collecte MOS 2021/2025 (79 postes) du Val-d'Oise via Opendatasoft.
Par défaut: vérification des enregistrements. EXPORT_MOS=true: GeoJSON départemental.
"""
import datetime,json,os,pathlib,requests
ROOT="https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets"
DATASET="mos-occupation-du-sol-2025-and-2021-en-79-postes-de-la-region-ile-de-france"
OUT=pathlib.Path("outputs/mos95");OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers["User-Agent"]="DataHubSIG/0.6 (+https://github.com/BABW4ter/DataHub-SIG)"
WHERE="insee >= 95000 AND insee < 96000"
report={"source":"Institut Paris Region / Open data Ile-de-France","dataset":DATASET,"where":WHERE,"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"statut":"error"}
try:
    endpoint=f"{ROOT}/{DATASET}/records"
    r=S.get(endpoint,params={"where":WHERE,"limit":1},timeout=90)
    r.raise_for_status(); data=r.json()
    report["total_records_95"]=data.get("total_count",0)
    report["statut"]="ok" if report["total_records_95"]>0 else "empty"
    report["mode"]="verification"
    if os.getenv("EXPORT_MOS","false").lower()=="true" and report["total_records_95"]>0:
        url=f"{ROOT}/{DATASET}/exports/geojson"
        # Limite de sécurité : ne pas épuiser le stockage temporaire Actions.
        with S.get(url,params={"where":WHERE},timeout=(30,300),stream=True) as response:
            response.raise_for_status()
            target=OUT/"mos_2021_2025_valdoise.geojson"
            size=0
            with target.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if not chunk:continue
                    size+=len(chunk)
                    if size>350*1024*1024:
                        target.unlink(missing_ok=True)
                        raise ValueError("Export supérieur à 350 Mo, interrompu")
                    f.write(chunk)
            report["export_file"]=target.name
            report["export_bytes"]=size
            report["mode"]="export"
except Exception as exc:
    report["statut"]="error"
    report["erreur"]=str(exc)
(OUT/"rapport_mos.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
if report["statut"]!="ok":raise SystemExit("MOS indisponible ou aucun enregistrement Val-d'Oise")
