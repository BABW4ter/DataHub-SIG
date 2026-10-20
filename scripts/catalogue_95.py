"""Inventaire prioritaire data.gouv.fr pour le Val-d'Oise.
Catalogue et métadonnées seulement; ne prétend pas que toutes les ressources sont téléchargeables.
"""
import csv,json,os,pathlib,requests
from urllib.parse import urlparse
D=os.getenv("DEP","95")
if D!="95": raise SystemExit("Ce workflow ciblé est limité au Val-d'Oise (95).")
OUT=pathlib.Path("outputs/catalogue_95");OUT.mkdir(parents=True,exist_ok=True)
API="https://www.data.gouv.fr/api/1/datasets/"
S=requests.Session();S.headers["User-Agent"]="DataHubSIG/0.4 (+https://github.com/BABW4ter/DataHub-SIG)"
queries=[
("DDT95","",{"organization":"direction-departementale-des-territoires-du-val-doise"}),
("95 explicite","Val-d'Oise",{}),
("95 explicite","Val d'Oise",{}),
("95 explicite","DDT 95",{}),
("95 explicite","département 95",{}),
("IDF pertinente","Île-de-France zones humides",{}),
("IDF pertinente","MOS Île-de-France",{}),
("IDF pertinente","équipements sportifs Val-d'Oise",{})
]
items={};errors=[]
for tier,q,extra in queries:
    try:
        for page in range(1,11):
            params={"page":page,"page_size":100,**extra}
            if q:params["q"]=q
            r=S.get(API,params=params,timeout=60);r.raise_for_status()
            payload=r.json()
            rows=payload.get("data",[])
            for d in rows:
                id=d.get("id")
                if not id:continue
                existing=items.get(id)
                tiers={"DDT95":1,"95 explicite":2,"IDF pertinente":3}
                priority=tiers[tier]
                if existing and existing["priorite"]<=priority:continue
                resources=d.get("resources") or []
                items[id]={"id":id,"titre":d.get("title"),"priorite":priority,"categorie":tier,"url":d.get("page"),"date_maj":d.get("last_update"),"licence":d.get("license"),"organisation":(d.get("organization") or {}).get("name"),"spatial":d.get("spatial"),"ressources":[{"titre":z.get("title"),"format":z.get("format"),"url":z.get("url")} for z in resources]}
            if len(rows)<100 or page>=payload.get("total",0)//100+1:break
    except Exception as exc:errors.append({"categorie":tier,"requete":q,"erreur":str(exc)})
sorted_items=sorted(items.values(),key=lambda x:(x["priorite"],(x["titre"] or "").lower()))
(OUT/"inventaire.json").write_text(json.dumps({"departement":D,"total":len(sorted_items),"jeux_de_donnees":sorted_items,"erreurs":errors,"avertissement":"La correspondance géographique des résultats textuels doit être vérifiée avant collecte."},ensure_ascii=False,indent=2),encoding="utf-8")
with (OUT/"inventaire.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.writer(f,delimiter=";");w.writerow(["priorite","categorie","titre","organisation","date_maj","licence","url","nb_ressources"])
    for x in sorted_items:w.writerow([x["priorite"],x["categorie"],x["titre"],x["organisation"],x["date_maj"],x["licence"],x["url"],len(x["ressources"])])
print("Jeux identifiés:",len(sorted_items),"Erreurs:",errors)
if not sorted_items:raise SystemExit("Aucun résultat; consulter inventaire.json")
