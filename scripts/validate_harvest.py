"""Contrôle des artefacts de collecte pour distinguer santé API et données réellement collectées."""
import json,pathlib,datetime
root=pathlib.Path("outputs")
sources=[
("communes",root/"connecteurs"/"communes_population.json","features",183),
("hydrometrie",root/"connecteurs"/"hubeau_stations.json","data",1),
("catalogue",root/"connecteurs"/"datagouv_catalogue.json","jeux_de_donnees",1)
]
checks=[]
for name,path,key,minimum in sources:
    item={"source":name,"fichier":str(path),"minimum":minimum}
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        n=len(data.get(key,[]))
        item.update({"nombre":n,"statut":"ok" if n>=minimum else "insuffisant"})
    except Exception as exc:
        item.update({"statut":"manquant","erreur":str(exc)})
    checks.append(item)
report={"date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"checks":checks,"note":"Contrôle de présence et de volumes, non preuve d'exhaustivité ou de fraîcheur des données sources"}
path=root/"controle_moissonnage.json"
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
if any(x["statut"]!="ok" for x in checks):
    raise SystemExit("Collecte incomplète : consulter controle_moissonnage.json")
