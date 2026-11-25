'use strict';

(() => {
  const $ = id => document.getElementById(id);
  const text = (tag, value, className = '') => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = (value, digits = 2) => value === null || value === undefined || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString(undefined, {maximumFractionDigits:digits, minimumFractionDigits:digits});
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const plural = {buses:'Bus',lines:'Transmission line',transformers:'Transformer',loads:'Data center',sources:'Supply point'};
  const palette = {line:'#13828e', off:'#8b9ca7', selected:'#183e52', danger:'#c64758', warning:'#c58b32', down:'#208ab0', source:'#7869b4', neutral:'#426f80'};
  const map = L.map('map', {zoomControl:false, preferCanvas:true, minZoom:7, maxZoom:19, zoomSnap:.25}).setView([29.79,-95.35],10);
  window.editorMap = map;
  L.control.zoom({position:'bottomright'}).addTo(map);
  map.attributionControl.setPrefix(false);
  const tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors', opacity:.63});
  tileLayer.on('tileerror', () => { $('tile-note').hidden = !$('streets').checked; });
  tileLayer.on('tileload', () => { $('tile-note').hidden = true; });
  tileLayer.addTo(map);
  const gridLayer = L.layerGroup().addTo(map);
  const handlesLayer = L.layerGroup().addTo(map);
  let bridge = null;
  let state = null;
  let selected = null;
  let tool = 'select';
  let lineStart = null;
  let hasFitted = false;
  let dialogAction = null;
  let modelLookup = {buses:new Map()};
  const local = {color:'loading'};

  function send(type, values = {}) {
    if (!bridge) { setStatus('The local engine is still connecting.'); return; }
    if (state?.busy && !['select','save','export'].includes(type)) return;
    bridge.action(JSON.stringify({type, ...values}));
  }
  function setStatus(message) { $('status-message').textContent = message; }
  function currentResult() { return state?.result?.converged ? state.result : null; }
  function comparisonReady() { return Boolean(state?.comparison_ready && state.baseline?.converged && state.scenario?.converged); }
  function getBus(id) { return modelLookup.buses.get(id); }
  function coordinates(row) {
    if (finite(row?.lat) && finite(row?.lon)) return [row.lat, row.lon];
    const bus = getBus(row?.bus_id);
    return bus ? [bus.lat, bus.lon] : null;
  }
  function linePoints(row, section = 'lines') {
    const a = getBus(row.from_bus ?? row.hv_bus), b = getBus(row.to_bus ?? row.lv_bus);
    if (!a || !b) return [];
    const points = section === 'lines' && Array.isArray(row.points) && row.points.length > 1 ? row.points.map(p => [p[0],p[1]]) : [[a.lat,a.lon],[b.lat,b.lon]];
    points[0] = [a.lat,a.lon]; points[points.length-1] = [b.lat,b.lon];
    return points;
  }
  function isSelected(section,id) { return selected?.section === section && selected?.id === id; }
  function pick(section,id) {
    if (state?.busy) return;
    if (tool === 'line' && section === 'buses') {
      if (!lineStart) {
        lineStart = id;
        updateToolHint();
        renderMap();
      } else if (lineStart !== id) {
        send('add_line', {from_bus:lineStart,to_bus:id});
        setTool('select');
      }
      return;
    }
    selected = {section,id};
    renderInspector();
    renderMap();
    send('select', {section,id});
  }
  function branchColor(row, section) {
    if (row.in_service === false) return palette.off;
    const result = currentResult()?.[section]?.[row.id];
    if (local.color === 'inputs' || !result) return palette.line;
    if (local.color === 'change' && comparisonReady()) {
      const base = state.baseline?.[section]?.[row.id]?.loading_percent;
      const scenario = state.scenario?.[section]?.[row.id]?.loading_percent;
      if (base == null || scenario == null) return palette.neutral;
      return scenario - base > .05 ? palette.warning : scenario - base < -.05 ? palette.down : palette.line;
    }
    const loading = result.loading_percent;
    if (loading > 100) return palette.danger;
    if (loading > 75) return palette.warning;
    return palette.line;
  }
  function busColor(bus) {
    if (bus.in_service === false) return palette.off;
    const result = currentResult()?.buses?.[bus.id];
    if (!result || local.color === 'inputs') return palette.neutral;
    if (!result.supplied || result.vm_pu == null) return palette.danger;
    if (result.vm_pu < .95 || result.vm_pu > 1.05) return palette.danger;
    if (local.color === 'change' && comparisonReady()) {
      const base = state.baseline?.buses?.[bus.id]?.vm_pu, scenario = state.scenario?.buses?.[bus.id]?.vm_pu;
      if (base != null && scenario != null && Math.abs(scenario-base) > .001) return scenario < base ? palette.warning : palette.down;
    }
    return palette.line;
  }
  function branchTooltip(row, section) {
    const result = currentResult()?.[section]?.[row.id];
    let content = '<strong>'+esc(row.id)+'</strong><br>'+esc(row.from_bus ?? row.hv_bus)+' → '+esc(row.to_bus ?? row.lv_bus);
    content += '<br>'+(row.in_service === false ? 'Disabled' : result?.loading_percent != null ? 'Loading '+number(result.loading_percent,1)+'%' : 'In service · not calculated');
    if (row.length_km != null) content += ' · '+number(row.length_km,2)+' km';
    if (row.name) content += '<br><small>'+esc(row.name)+'</small>';
    return content;
  }
  function renderMap() {
    gridLayer.clearLayers(); handlesLayer.clearLayers();
    if (!state?.model) return;
    const model = state.model, result = currentResult();
    for (const section of ['lines','transformers']) for (const row of model[section] || []) {
      const points = linePoints(row,section); if (points.length < 2) continue;
      const active = isSelected(section,row.id), disabled = row.in_service === false;
      const color = branchColor(row,section);
      if (active) L.polyline(points,{color:'#ffffff',weight:8,opacity:.97,interactive:false}).addTo(gridLayer);
      const visible = L.polyline(points,{color:active ? palette.selected : color,weight:active ? 4 : section === 'transformers' ? 2.8 : 2.1,opacity:disabled ? .65 : .9,dashArray:disabled?'6 6':section==='transformers'?'3 5':null,interactive:false}).addTo(gridLayer);
      const hit = L.polyline(points,{color,weight:14,opacity:0,interactive:true}).addTo(gridLayer);
      hit.bindTooltip(branchTooltip(row,section),{sticky:true});
      hit.on('click', event => { L.DomEvent.stopPropagation(event); pick(section,row.id); });
      if (active && tool === 'move' && section === 'lines' && !state.busy) addLineHandles(row,points);
    }
    const showBuses = $('show-buses').checked || tool === 'line' || tool === 'move';
    for (const bus of model.buses || []) {
      const active = isSelected('buses',bus.id), starting = lineStart === bus.id;
      if (!showBuses && !active && !starting) continue;
      let marker;
      if (active && tool === 'move' && !state.busy) {
        marker = L.marker([bus.lat,bus.lon],{draggable:true,icon:L.divIcon({className:'bus-drag',iconSize:[17,17],iconAnchor:[8,8]})}).addTo(gridLayer);
        marker.on('dragend', () => {const p=marker.getLatLng();send('move',{section:'buses',id:bus.id,lat:p.lat,lon:p.lng});});
      } else {
        marker = L.circleMarker([bus.lat,bus.lon],{radius:active||starting?6:map.getZoom()>12?3.5:2.8,fillColor:busColor(bus),fillOpacity:.98,color:active||starting?palette.selected:'#ffffff',weight:active||starting?2.5:1}).addTo(gridLayer);
      }
      const row = result?.buses?.[bus.id];
      marker.bindTooltip('<strong>'+esc(bus.id)+'</strong> · '+number(bus.vn_kv,0)+' kV<br>'+(bus.in_service===false?'Disabled':row?.supplied===false?'Unsupplied':row?'Voltage '+number(row.vm_pu,3)+' pu':'Not calculated'));
      marker.on('click',event=>{L.DomEvent.stopPropagation(event);pick('buses',bus.id);});
    }
    for (const load of model.loads || []) {
      const p=coordinates(load); if (!p) continue;
      const bus=getBus(load.bus_id), active=isSelected('loads',load.id), row=result?.loads?.[load.id];
      if (bus) L.polyline([p,[bus.lat,bus.lon]],{color:active?palette.selected:'#aa8b50',weight:active?1.7:1,opacity:active ? .9 : .55,dashArray:'3 5',interactive:false}).addTo(gridLayer);
      const classes='load-marker'+(active?' selected':'')+(load.in_service===false?' disabled':row?.supplied===false?' unsupplied':'');
      const marker=L.marker(p,{draggable:tool==='move'&&!state.busy,icon:L.divIcon({className:classes,html:'▥',iconSize:[25,25],iconAnchor:[12,12]}),zIndexOffset:100}).addTo(gridLayer);
      marker.bindTooltip('<strong>'+esc(load.id)+'</strong><br>'+number(load.p_mw,1)+' MW · '+esc(load.bus_id)+(row?.supplied===false?'<br>Unsupplied':''));
      marker.on('click',event=>{L.DomEvent.stopPropagation(event);pick('loads',load.id);});
      marker.on('dragend',()=>{const point=marker.getLatLng();send('move',{section:'loads',id:load.id,lat:point.lat,lon:point.lng});});
    }
    for (const source of model.sources || []) {
      const p=coordinates(source); if (!p) continue;
      const marker=L.marker(p,{icon:L.divIcon({className:'source-marker'+(source.in_service===false?' disabled':'')+(isSelected('sources',source.id)?' selected':''),html:'◆',iconSize:[23,23],iconAnchor:[11,11]}),zIndexOffset:50}).addTo(gridLayer);
      marker.bindTooltip('<strong>'+esc(source.id)+'</strong><br>Assumed supply point · '+esc(source.bus_id));
      marker.on('click',event=>{L.DomEvent.stopPropagation(event);if(['line','move'].includes(tool))pick('buses',source.bus_id);else pick('sources',source.id);});
    }
    updateLegend();
    if (!hasFitted) {fitMap();hasFitted=true;}
  }
  function addLineHandles(row, originalPoints) {
    const points=originalPoints.map(p=>p.slice());
    if (points.length === 2) points.splice(1,0,[(points[0][0]+points[1][0])/2,(points[0][1]+points[1][1])/2]);
    const count=points.length-2, stride=Math.max(1,Math.ceil(count/16));
    for (let i=1;i<points.length-1;i+=stride) {
      const handle=L.marker(points[i],{draggable:true,icon:L.divIcon({className:'line-handle',iconSize:[11,11],iconAnchor:[5,5]}),zIndexOffset:300}).addTo(handlesLayer);
      handle.bindTooltip('Drag to reshape this line. Endpoints stay connected.');
      handle.on('dragend',()=>{const p=handle.getLatLng();points[i]=[p.lat,p.lng];send('geometry',{id:row.id,points});});
    }
  }
  function fitMap() {
    if (!state?.model?.buses?.length) return;
    const bounds=L.latLngBounds(state.model.buses.map(b=>[b.lat,b.lon]));
    if(bounds.isValid())map.fitBounds(bounds,{padding:[42,44],maxZoom:13});
  }
  function updateLegend() {
    const legend=$('map-legend');legend.replaceChildren();
    const rows=local.color==='change'&&comparisonReady() ? [['change-up','Loading increased'],['change-down','Loading decreased'],['off','Disabled']] : currentResult()&&local.color!=='inputs' ? [['line','Normal'],['warn','Overload / unsupplied'],['off','Disabled']] : [['line','In service'],['off','Disabled']];
    rows.push(['dc','Data center'],['source','Supply']);
    for (const [kind,label] of rows) {const item=text('span','', 'legend-item');item.append(text('i','','swatch '+kind),text('span',label));legend.append(item);}
  }
  function setTool(value) {
    if (state?.busy) return;
    tool=value;lineStart=null;
    document.querySelectorAll('[data-tool]').forEach(b=>{b.classList.toggle('active',b.dataset.tool===value);b.setAttribute('aria-pressed',String(b.dataset.tool===value));});
    $('map').classList.toggle('editing',['load','bus','line'].includes(tool));
    $('map').classList.toggle('moving',tool==='move');
    updateToolHint();renderMap();
  }
  function updateToolHint() {
    const hints={select:'Select a transmission line, bus, or data center to edit it.',load:'Click the map to place a hypothetical data center. Press Esc to cancel.',bus:'Click the map to place a new bus. Press Esc to cancel.',line:lineStart?'Start: '+lineStart+' · select the destination bus. Esc cancels.':'Select a starting bus, then a destination bus to draw a line.',move:'Select a bus or line, then drag its handle. Data-center markers can be dragged directly.'};
    $('tool-hint').textContent=hints[tool];$('tool-hint').classList.toggle('drawing',tool!=='select');
  }
  map.on('click',event=>{
    if(state?.busy)return;
    if(tool==='load')openAddLoad(event.latlng);
    if(tool==='bus')openAddBus(event.latlng);
  });
  map.on('mousemove',event=>{$('coordinates').textContent=number(event.latlng.lat,4)+'° N  '+number(Math.abs(event.latlng.lng),4)+'° W';});
  map.on('zoomend',()=>{if(state)renderMap();});

  function field(label, key, value, options={}) {
    const wrapper=text('label','','field');wrapper.append(text('span',label));
    const input=document.createElement('input');input.name=key;input.value=value??'';input.type=options.type||'number';
    if(input.type==='number')input.step=options.step??'any';
    if(options.min!==undefined)input.min=String(options.min);
    if(options.max!==undefined)input.max=String(options.max);
    if(options.required!==false)input.required=true;
    if(options.readOnly)input.readOnly=true;
    wrapper.append(input);if(options.note)wrapper.append(text('small',options.note));return wrapper;
  }
  function busSelect(label,key,value) {
    const wrapper=text('label','','field');wrapper.append(text('span',label));
    const select=document.createElement('select');select.name=key;select.required=true;
    for(const bus of state.model.buses){const option=document.createElement('option');option.value=bus.id;option.textContent=bus.id+' · '+number(bus.vn_kv,0)+' kV';option.selected=bus.id===value;select.append(option);}
    wrapper.append(select);return wrapper;
  }
  function readForm(form) {
    const values={};
    for(const node of form.querySelectorAll('input[name],select[name]'))values[node.name]=node.type==='number'?Number(node.value):node.value.trim();
    return values;
  }
  function addButton(container,label,callback,className='') {const button=text('button',label,className);button.type='button';button.onclick=callback;container.append(button);return button;}
  function valuesList(container,rows) {
    const list=text('dl','','value-list');
    rows.forEach(([label,value])=>list.append(text('dt',label),text('dd',value)));container.append(list);
  }
  function renderInspector() {
    const container=$('selection-content');container.replaceChildren();
    const row=selected && state?.model?.[selected.section]?.find(r=>r.id===selected.id);
    if(!row) {
      $('selection-title').textContent='Explore the grid';$('selection-state').hidden=true;
      const empty=text('div','','empty-selection');empty.append(text('div','⌖','empty-symbol'),text('h3','Click a line to begin'),text('p','Inspect its connection, disable it, or change its endpoints.'),text('p','Add a hypothetical data center anywhere on the map. It connects to the nearest line or bus.'));container.append(empty);return;
    }
    const {section,id}=selected;
    $('selection-title').textContent=id;
    const result=currentResult()?.[section]?.[id], disabled=row.in_service===false;
    const pill=$('selection-state');pill.hidden=false;pill.textContent=disabled?'Disabled':result?.supplied===false?'Unsupplied':'In service';pill.className='status-pill'+(disabled?' off':result?.supplied===false?' bad':'');
    container.append(text('p',plural[section]+(row.name?' · '+row.name:''),'selection-subtitle'));
    const actions=text('div','','selection-actions');
    addButton(actions,disabled?'Enable':'Disable',()=>send('toggle',{section,id}),disabled?'enable':'disable');
    if(['loads','lines','buses','transformers'].includes(section))addButton(actions,'Remove',()=>send('delete',{section,id}),'delete');
    container.append(actions);
    const form=text('form','','inspector-form');
    if(section==='loads') {
      form.append(field('Demand (MW)','p_mw',row.p_mw,{min:0,max:10000,step:.1}));
      form.append(busSelect('Connection bus','bus_id',row.bus_id));
      const advanced=text('details','','advanced');advanced.append(text('summary','Advanced settings'));
      advanced.append(field('Power factor','pf',row.pf,{min:.01,max:1,step:.01}),field('Onsite generation (MW)','onsite_gen_mw',row.onsite_gen_mw||0,{min:0,max:10000,step:.1}));form.append(advanced);
      const submit=text('button','Apply load changes','primary');submit.type='submit';form.append(submit);
      form.onsubmit=e=>{e.preventDefault();send('update',{section,id,values:readForm(form)});};container.append(form);
      container.append(text('p','Use Move to drag this data center. Placement uses an assumed compatible connection.','selection-note'));
    } else if(section==='lines'||section==='transformers') {
      const isLine=section==='lines';
      form.append(busSelect(isLine?'From bus':'High-voltage bus','from_bus',row.from_bus??row.hv_bus),busSelect(isLine?'To bus':'Low-voltage bus','to_bus',row.to_bus??row.lv_bus));
      const submit=text('button','Reconnect','primary');submit.type='submit';form.append(submit);
      form.onsubmit=e=>{e.preventDefault();const v=readForm(form);if(isLine)send('reconnect',{id,...v});else send('update',{section,id,values:{hv_bus:v.from_bus,lv_bus:v.to_bus}});};container.append(form);
      if(isLine){container.append(text('p','Select Move to drag the route’s bend handles. Change the buses above to reconnect its endpoints.','selection-note'));renderLineParameters(container,row);}
    } else if(section==='buses') {
      form.append(field('Nominal voltage (kV)','vn_kv',row.vn_kv,{min:1,max:1000,step:1}));
      const submit=text('button','Apply bus changes','primary');submit.type='submit';form.append(submit);
      form.onsubmit=e=>{e.preventDefault();send('update',{section,id,values:readForm(form)});};container.append(form);
      const incident=(state.model.lines||[]).filter(l=>l.from_bus===id||l.to_bus===id).length;
      container.append(text('p',incident+' connected transmission '+(incident===1?'line':'lines')+'. Disabling this bus affects attached equipment. Use Move to change its location.','selection-note'));
    } else if(section==='sources') {
      form.append(field('Voltage setpoint (pu)','vm_pu',row.vm_pu??1,{min:.8,max:1.2,step:.01}));
      const submit=text('button','Apply supply changes','primary');submit.type='submit';form.append(submit);
      form.onsubmit=e=>{e.preventDefault();send('update',{section,id,values:readForm(form)});};container.append(form);
      container.append(text('p','Fixed assumed supply at '+row.bus_id+'. Disabling supply can leave connected areas unsupplied.','selection-note'));
    }
    const coord=coordinates(row);
    if(coord){container.append(text('hr','','inspector-divider'));valuesList(container,[['Latitude',number(coord[0],5)],['Longitude',number(coord[1],5)]]);}
    container.append(text('hr','','inspector-divider'),text('h3','Calculated results','section-label'));
    if(!result)container.append(text('p','Run simulation to calculate this case.','muted'));
    else if(section==='buses')valuesList(container,[['Voltage',number(result.vm_pu,3)+' pu'],['Angle',number(result.va_degree,2)+'°'],['Supplied',result.supplied?'Yes':'No']]);
    else if(section==='lines'||section==='transformers')valuesList(container,[['Loading',number(result.loading_percent,1)+'%'],['Real power',number(result.p_from_mw??result.p_hv_mw,2)+' MW'],['Losses',number(result.pl_mw,3)+' MW']]);
    else if(section==='loads')valuesList(container,[['Grid demand',number(result.net_grid_mw,2)+' MW'],['Reactive demand',number(result.q_mvar,2)+' MVAr'],['Supplied',result.supplied===false?'No':'Yes']]);
    container.querySelectorAll('button,input,select').forEach(node=>node.disabled=Boolean(state.busy));
  }
  function renderLineParameters(container,row) {
    const details=text('details','','advanced');details.append(text('summary','Line parameters'));
    const form=text('form','','inspector-form');
    form.append(field('Length (km)','length_km',row.length_km,{min:.000001}),field('Current rating (kA)','max_i_ka',row.max_i_ka??1,{min:.000001}),field('Resistance (Ω/km)','r_ohm_per_km',row.r_ohm_per_km??.05,{min:0}),field('Reactance (Ω/km)','x_ohm_per_km',row.x_ohm_per_km??.4,{min:0}));
    const submit=text('button','Apply parameters');submit.type='submit';form.append(submit);
    form.onsubmit=e=>{e.preventDefault();send('update',{section:'lines',id:row.id,values:readForm(form)});};details.append(form);container.append(details);
  }
  function openDialog(title, fields, note, callback) {
    if(state?.busy)return;
    $('dialog-title').textContent=title;$('dialog-fields').replaceChildren(...fields);$('dialog-note').textContent=note;dialogAction=callback;
    $('editor-dialog').showModal();
    const input=$('dialog-fields').querySelector('input');if(input)input.focus();
  }
  function closeDialog() {$('editor-dialog').close();dialogAction=null;}
  function openAddLoad(latlng) {
    const advanced=text('details','','advanced');advanced.append(text('summary','Advanced settings'),field('Power factor','pf',.95,{min:.01,max:1,step:.01}),field('Onsite generation (MW)','onsite_gen_mw',0,{min:0,max:10000,step:.1}));
    openDialog('Add data center',[field('Name','name','',{type:'text'}),field('Demand (MW)','p_mw',30,{min:0,max:10000,step:.1}),advanced],
      'Connects to the nearest line or bus. Suitable interface equipment is assumed. You can change the connection afterward.',
      values=>{send('add_load',{...values,lat:latlng.lat,lon:latlng.lng});setTool('select');});
  }
  function openAddBus(latlng) {
    openDialog('Add bus',[field('Name (optional)','name','',{type:'text',required:false}),field('Nominal voltage (kV)','vn_kv',138,{min:1,max:1000,step:1})],
      'Place the bus, then use Draw line to connect it to the network.',
      values=>{if(!values.name)delete values.name;send('add_bus',{...values,lat:latlng.lat,lon:latlng.lng});setTool('select');});
  }
  const metrics=[['grid_supply_mw','Grid supply','MW',1],['losses_mw','Network losses','MW',2],['min_voltage_pu','Lowest bus voltage','pu',3],['max_loading_percent','Highest line loading','%',1],['unsupplied_buses','Unsupplied buses','',0],['unserved_load_mw','Unserved demand','MW',1]];
  function renderResults() {
    const base=state?.baseline?.converged?state.baseline:null,scenario=state?.scenario?.converged?state.scenario:null;
    const body=$('metrics-body');body.replaceChildren();
    for(const [key,label,unit,digits] of metrics) {
      const row=document.createElement('tr'),b=base?.totals?.[key],s=scenario?.totals?.[key];
      row.append(text('td',label+(unit?' ('+unit+')':'')),text('td',number(b,digits)),text('td',number(s,digits)));
      const delta=b!=null&&s!=null&&comparisonReady()?s-b:null;
      row.append(text('td',delta==null?'—':(delta>0?'+':'')+number(delta,digits),delta>0?'positive':delta<0?'negative':''));body.append(row);
    }
    const result=state?.result,affected=$('affected-list');affected.replaceChildren();
    if(!result){affected.append(text('p','Run this case to see overloads and unsupplied areas.','muted'));$('affected-count').textContent='';}
    else if(!result.converged){affected.append(text('p',result.message||'The calculation did not converge. No current numerical results are available.','muted'));$('affected-count').textContent='Not solved';}
    else {
      const violations=result.violations||[];$('affected-count').textContent=violations.length+' issues';
      if(!violations.length)affected.append(text('p','No voltage, loading, or supply violations in this case.','muted'));
      for(const issue of violations.slice(0,200)) {
        const button=text('button','','affected-item');button.type='button';button.append(text('span',issue.id),text('span',issue.message+(issue.value==null?'':' · '+number(issue.value,issue.metric==='vm_pu'?3:1)+(issue.metric==='vm_pu'?' pu':'%'))));
        button.onclick=()=>{const section={bus:'buses',line:'lines',transformer:'transformers',load:'loads'}[issue.type];if(section){pick(section,issue.id);panTo(section,issue.id);}};affected.append(button);
      }
      if(violations.length>200)affected.append(text('p',(violations.length-200)+' more issues are included in the exported results.','muted'));
    }
    $('result-summary').textContent=state?.busy?'Calculating…':comparisonReady()?'Baseline and scenario ready':result?.converged?(state.case==='baseline'?'Baseline calculated':'Scenario calculated'):result?'Calculation failed':'Inputs changed / not calculated';
  }
  function panTo(section,id) {
    const row=state.model[section]?.find(item=>item.id===id);if(!row)return;
    const p=coordinates(row);
    if(p)map.panTo(p);else if(['lines','transformers'].includes(section)){const points=linePoints(row,section);if(points.length)map.panTo(points[Math.floor(points.length/2)]);}
  }
  window.renderEditor = next => {
    state=next;window.editorState=state;selected=next.selected||null;
    modelLookup={buses:new Map((state.model?.buses||[]).map(b=>[b.id,b]))};
    const baseline=state.case==='baseline';
    document.body.classList.toggle('busy',Boolean(state.busy));
    document.querySelectorAll('[data-case]').forEach(b=>{const active=b.dataset.case===state.case;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));b.disabled=Boolean(state.busy);});
    $('case-title').textContent=baseline?'Build your baseline':'Edit your comparison scenario';
    $('case-note').textContent=baseline?'Edit the grid, then run the simulation.':'Changes stay separate from the baseline.';
    $('start-scenario').textContent=baseline?'Start scenario from baseline':'Reset scenario to baseline';
    $('run-button').textContent=state.busy?'Calculating…':'▶  Run '+(baseline?'baseline':'simulation');
    $('save-state').textContent=state.dirty?'Unsaved changes':'Local project';
    const m=state.model||{};$('network-count').textContent=(m.lines?.length||0)+' lines · '+(m.buses?.length||0)+' buses · '+(m.loads?.length||0)+' data centers';
    const assumptions=typeof m.assumptions==='string'?m.assumptions:Array.isArray(m.assumptions)?m.assumptions.join(' '):'';
    $('assumptions-body').textContent='Houston routes provide the study layout. Connections, electrical parameters, and supply points are assumed. Supply locations stay fixed after an outage; isolated areas do not acquire replacement supplies. Data-center interfaces assume suitable equipment. This is a comparative study model, not a validated utility network.'+(assumptions?' '+assumptions:'');
    $('status-message').textContent=state.message||(state.busy?'Calculating the current network…':'Edits are applied to inputs. Press Run simulation to calculate.');
    $('status-light').className='status-light'+(state.busy?' busy':state.result&&!state.result.converged?' error':'');
    $('run-state').textContent=state.busy?'Solver running':state.result?.converged?'Calculated in '+number(state.result.runtime_seconds,2)+' s':state.result?'Calculation failed':'Not calculated';
    document.querySelectorAll('[data-action],[data-tool]').forEach(button=>button.disabled=Boolean(state.busy));
    $('undo-button').disabled=Boolean(state.busy)||!state.can_undo;
    $('redo-button').disabled=Boolean(state.busy)||!state.can_redo;
    $('start-scenario').disabled=Boolean(state.busy)||!state.baseline?.converged;
    $('run-button').disabled=Boolean(state.busy)||(!baseline&&!state.baseline?.converged);
    document.querySelector('[data-action="export"]').disabled=Boolean(state.busy)||!state.baseline?.converged;
    const changeOption=$('map-colors').querySelector('option[value="change"]');changeOption.disabled=baseline||!comparisonReady();
    if(local.color==='change'&&(baseline||!comparisonReady())){local.color='loading';$('map-colors').value=local.color;}
    renderMap();renderInspector();renderResults();
    requestAnimationFrame(()=>map.invalidateSize());
  };
  document.querySelectorAll('[data-action]').forEach(button=>button.addEventListener('click',()=>send(button.dataset.action)));
  document.querySelectorAll('[data-case]').forEach(button=>button.addEventListener('click',()=>{setTool('select');send('set_case',{case:button.dataset.case});}));
  document.querySelectorAll('[data-tool]').forEach(button=>button.addEventListener('click',()=>setTool(button.dataset.tool)));
  $('map-colors').onchange=()=>{local.color=$('map-colors').value;renderMap();};
  $('streets').onchange=()=>{if($('streets').checked)tileLayer.addTo(map);else{map.removeLayer(tileLayer);$('tile-note').hidden=true;}};
  $('show-buses').onchange=renderMap;$('fit-map').onclick=fitMap;
  $('results-toggle').onclick=()=>{const open=$('results-body').hidden;$('results-body').hidden=!open;$('results-toggle').setAttribute('aria-expanded',String(open));$('results-chevron').textContent=open?'⌄':'⌃';requestAnimationFrame(()=>map.invalidateSize());};
  $('assumptions-toggle').onclick=()=>{const open=$('assumptions-body').hidden;$('assumptions-body').hidden=!open;$('assumptions-toggle').setAttribute('aria-expanded',String(open));$('assumptions-toggle').querySelector('span').textContent=open?'−':'+';};
  $('dialog-close').onclick=closeDialog;$('dialog-cancel').onclick=closeDialog;
  $('dialog-form').onsubmit=event=>{event.preventDefault();const action=dialogAction,values=readForm($('dialog-form'));closeDialog();if(action)action(values);};
  $('editor-dialog').addEventListener('cancel',()=>{dialogAction=null;});
  document.addEventListener('keydown',event=>{
    const typing=['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName);
    if(event.key==='Escape'&&!$('editor-dialog').open)setTool('select');
    if(event.ctrlKey&&!typing&&!$('editor-dialog').open){
      const actions={s:'save',o:'open',z:event.shiftKey?'redo':'undo',y:'redo'};
      if(actions[event.key.toLowerCase()]){event.preventDefault();send(actions[event.key.toLowerCase()]);}
    }
  });
  new ResizeObserver(()=>map.invalidateSize()).observe($('map-frame')||document.querySelector('.map-frame'));
  if(typeof QWebChannel!=='undefined'&&window.qt?.webChannelTransport) {
    new QWebChannel(qt.webChannelTransport,channel=>{bridge=channel.objects.studyFiles;window.editorBridgeReady=true;bridge.ready();});
  } else setStatus('The desktop connection is unavailable. Open Project V4 through its launcher.');
})();
