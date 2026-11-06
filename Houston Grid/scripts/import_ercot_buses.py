"""Best-effort ERCOT bus-name to OSM-substation matching. No synthetic coordinates.
Run python scripts/import_ercot_buses.py, then python houston_grid.py.
Rules are reviewed candidate aliases, not verified ERCOT station assignments.
"""
import csv,json,re,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data'/'source'
DATA=ROOT/'data'/'processed'
DATA.mkdir(parents=True,exist_ok=True)
# Match anchored bus prefixes only; hub membership never assigns a location.
RULES=[(r'^ADICKS_|^ADK_', 'Addicks Substation'),(r'^BELAIR_', 'Bellaire Substation'),
(r'^HARDY$', 'Hardy Substation'),(r'^JENETA_|^JN_', 'Jeanetta Substation'),
(r'^OBRIEN_|^OBRIN_|^OB_', "O'Brien Substation"),(r'^KING_|^KG_', 'King Substation'),
(r'^WHITOK_|^WO_', 'White Oak Substation'),(r'^ZEN_', 'Zenith Substation'),
(r'^KARSTN_', 'Karsten Substation'),(r'^OASIS_', 'Oasis Substation'),
(r'^CBY_|^CBY4_', 'Cedar Bayou Plant Substation'),
(r'^GRNBYU_|^GBY_', 'Greens Bayou 345kV Substation'),
(r'^T_H_W|^THW_', 'T. H. Wharton Substation'),
(r'^P_H_R|^PHR_', 'P. H. Robinson Switching Station'),
(r'^WAP_', 'W. A. Parish Station (345 kV)'),(r'^NB_', 'North Belt Substation')]
SERVICE='https://services1.arcgis.com/lDFzr3JyGEn5Eymu/arcgis/rest/services/Open_Infrastructure_Map_Substations_Polygon/FeatureServer/40'
def centroid(ring):
 area=sx=sy=0
 for (x,y),(xx,yy)in zip(ring,ring[1:]+ring[:1]):
  cross=x*yy-xx*y;area+=cross;sx+=(x+xx)*cross;sy+=(y+yy)*cross
 if abs(area)<1e-12:return sum(x[0]for x in ring)/len(ring),sum(x[1]for x in ring)/len(ring)
 return sx/(3*area),sy/(3*area)
def build():
 features=json.loads((SOURCE/'substation_reference.json').read_text())['features'];stations={}
 for f in features:
  a=f['attributes'];name=(a.get('name')or'').strip()
  if not name:continue
  ring=max(f['geometry']['rings'],key=len);lon,lat=centroid(ring)
  if not(-95.85<=lon<=-94.85 and 29.45<=lat<=30.08):continue
  stations[name]={'name':name,'latitude':lat,'longitude':lon,'osm_id':a.get('id'),'voltages':a.get('voltages'),'operator':a.get('operator'),'source':SERVICE,'source_object_id':a['OBJECTID']}
 hubs={r['ELECTRICAL_BUS']:r for r in csv.DictReader((SOURCE/'Electrical_BusMap_To_HUB_10212026_170159.csv').open(encoding='utf-8-sig'))}
 rows=list(csv.DictReader((SOURCE/'Full_Electrical_Bus_10212026_170159.csv').open(encoding='utf-8-sig')));matched=[];unmatched=[]
 for row in rows:
  name=row['ELECTRICAL_BUS'];hub=hubs.get(name,{});hits=[(pattern,station)for pattern,station in RULES if re.search(pattern,name)]
  if len(hits)!=1 or hits[0][1]not in stations:
   unmatched.append({'bus_name':name,'reason':'No unique candidate within the Houston reference coverage'});continue
  pattern,station_name=hits[0];station=stations[station_name]
  kv=float(hub['ELECTRICAL_BUS_KV'])if hub else None;kv_source='ERCOT hub mapping file'if hub else 'Unknown'
  if kv is None:
   m=re.search(r'(?:^|_)(345|138|069|69)(?=[A-Z_]|$)',name)
   if m:kv=float(m[1]);kv_source='Inferred from bus name; not independently verified'
  # Separate mapped voltage yards where reference explicitly distinguishes them.
  if station_name=='Greens Bayou 345kV Substation'and kv==69:station=stations.get('Greens Bayou 69kV Substation',station)
  if station_name=='W. A. Parish Station (345 kV)'and kv==138:station=stations.get('W. A. Parish Station (138 kV)',station)
  matched.append(dict(bus_name=name,station_name=station['name'],latitude=station['latitude'],longitude=station['longitude'],nominal_kv=kv,voltage_source=kv_source,hub=hub.get('HUB',''),hub_bus_name=hub.get('HUB_BUS_NAME',''),match_rule=pattern,location_status='Inferred substation-level location',location_note='Bus name/code matched to a mapped substation; exact busbar and ERCOT station assignment unverified.',coordinate_source=station['source'],source_object_id=station['source_object_id'],osm_id=station['osm_id']))
 data={'dataset':'ERCOT bus-name location candidates','synthetic':False,'source_bus_file':'Full_Electrical_Bus_10212026_170159.csv','source_date_from_filename':'2026-10-21','coordinate_reference':'OSM-derived ArcGIS polygon snapshot; snapshot currency not established; retrieved 2026-11-06 UTC','total_bus_names':len(rows),'buses':matched,'unmatched_count':len(unmatched),'reference_stations':list(stations.values()),'note':'All bus-to-substation assignments are inferred candidates, not verified topology. Houston reference coverage only. No geographic positions fabricated for unmatched records.'}
 (DATA/'ercot_buses.json').write_text(json.dumps(data,indent=2))
 for filename,records in [('ercot_bus_location_candidates.csv',matched),('ercot_bus_unmatched.csv',unmatched)]:
  with(DATA/filename).open('w',newline='')as f:
   writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
 summary={'total_bus_names':len(rows),'placed_candidates':len(matched),'candidate_stations':len({b['station_name']for b in matched}),'unmatched':len(unmatched),'hub_houston_placed':sum(b['hub']=='HB_HOUSTON'for b in matched),'all_locations_inferred':True}
 (DATA/'ercot_bus_import_results.json').write_text(json.dumps(summary,indent=2));print(summary)
if __name__=='__main__':build()
