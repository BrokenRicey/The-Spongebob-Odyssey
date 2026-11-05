// Route attachments are study assumptions, not inferred electrical connectivity.
const studyLayer = L.layerGroup().addTo(map);
let studyLoads = [], removedLoads = [], selectedRoute = null, selectedPoint = null;
let editingId = null, movingId = null, studyDirty = false;
const $ = id => document.getElementById(id);
const editor = document.createElement('aside');
editor.className = 'load-panel';
editor.innerHTML = `<div class="tag">PROJECT V3 · STUDY LOADS</div><h2>Attach loads to lines</h2>
<p id="route-hint">Click a colored power line to choose an attachment point.</p>
<div id="route-summary">No line selected</div>
<form id="load-form"><label>Load name<input id="load-name" maxlength="40" required placeholder="e.g. Data center 1"></label>
<div class="load-fields"><label>Demand (MW)<input id="load-mw" type="number" min="0" max="10000" step="any" value="30" required></label>
<label>Power factor<input id="load-pf" type="number" min="0.01" max="1" step="any" value="0.95" required></label></div>
<label>Onsite generation (MW)<input id="load-gen" type="number" min="0" max="10000" step="any" value="0" required></label>
<p id="load-net"></p><div class="load-actions"><button id="save-load" type="submit" disabled>Add load to this line</button><button id="cancel-load" type="button" hidden>Cancel</button></div></form>
<p id="load-status" role="status" aria-live="polite"></p><hr>
<div class="load-actions"><b id="load-total">0 attached loads</b><button id="undo-load" disabled>Undo remove</button></div>
<div id="study-list"></div><hr><div class="load-actions"><button id="export-study">Save study</button><button id="import-study">Open study</button></div>
<input id="study-file" type="file" accept=".json" hidden>
<p><small>Save study downloads a file with your loads and route attachments. Open it to continue later.</small></p>
<small>Assumed connections to GIS routes. These are not validated electrical taps; no route power-flow results are calculated.</small>`;
document.body.appendChild(editor);
L.DomEvent.disableClickPropagation(editor);L.DomEvent.disableScrollPropagation(editor);
function routeKey(f) { return String(f.properties.OBJECTID ?? f.properties.OBJECTID_1 ?? f.properties.ID); }
const routeFeatures = new Map(data.features.map(f => [routeKey(f), f]));
// Snap to the nearest segment in Leaflet's projected map coordinates.
function snapToRoute(feature, latlng) {
  const p=map.project(latlng, 14);let best=null, distance=Infinity;
  for (const part of feature.geometry.coordinates) for(let i=1;i<part.length;i++) {
    const a=map.project([part[i-1][1],part[i-1][0]],14), b=map.project([part[i][1],part[i][0]],14);
    const dx=b.x-a.x,dy=b.y-a.y,den=dx*dx+dy*dy;
    const t=den ? Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/den)):0;
    const q=L.point(a.x+t*dx,a.y+t*dy),d=p.distanceTo(q);
    if(d<distance){distance=d;best=map.unproject(q,14);}
  }
  if(!best)throw Error('This route has no usable segments.');
  return {lat:best.lat,lng:best.lng};
}
let selectedHighlight=null, pointHighlight=null;
function selectRoute(f,latlng) {
  selectedRoute=f;selectedPoint=snapToRoute(f,latlng);
  if(selectedHighlight)map.removeLayer(selectedHighlight);
  if(pointHighlight)map.removeLayer(pointHighlight);
  selectedHighlight=L.geoJSON(f,{interactive:false,style:{color:'#163747',weight:7,opacity:.55}}).addTo(map);
  pointHighlight=L.circleMarker(selectedPoint,{radius:7,color:'#173747',fillColor:'#fff',fillOpacity:1,interactive:false}).addTo(map);
  $('route-summary').textContent=`Line ${f.properties.ID} · ${f.properties.VOLTAGE>0?f.properties.VOLTAGE+' kV':f.properties.display_class+' kV'} · ${f.properties.OWNER || 'Owner unavailable'}`;
  $('route-hint').textContent=movingId?'New connection selected. Click Save changes to move the load.':'Attachment point snapped to the selected line.';
  $('save-load').disabled=false;
  if(!$('load-name').value)$('load-name').value=nextName();
  $('load-status').textContent='';editor.scrollTop=0;
}
function nextName(){let i=1;while(studyLoads.some(l=>l.name===`Load ${i}`))i++;return `Load ${i}`;}
function updateNet(){const p=Number($('load-mw').value),pf=Number($('load-pf').value),g=Number($('load-gen').value);$('load-net').textContent=pf>0&&pf<=1?`Net demand: ${(p-g).toFixed(1)} MW · ${(p*Math.tan(Math.acos(pf))).toFixed(1)} MVAr`:'';}
['load-mw','load-pf','load-gen'].forEach(id=>$(id).addEventListener('input',updateNet));updateNet();
function resetEditor(){editingId=movingId=null;$('route-hint').textContent='Click a colored line to choose an attachment point.';$('load-name').value='';$('load-mw').value=30;$('load-gen').value=0;$('load-pf').value=.95;$('save-load').textContent='Add load to this line';$('cancel-load').hidden=true;updateNet();}
$('cancel-load').onclick=()=>{resetEditor();$('route-hint').textContent='Click a colored line to choose an attachment point.';};
function editLoad(id,move=false){const l=studyLoads.find(x=>x.id===id);if(!l)return;editingId=id;movingId=move?id:null;if($('simulation-bus'))$('simulation-bus').value=l.simulation_bus||'';selectRoute(routeFeatures.get(l.route_key),l.point);$('load-name').value=l.name;$('load-mw').value=l.p_mw;$('load-pf').value=l.pf;$('load-gen').value=l.onsite_gen_mw;$('save-load').textContent='Save changes';$('cancel-load').hidden=false;$('route-hint').textContent=move?'Click another power line, then Save changes.':'Edit the values below, then Save changes.';updateNet();map.closePopup();editor.scrollTop=0;map.panTo(l.point);}
function removeLoad(id){const index=studyLoads.findIndex(l=>l.id===id);if(index<0)return;removedLoads.push({index,load:studyLoads.splice(index,1)[0]});studyDirty=true;if(editingId===id)resetEditor();renderLoads();$('load-status').textContent='Load removed. Undo remove restores it.';}
$('undo-load').onclick=()=>{const item=removedLoads.pop();if(!item)return;studyLoads.splice(item.index,0,item.load);studyDirty=true;renderLoads();$('load-status').textContent='Load restored.';};
$('load-form').onsubmit=e=>{e.preventDefault();if(!selectedRoute||!selectedPoint)return;
  if(!editingId&&studyLoads.length>=1000){$('load-status').textContent='This study supports up to 1,000 loads.';return;}
  const name=$('load-name').value.trim(),p=Number($('load-mw').value),pf=Number($('load-pf').value),g=Number($('load-gen').value);
  if(!name||studyLoads.some(l=>l.name===name&&l.id!==editingId)){$('load-status').textContent='Please use a unique load name.';return;}
  if(![p,pf,g].every(Number.isFinite)||p<0||p>10000||g<0||g>10000||pf<=0||pf>1)return;
  const row={id:editingId||crypto.randomUUID(),name,route_key:routeKey(selectedRoute),line_id:String(selectedRoute.properties.ID),point:{...selectedPoint},p_mw:p,pf,onsite_gen_mw:g,simulation_bus:$('simulation-bus')?.value||null,connection_status:'assumed GIS route attachment'};
  if(editingId)studyLoads[studyLoads.findIndex(l=>l.id===editingId)]=row;else studyLoads.push(row);
  studyDirty=true;resetEditor();renderLoads();$('load-status').textContent=`${name} saved on line ${row.line_id}. Save study to keep your work.`;
};
function renderLoads(){if($('mapped-result'))$('mapped-result').textContent='Run mapped loads to refresh simulation results after changes.';studyLayer.clearLayers();$('study-list').replaceChildren();$('undo-load').disabled=!removedLoads.length;
  const total=studyLoads.reduce((n,l)=>n+l.p_mw-l.onsite_gen_mw,0);$('load-total').textContent=`${studyLoads.length} loads · ${total.toFixed(1)} MW net`;
  for(const load of studyLoads){
    const marker=L.marker(load.point,{icon:L.divIcon({className:'study-load-icon',html:'⚡',iconSize:[28,28],iconAnchor:[14,14]})}).addTo(studyLayer);
    marker.bindTooltip(`${esc(load.name)} · ${load.p_mw} MW<br>Line ${esc(load.line_id)}`);marker.on('click',()=>editLoad(load.id));
    const card=document.createElement('div');card.className='load-card';
    const title=document.createElement('b');title.textContent=load.name;card.appendChild(title);
    const info=document.createElement('p');info.textContent=`Line ${load.line_id} · ${load.p_mw} MW · PF ${load.pf}`;card.appendChild(info);
    const actions=document.createElement('div');actions.className='load-actions';
    for(const [name,fn] of [['Edit',()=>editLoad(load.id)],['Move',()=>editLoad(load.id,true)],['Remove',()=>removeLoad(load.id)]]){const b=document.createElement('button');b.textContent=name;b.onclick=fn;actions.appendChild(b);}
    card.appendChild(actions);$('study-list').appendChild(card);
  }
}
$('export-study').onclick=()=>{const payload={format:'houston-route-loads',version:1,loads:studyLoads};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='Houston-load-study.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);studyDirty=false;$('load-status').textContent='Study downloaded. Keep the JSON file to reopen your loads.';};
$('import-study').onclick=()=>$('study-file').click();
function validateStudy(obj){
  if(obj.format!=='houston-route-loads'||obj.version!==1||!Array.isArray(obj.loads)||obj.loads.length>1000)throw Error('Unsupported study file.');
  const ids=new Set(),names=new Set();
  for(const l of obj.loads){
    if(typeof l.id!=='string'||!l.id||ids.has(l.id)||typeof l.name!=='string'||!l.name.trim()||l.name.length>60||names.has(l.name))throw Error('Invalid or duplicate load name / ID.');
    ids.add(l.id);names.add(l.name);
    if(![l.p_mw,l.pf,l.onsite_gen_mw].every(x=>typeof x==='number'&&Number.isFinite(x))||l.p_mw<0||l.p_mw>10000||l.pf<=0||l.pf>1||l.onsite_gen_mw<0||l.onsite_gen_mw>10000)throw Error('Invalid load demand or power factor.');
    const f=routeFeatures.get(l.route_key);if(!f)throw Error('An attached route does not exist in this map revision.');
    if(!l.point||![l.point.lat,l.point.lng].every(x=>typeof x==='number'&&Number.isFinite(x))||Math.abs(l.point.lat)>85||Math.abs(l.point.lng)>180)throw Error('Invalid attachment coordinates.');
    if(map.distance(l.point,snapToRoute(f,l.point))>2)throw Error('Attachment point is not on its stored route.');
    l.line_id=String(f.properties.ID);
  }return obj.loads;
}
$('study-file').onchange=async()=>{const file=$('study-file').files[0];if(!file)return;try{
  if(file.size>2000000)throw Error('Study file exceeds 2 MB.');
  const loads=validateStudy(JSON.parse(await file.text()));
  if(studyDirty&&!confirm('Replace your unsaved study loads with this file?'))return;
  studyLoads=loads;removedLoads=[];studyDirty=false;resetEditor();renderLoads();$('load-status').textContent=`Opened ${loads.length} loads.`;
}catch(e){$('load-status').textContent=e.message;}finally{$('study-file').value='';}};
window.addEventListener('beforeunload',e=>{if(studyDirty){e.preventDefault();e.returnValue='';}});
renderLoads();
