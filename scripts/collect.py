import csv, json, os, pathlib, re, time
import requests

dep = os.getenv("DEP", "95").strip()
if not re.fullmatch(r"(?:0[1-9]|[1-8][0-9]|9[0-5]|97[1-6]|2A|2B)", dep):
    raise SystemExit("Code département invalide")
out = pathlib.Path("outputs")
out.mkdir(exist_ok=True)
session = requests.Session()
session.headers["User-Agent"] = "DataHubSIG/0.1 (collecte publique GitHub)"
report = {"departement": dep, "sources": [], "erreurs": []}

def get_json(url, **kwargs):
    r = session.get(url, timeout=90, **kwargs)
    r.raise_for_status()
    return r.json()

if os.getenv("POP", "true").lower() == "true":
  try:
    communes = get_json("https://geo.api.gouv.fr/departements/" + dep + "/communes", params={"fields": "nom,code,population,centre,contour", "format": "geojson", "geometry": "contour"})
    (out / "communes_population.geojson").write_text(json.dumps(communes, ensure_ascii=False), encoding="utf-8")
    with (out / "population_communes.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["code_insee", "commune", "population"])
        for feature in communes.get("features", []):
            p = feature.get("properties", {})
            w.writerow([p.get("code"), p.get("nom"), p.get("population")])
    report["sources"].append({"source": "geo.api.gouv.fr", "statut": "ok", "limite": "Population fournie par l'API, millésime à vérifier avant analyse"})
  except Exception as exc:
    report["erreurs"].append("Communes : " + str(exc))

# Overpass : requêtes par aire administrative départementale, sorties ponctuelles et linéaires.
if os.getenv("ARBRES", "true").lower() == "true" or os.getenv("VERTS", "true").lower() == "true":
    clauses = []
    if os.getenv("ARBRES", "true").lower() == "true":
        clauses += ['node["natural"="tree"](area.a);', 'way["natural"="tree_row"](area.a);']
    if os.getenv("VERTS", "true").lower() == "true":
        clauses += ['way["leisure"~"^(park|garden)$"](area.a);', 'relation["leisure"~"^(park|garden)$"](area.a);', 'way["landuse"="grass"](area.a);']
    query = '[out:json][timeout:180];area["boundary"="administrative"]["admin_level"="6"]["ref:INSEE"="' + dep + '"]->.a;(' + ''.join(clauses) + ');out geom;'
    try:
        r = session.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=240)
        r.raise_for_status()
        data = r.json()
        (out / "osm_brut.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        features = []
        for item in data.get("elements", []):
            tags = item.get("tags", {})
            geom = None
            if item["type"] == "node" and "lat" in item:
                geom = {"type": "Point", "coordinates": [item["lon"], item["lat"]]}
            elif item["type"] == "way" and item.get("geometry"):
                coords = [[p["lon"], p["lat"]] for p in item["geometry"]]
                closed = len(coords) > 3 and coords[0] == coords[-1]
                geom = {"type": "Polygon", "coordinates": [coords]} if closed and tags.get("leisure") in ("park", "garden") or (closed and tags.get("landuse") == "grass") else {"type": "LineString", "coordinates": coords}
            if geom:
                features.append({"type": "Feature", "geometry": geom, "properties": {"osm_id": str(item["id"]), "osm_type": item["type"], **tags}})
        (out / "osm_vegetation.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
        report["sources"].append({"source": "OpenStreetMap/Overpass", "statut": "ok", "objets": len(features), "limite": "Relations complexes conservées dans osm_brut.json; couverture OSM non exhaustive"})
    except Exception as exc:
        report["erreurs"].append("Overpass : " + str(exc))
(out / "rapport.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
if report["erreurs"]:
    print("AVERTISSEMENT : collecte partielle, consulter outputs/rapport.json")
if not report["sources"]:
    raise SystemExit("Aucune source collectée : consulter outputs/rapport.json")
