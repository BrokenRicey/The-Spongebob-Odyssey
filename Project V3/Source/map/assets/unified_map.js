// One map shared by native study controls and result tables.
let nativeBridge=null, selectedRoute=null, selectedPoint=null, routeHighlight=null;
let latestState=null, focusedKey=null;
map.options.zoomSnap=.25;map.fitBounds(bounds);
const resultLayer=L.layerGroup().addTo(map);
const routeGroups=[];
map.eachLayer(layer=>{if(layer instanceof L.GeoJSON)routeGroups.push(layer);});
const routeFeatures=new Map(data.features.map(f=>[String(f.properties.OBJECTID??f.properties.OBJECTID_1??f.properties.ID),f]));
const panel=document.querySelector('.panel');
panel.style.display='none';
const tools=L.control({position:'topright'});
tools.onAdd=()=>{const box=L.DomUtil.create('div','map-tools');
  box.innerHTML='<button id="map-options">Map layers</button><label><input type="checkbox" id="bus-overlay" checked> Simulation buses</label><span id="map-case">No results yet</span>';
  L.DomEvent.disableClickPropagation(box);L.DomEvent.disableScrollPropagation(box);
  box.querySelector('button').onclick=()=>{panel.style.display=panel.style.display==='none'?'block':'none';};
  box.querySelector('input').onchange=()=>{if(latestState)window.renderStudy(latestState);};return box;};tools.addTo(map);
const note=L.control({position:'bottomleft'});
note.onAdd=()=>{const box=L.DomUtil.create('div','map-note');box.textContent='Colored routes: GIS geography · Circular buses: calculated on assumed network';return box;};note.addTo(map);
function routeKey(f){return String(f.properties.OBJECTID??f.properties.OBJECTID_1??f.properties.ID);}
function snapToRoute(feature,latlng){const p=map.project(latlng,14);let best=null,distance=Infinity;
  for(const part of feature.geometry.coordinates)for(let i=1;i<part.length;i++){
    const a=map.project([part[i-1][1],part[i-1][0]],14),b=map.project([part[i][1],part[i][0]],14);
    const dx=b.x-a.x,dy=b.y-a.y,den=dx*dx+dy*dy;
    const t=den?Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/den)):0;
    const q=L.point(a.x+t*dx,a.y+t*dy),d=p.distanceTo(q);
    if(d<distance){distance=d;best=map.unproject(q,14);}
  }if(!best)throw Error('Route has no usable geometry');return {lat:best.lat,lng:best.lng};}
