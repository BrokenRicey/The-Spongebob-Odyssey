"""Single-screen Houston map, load editor, and V4 results workspace."""
import json
import math
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Signal, Slot, QUrl, QFile, QIODevice
from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QLabel, QPushButton, QWidget, QVBoxLayout, QComboBox, QHBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

from simulation.study import ROOT, default_model, load_study, save_study
from map import generator


class HoustonMap(QWebEngineView):
    selected = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(240, 210)
        self.model = self.result = self.baseline = None
        self.mode = 'Baseline'
        self.active = ('loads', 'DC_01')
        self.show_gis = self.show_directory = True
        self.palette_colors = {}
        self.ready = False
        self.directory = json.loads((ROOT/'data/github_houston/data_centers.geojson').read_text(encoding='utf-8'))['features']

    def update(self, *args):
        super().update(*args)
        if not self.ready:
            return
        state = dict(model=self.model, result=self.result, baseline=self.baseline, mode=self.mode,
                     active=self.active, show_gis=self.show_gis, show_directory=self.show_directory,
                     directory=self.directory)
        self.page().runJavaScript('window.renderStudy('+json.dumps(state, allow_nan=False)+')')

    def fit(self):
        if self.ready:
            self.page().runJavaScript('map.fitBounds(bounds)')

    def zoom_by(self, factor):
        if self.ready:
            self.page().runJavaScript('map.setZoom(map.getZoom()+'+str(1 if factor>1 else -1)+')')


class Bridge(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @Slot()
    def ready(self):
        self.window.web.ready = True
        self.window.simulation.refresh_map()

    @Slot(str, str)
    def componentPicked(self, section, key):
        sim = self.window.simulation
        if sim.worker and sim.worker.isRunning():
            return
        if section in ('loads', 'buses', 'lines', 'transformers') and any(r['id']==key for r in sim.model.get(section, [])):
            sim.on_map_selected(section, key)

    @Slot(str)
    def routePicked(self, text):
        try:
            row = json.loads(text)
            self.window.validate_attachment(dict(route_key=row['route_key'], route_point=row['point']))
            self.window.route = row
            self.window.route_note.setText('Selected GIS line '+row['line_id']+'. Add a load here, or attach the selected load below. The electrical bus is chosen separately.')
            self.window.attach_button.setEnabled(not self.window.busy())
        except (ValueError, KeyError, TypeError) as exc:
            self.window.simulation.error(str(exc))


class MapPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, main_frame):
        if main_frame and url.host() not in ('127.0.0.1', ''):
            return False
        return super().acceptNavigationRequest(url, kind, main_frame)


class HoustonWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Texas Grid Analysis - Project V3')
        self.resize(1560, 990)
        self.setMinimumSize(1100, 740)
        self.route = None
        self._closing = False
        assets = ROOT/'map/assets'
        cache = json.loads((assets/'source_cache.json').read_text(encoding='utf-8'))
        data = generator.build_features(cache, generator.DEFAULT_BBOX)
        self.routes = {str(f['properties'].get('OBJECTID', f['properties'].get('OBJECTID_1', f['properties']['ID']))): f for f in data['features']}
        records = json.loads((assets/'data_centers.json').read_text(encoding='utf-8'))['records']
        west,south,east,north=generator.DEFAULT_BBOX
        for record in records:
            lat,lon=record.get('latitude'),record.get('longitude')
            record['status']='included' if lat is not None and lon is not None and west<=lon<=east and south<=lat<=north else 'outside'
            record['reason']='Outside study boundary or unresolved address' if record['status']!='included' else 'Within study boundary'
        page = generator.PAGE
        for old, new in [('__COUNT__', str(len(data['features']))), ('__DATE__', cache['retrieved_utc'][:10]),
                         ('__DATA__', json.dumps(data)), ('__COLORS__', json.dumps(generator.COLORS)),
                         ('__BBOX__', json.dumps(generator.DEFAULT_BBOX)), ('__DC_DATA__', json.dumps(records))]:
            page = page.replace(old, new.replace('<', '\\u003c'))
        page = page.replace('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">', '<style>'+(assets/'vendor/leaflet.css').read_text(encoding='utf-8')+'</style>')
        page = page.replace('<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>', '<script>'+(assets/'vendor/leaflet.js').read_text(encoding='utf-8')+'</script>')
        resource = QFile(':/qtwebchannel/qwebchannel.js')
        if not resource.open(QIODevice.ReadOnly):
            raise RuntimeError('Qt WebChannel script is unavailable')
        channel_script = bytes(resource.readAll()).decode('utf-8')
        resource.close()
        css = '''.panel{left:auto;right:12px;top:48px;width:225px;padding:14px;max-height:calc(100vh - 110px)}
        .map-tools,.map-note{background:#ffffffed;padding:7px 10px;border-radius:5px;box-shadow:0 1px 6px #1234;font:11px system-ui;color:#173747}
        .map-tools{display:flex;gap:9px;align-items:center}.map-tools button{padding:5px 8px;font-size:11px}.map-tools label{white-space:nowrap}
        .native-load{background:#fff0a3;border:2px solid #97540a;border-radius:50%;text-align:center;line-height:26px;font-size:17px;box-shadow:0 1px 5px #1235}
        .native-load.active{border:3px solid #133d60;box-shadow:0 0 0 4px #ffffffaa}.native-load.violation{background:#ffadb5}.native-load.disconnected{background:#cbd5e1;opacity:.65}
        '''
        page = page.replace('</head>', '<style>'+css+'</style><script>'+channel_script+'</script></head>')
        page = page.replace('No power-flow results are represented.', 'Bus and load overlays show results for the assumed electrical model, not capacities of the GIS routes.')
        page = page.replace('</script></body>', (assets/'unified_map.js').read_text(encoding='utf-8')+'</script></body>')
        payload = page.encode('utf-8')

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if urlsplit(self.path).path not in ('/', '/houston_grid.html'):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.web = HoustonMap()
        self.page = MapPage(self.web)
        self.web.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.bridge = Bridge(self)
        self.channel.registerObject('studyFiles', self.bridge)
        self.page.setWebChannel(self.channel)
        from program.window import MainWindow
        self.simulation = MainWindow(map_widget=self.web)
        sim = self.simulation
        self.setCentralWidget(sim)
        sim.statusBar().showMessage('Houston GIS routes with calculated bus/load overlays. Electrical connections and equipment parameters are study assumptions.')
        # Existing widgets remain visible around the map; no workspace tabs.
        sim.tabs.tabBar().hide()
        self.result_view = QComboBox()
        for i in range(sim.tabs.count()):
            self.result_view.addItem(sim.tabs.tabText(i))
        self.result_view.currentIndexChanged.connect(sim.tabs.setCurrentIndex)
        sim.tabs.currentChanged.connect(self.result_view.setCurrentIndex)
        center = sim.main_split.widget(1)
        sim.tabs.setParent(None)
        result_panel = QWidget()
        layout = QVBoxLayout(result_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.result_view)
        layout.addWidget(sim.tabs)
        center.addWidget(result_panel)
        center.setSizes([620, 220])
        form = sim.undo_button.parentWidget().layout()
        self.route_note = QLabel('Click a colored GIS line to place a new load or attach the selected load.')
        self.route_note.setWordWrap(True)
        self.attach_button = QPushButton('Attach to line')
        self.attach_button.setEnabled(False)
        self.attach_button.clicked.connect(self.attach_selected)
        self.detach_button = QPushButton('Clear attachment')
        self.detach_button.clicked.connect(self.detach_selected)
        position = form.indexOf(sim.undo_button)+1
        route_actions=QWidget()
        route_layout=QHBoxLayout(route_actions);route_layout.setContentsMargins(0,0,0,0);route_layout.setSpacing(6)
        route_layout.addWidget(self.attach_button);route_layout.addWidget(self.detach_button)
        form.setSpacing(6)
        sim.facility_note.hide()
        for widget in [self.route_note, route_actions]:
            form.insertWidget(position, widget)
            position += 1
        self.original_add = sim.add_load
        sim.add_button.clicked.disconnect()
        sim.add_button.clicked.connect(self.add_load)
        self.original_busy = sim.set_busy
        sim.set_busy = self.set_busy
        self.original_detail = sim.refresh_detail
        sim.refresh_detail = self.refresh_detail
        sim.open_button.clicked.disconnect()
        sim.open_button.clicked.connect(self.open_project)
        sim.save_button.clicked.disconnect()
        sim.save_button.clicked.connect(self.save_project)
        sim.save_button.setText('Save project')
        sim.open_button.setText('Open project')
        # Ensure keyboard shortcuts and discard-save use the same project format.
        sim.save_file = self.save_project
        sim.open_file = self.open_project
        for action in sim.actions():
            if action.text() in ('Save', 'Open'):
                action.triggered.disconnect()
                action.triggered.connect(self.save_project if action.text()=='Save' else self.open_project)
        for label in sim.findChildren(QLabel):
            if label.text().startswith(('Click a load on the map to edit it.', '03   ANALYSIS SCOPE', 'AC steady-state power flow')):label.hide()
            if label.text() == '●  LOCAL & OFFLINE':label.setText('●  LOCAL SIMULATION')
            if label.text().startswith('● Bus     ▣ Study load'):label.setText('● Calculated bus   ⚡ Study load   Colored routes: GIS   Dashed selection: assumed model')
        for button in sim.findChildren(QPushButton):
            if button.text().startswith('Fault study'):button.hide()
        sim.baseline_button.setToolTip('Run the saved inputs shown in this workspace. Apply edited values first.')
        self.web.setUrl(QUrl(f'http://127.0.0.1:{self.server.server_port}/houston_grid.html'))

    def busy(self):
        return bool(self.simulation.worker and self.simulation.worker.isRunning())

    def set_busy(self, busy):
        self.original_busy(busy)
        self.attach_button.setEnabled(not busy and self.route is not None)
        self.detach_button.setEnabled(not busy)

    def validate_attachment(self, load):
        if 'route_key' not in load:
            return
        feature = self.routes.get(str(load['route_key']))
        point = load.get('route_point')
        if not feature or not isinstance(point, dict):raise ValueError('Unknown route or missing attachment point.')
        lat, lon = point.get('lat'), point.get('lng')
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (lat, lon)) or not -85<lat<85 or not -180<lon<180:
            raise ValueError('Invalid route coordinates.')
        def project(x,y):return (6378137*math.radians(x),6378137*math.log(math.tan(math.pi/4+math.radians(y)/2)))
        px, py = project(lon,lat)
        nearest = float('inf')
        for part in feature['geometry']['coordinates']:
            for a,b in zip(part,part[1:]):
                ax,ay=project(*a[:2]);bx,by=project(*b[:2]);dx,dy=bx-ax,by-ay
                t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy))) if dx or dy else 0
                nearest=min(nearest,math.hypot(px-ax-t*dx,py-ay-t*dy))
        if nearest>3:raise ValueError('Attachment point is not on its GIS route.')

    def attach_selected(self):
        if self.busy() or not self.route:return
        sim = self.simulation
        row = next(l for l in sim.model['loads'] if l['id']==sim.facility.currentData())
        row.update(route_key=self.route['route_key'], line_id=self.route['line_id'], route_point=deepcopy(self.route['point']))
        sim.invalidate_baseline('Route attachment updated. Run baseline to refresh results.')
        sim.dirty = True
        sim.refresh_detail()

    def detach_selected(self):
        if self.busy():return
        sim = self.simulation
        row = next(l for l in sim.model['loads'] if l['id']==sim.facility.currentData())
        for key in ('route_key','line_id','route_point'):row.pop(key,None)
        sim.invalidate_baseline('Route attachment cleared; load remains on its assumed simulation bus.')
        sim.dirty = True
        sim.refresh_detail()

    def add_load(self):
        before={l['id'] for l in self.simulation.model['loads']}
        self.original_add()
        if self.route and self.simulation.facility.currentData() not in before:
            self.attach_selected()

    def refresh_detail(self):
        self.original_detail()
        if self.web.active[0]=='loads':
            row=next((l for l in self.simulation.model['loads'] if l['id']==self.web.active[1]),{})
            extra='GIS route: '+str(row['line_id']) if row.get('route_key') else 'No GIS route attachment; shown beside its assumed bus.'
            self.simulation.detail.setPlainText(self.simulation.detail.toPlainText()+'\n\n'+extra)

    def save_project(self):
        sim=self.simulation
        path,_=QFileDialog.getSaveFileName(self,'Save Texas Grid project','Houston.gridstudy','Grid project (*.gridstudy)')
        if not path:return False
        try:
            for load in sim.model['loads']:self.validate_attachment(load)
            save_study(path,sim.model,sim.spec(),sim.baseline,sim.scenario)
            sim.dirty=False
            sim.append_log('Saved unified project: '+path)
            return True
        except (OSError, ValueError, KeyError, TypeError) as exc:
            sim.error(str(exc));return False

    def open_project(self):
        sim=self.simulation
        if self.busy():return
        if not sim.confirm_discard():return
        path,_=QFileDialog.getOpenFileName(self,'Open Texas Grid project','','Grid project (*.gridstudy *.json)')
        if not path:return
        try:
            obj=json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if obj.get('format')=='houston-route-loads':
                # Older V3 files kept map and simulation lists separately.
                payload=obj.get('simulation')
                model=deepcopy(payload['model'] if payload else default_model())
                if obj['loads']:
                    model['loads']=[dict(id=l['name'],bus_id=l.get('simulation_bus'),p_mw=l['p_mw'],pf=l['pf'],onsite_gen_mw=l['onsite_gen_mw'],route_key=l['route_key'],line_id=l['line_id'],route_point=l['point']) for l in obj['loads']]
                spec=dict(kind='Load change',line=model['lines'][0]['id'],load=deepcopy(model['loads'][0]))
                # Reuse existing study validator through a temporary file.
                import tempfile
                with tempfile.TemporaryDirectory() as folder:
                    candidate=Path(folder)/'converted.gridstudy'
                    save_study(candidate,model,spec)
                    model,spec=load_study(candidate)
            else:
                model,spec=load_study(path)
            for load in model['loads']:self.validate_attachment(load)
            sim.model=model;sim.removed_loads.clear();sim.undo_button.setEnabled(False)
            sim.populate_facilities(spec['load']['id'])
            sim.loading=True
            sim.kind.setCurrentText(spec['kind']);sim.line.setCurrentIndex(sim.line.findData(spec['line']))
            sim.bus.setCurrentIndex(sim.bus.findData(spec['load']['bus_id']))
            sim.demand.setValue(spec['load']['p_mw']);sim.gen.setValue(spec['load']['onsite_gen_mw']);sim.pf.setValue(spec['load']['pf'])
            sim.loading=False;sim.inputs_changed(mark_dirty=False)
            sim.invalidate_baseline('Project loaded. Rerun baseline to refresh map and results.');sim.dirty=False
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            sim.loading=False;sim.error(str(exc))

    def closeEvent(self,event):
        if self._closing:event.accept();return
        if self.busy():
            QMessageBox.information(self,'Calculation running','Wait for the calculation to finish before closing.');event.ignore();return
        if not self.simulation.confirm_discard():event.ignore();return
        self._closing=True
        self.server.shutdown();self.server.server_close();self.server_thread.join(timeout=2)
        event.accept()
