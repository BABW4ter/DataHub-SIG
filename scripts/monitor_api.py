"""DataHub SIG - health checks des sources. Pas de fausse affirmation de collecte.
Codes: ok, degraded, unavailable, reference_only.
"""
import concurrent.futures,datetime,json,pathlib,time
import requests

ROOT=pathlib.Path("outputs/monitoring");ROOT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers.update({"User-Agent":"DataHubSIG-monitor/1.0 (https://github.com/BABW4ter/DataHub-SIG)","Accept":"application/json, */*"})
CHECKS=[
("API Geo","https://geo.api.gouv.fr/departements/95/communes?fields=nom,code&format=json","json","communes"),
("Overpass OSM","https://overpass-api.de/api/status","text","service"),
("data.gouv.fr","https://www.data.gouv.fr/api/1/datasets/?q=Val-d%27Oise&page_size=1","json","datasets"),
("Hub'Eau","https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/stations?code_departement=95&size=1","json","stations"),
("Géorisques","https://georisques.gouv.fr/api/v1/gaspar/risques?code_insee=95018","json","risques"),
("BRGM InfoTerre","https://infoterre.brgm.fr/","text","portail"),
("IGN Géoservices","https://geoservices.ign.fr/","text","portail"),
("IGN Géoplateforme WFS","https://data.geopf.fr/wfs/ows?service=WFS&request=GetCapabilities&version=2.0.0","text","service"),
("INSEE","https://www.insee.fr/fr/information/2862759","text","documentation"),
("INPN OpenObs","https://openobs.mnhn.fr/","text","portail"),
("Sandre","https://www.sandre.eaufrance.fr/","text","portail"),
("BNPE","https://bnpe.eaufrance.fr/","text","portail"),
("Géoportail urbanisme","https://www.geoportail-urbanisme.gouv.fr/","text","portail"),
("Cadastre Etalab","https://cadastre.data.gouv.fr/","text","portail"),
("DVF data.gouv","https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/","text","portail"),
("transport.data.gouv","https://transport.data.gouv.fr/","text","portail"),
("Éducation nationale","https://data.education.gouv.fr/","text","portail"),
("MOS Institut Paris Region","https://data.iledefrance.fr/","text","portail"),
("API Sirene INSEE","https://api.insee.fr/api-sirene/3.11/siren?q=siren%3A000000000","text","auth"),
("API Mélodi INSEE","https://api.insee.fr/melodi/","text","auth"),
("Géoportail administration","https://lannuaire.service-public.fr/","text","portail")
]
def test(entry):
    name,url,fmt,level=entry
    start=time.monotonic()
    result={"source":name,"url":url,"verification":level,"status":"unavailable","http":None,"duration_s":None,"detail":""}
    try:
        urls = ["https://overpass.kumi.systems/api/status","https://overpass.nchc.org.tw/api/status"] if name=="Overpass OSM" else []
        attempts=[url]+urls
        last_error=None
        for candidate in attempts:
            try:
                r=requests.get(candidate,headers={"User-Agent":"DataHubSIG-monitor/1.1"},timeout=12,allow_redirects=True)
                result["url_testee"]=candidate
                if r.status_code in (401,403) and level=="auth":
                    result["http"]=r.status_code
                    result["status"]="auth_required"
                    result["detail"]="Service joint mais accès authentifié ou refusé; pas une preuve de collecte"
                    return result
                r.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error=exc
        else:
            raise last_error
        result["http"]=r.status_code
        result["duration_s"]=round(time.monotonic()-start,2)
        if fmt=="json":
            data=r.json()
            if level=="communes":
                count=len(data) if isinstance(data,list) else len(data.get("features",[]))
                result["count"]=count
                result["status"]="ok" if count==183 else "degraded"
                result["detail"]="183 communes attendues"
            elif level=="datasets":
                count=len(data.get("data",[]));result["count"]=count
                result["status"]="ok" if count else "degraded"
            elif level=="stations":
                count=len(data.get("data",[]));result["count"]=count
                result["status"]="ok" if count else "degraded"
            else:
                result["status"]="ok";result["detail"]="Réponse JSON, pertinence territoriale non validée"
        else:
            result["status"]="reference_only" if level in ("portail","documentation") else "ok"
            result["detail"]="Page ou service accessible; connecteur de collecte non vérifié"
    except Exception as e:
        result["duration_s"]=round(time.monotonic()-start,2)
        result["detail"]=str(e)[:300]
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    results=list(pool.map(test,CHECKS))
summary={k:sum(x["status"]==k for x in results) for k in ["ok","degraded","reference_only","auth_required","unavailable"]}
payload={"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"scope":"Val-d'Oise 95","note":"Disponibilité technique, pas preuve de moissonnage exhaustif. Certains tests ne portent que sur le portail.","summary":summary,"checks":results}
(ROOT/"etat_api.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
(ROOT/"etat_api.md").write_text("# Santé des sources DataHub SIG\n\n"+"Contrôle UTC : "+payload["date_utc"]+"\n\n"+"| Source | Statut | HTTP | Niveau | Détail |\n|---|---|---|---|---|\n"+"\n".join("| "+str(x["source"])+" | "+x["status"]+" | "+str(x["http"])+" | "+x["verification"]+" | "+str(x["detail"]).replace("|","/")+" |" for x in results)+"\n",encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False))
# Les services publics peuvent avoir des pannes temporaires; conserver le rapport et ne pas faire échouer la surveillance.