function selectRoute(f,point){selectedRoute=f;selectedPoint=snapToRoute(f,point);
  if(routeHighlight)map.removeLayer(routeHighlight);
  routeHighlight=L.geoJSON(f,{interactive:false,style:{color:'#132f46',weight:6,opacity:.65}}).addTo(map);
  if(nativeBridge)nativeBridge.routePicked(JSON.stringify({route_key:routeKey(f),line_id:String(f.properties.ID),point:selectedPoint}));
}
function numeric(value,digits=3){return value===null||value===undefined?'—':Number(value).toFixed(digits);}
function pick(section,id){if(nativeBridge)nativeBridge.componentPicked(section,id);}
window.renderStudy=state=>{
  latestState=state;resultLayer.clearLayers();
  const model=state.model;if(!model)return;
  const result=state.result?.converged?state.result:null,base=state.baseline?.converged?state.baseline:null;
  const buses=new Map(model.buses.map(b=>[b.id,b]));
  const selected=state.active||[],focusId=selected.join(':');let target=null;
  document.getElementById('map-case').textContent=state.mode+' · '+(result?'solved':state.result?'calculation failed':'not run');
  for(const group of routeGroups){if(state.show_gis)group.addTo(map);else map.removeLayer(group);}
  if(state.show_directory)dcLayer.addTo(map);else map.removeLayer(dcLayer);
  const violations=new Set((result?.violations||[]).map(v=>v.type+':'+v.id));
  for(const b of model.buses){const r=result?.buses?.[b.id],v=r?.vm_pu;
    const active=selected[0]==='buses'&&selected[1]===b.id;
    const bad=result&&(v==null||v<.95||v>1.05);
    if(document.getElementById('bus-overlay').checked||active){
      const marker=L.circleMarker([b.lat,b.lon],{radius:active?9:5,color:active?'#001a2b':'white',weight:active?3:1.5,fillColor:bad?'#d12e40':result?'#008f8a':'#146fa8',fillOpacity:.95}).addTo(resultLayer);
      let tip='<b>'+esc(b.id)+'</b> · assumed '+b.vn_kv+' kV bus<br>'+state.mode+' voltage: '+numeric(v)+' pu';
      if(state.mode==='Change'&&v!=null&&base?.buses?.[b.id]?.vm_pu!=null)tip+='<br>Δ voltage: '+numeric(v-base.buses[b.id].vm_pu,4)+' pu';
      marker.bindTooltip(tip);marker.on('click',()=>pick('buses',b.id));
    }if(active)target=[b.lat,b.lon];
  }
  model.loads.forEach((load,index)=>{
    const b=buses.get(load.bus_id);if(!b)return;
    const active=selected[0]==='loads'&&selected[1]===load.id;
    const point=load.route_point||{lat:b.lat-.009-(index%3)*.002,lng:b.lon+.009};
    const row=result?.loads?.[load.id],disconnected=row?.in_service===false;
    const bad=violations.has('bus:'+load.bus_id);
    const marker=L.marker(point,{icon:L.divIcon({className:'native-load '+(active?'active ':'')+(disconnected?'disconnected':bad?'violation':''),html:'⚡',iconSize:[26,26],iconAnchor:[13,13]})}).addTo(resultLayer);
    let tip='<b>'+esc(load.id)+'</b><br>Assumed bus: '+esc(load.bus_id)+'<br>'+(load.line_id?'GIS route: '+esc(load.line_id):'Positioned beside assumed bus; no GIS attachment');
    tip+='<br>'+state.mode+' net MW: '+numeric(row?.net_grid_mw,1)+'<br>Bus voltage: '+numeric(result?.buses?.[load.bus_id]?.vm_pu)+' pu';
    if(disconnected)tip+='<br>Disconnected in this case';
    marker.bindTooltip(tip);marker.on('click',()=>pick('loads',load.id));
    if(active){target=point;L.polyline([point,[b.lat,b.lon]],{color:'#173747',weight:1,dashArray:'3 6',interactive:false}).addTo(resultLayer);}
  });
  // Selected modeled equipment is dashed to distinguish it from GIS routes.
  if(['lines','transformers'].includes(selected[0])){
    const branch=model[selected[0]].find(l=>l.id===selected[1]);
    if(branch){const a=buses.get(branch.from_bus||branch.hv_bus),b=buses.get(branch.to_bus||branch.lv_bus);
      const r=result?.[selected[0]]?.[branch.id];
      if(a&&b){const line=L.polyline([[a.lat,a.lon],[b.lat,b.lon]],{color:r?.in_service===false?'#64748b':r?.loading_percent>100?'#d12e40':'#103c68',weight:5,dashArray:'8 6'}).addTo(resultLayer);
        line.bindTooltip('Modeled '+esc(branch.id)+' · assumed connectivity<br>Loading: '+numeric(r?.loading_percent,1)+'%');line.on('click',()=>pick(selected[0],branch.id));target=[(a.lat+b.lat)/2,(a.lon+b.lon)/2];}
    }
  }
  if(selected[0]==='directory'){
    const f=state.directory?.[Number(selected[1])];const marker=f&&dcMarkers.get(f.properties.id);
    if(marker){target=marker.getLatLng();marker.openPopup();}
  }
  if(target&&focusedKey!==focusId){if(!map.getBounds().pad(-.1).contains(target))map.panTo(target);focusedKey=focusId;}
};
new QWebChannel(qt.webChannelTransport,channel=>{nativeBridge=channel.objects.studyFiles;window.nativeFilesReady=true;nativeBridge.ready();});
