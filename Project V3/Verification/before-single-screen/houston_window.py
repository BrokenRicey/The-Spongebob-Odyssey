"""Houston map embedded in the Texas Grid Analysis application."""
import json
import shutil
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Signal, Slot, QUrl, QFile, QIODevice
from PySide6.QtWidgets import QMainWindow, QTabWidget, QFileDialog, QMessageBox, QToolBar
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

from desktop.study import ROOT, default_model, validate_load, load_study
from desktop import houston_generator


BRIDGE_JS = '''
new QWebChannel(qt.webChannelTransport, channel => {
  const native = channel.objects.studyFiles;
  const busLabel=document.createElement('label');busLabel.textContent='Simulation bus (assumed connection)';
  const busSelect=document.createElement('select');busSelect.id='simulation-bus';
  busSelect.innerHTML='<option value="">Choose a bus before simulation</option>';
  for(const b of __BUS_OPTIONS__){const o=document.createElement('option');o.value=b.id;o.textContent=b.id+' · '+b.vn_kv+' kV';busSelect.appendChild(o);}
  busLabel.appendChild(busSelect);$('load-net').before(busLabel);
  const runButton=document.createElement('button');runButton.textContent='Run mapped loads in simulation';runButton.id='run-mapped';
  $('import-study').parentElement.after(runButton);
  const result=document.createElement('p');result.id='mapped-result';runButton.after(result);
  runButton.onclick=()=>{try{validateStudy({format:'houston-route-loads',version:1,loads:studyLoads});native.runMapped(JSON.stringify(studyLoads));}catch(e){$('load-status').textContent=e.message;}};
  native.result.connect(text=>{const r=JSON.parse(text);result.textContent=r.converged?'Assumed-network baseline: '+r.totals.grid_supply_mw.toFixed(1)+' MW supply; minimum voltage '+r.totals.min_voltage_pu.toFixed(3)+' pu. See Simulation & results.':r.message;});
  native.saved.connect(() => {studyDirty=false; $('load-status').textContent='Study saved.';});
  native.loaded.connect(text => {
    try {
      const loads=validateStudy(JSON.parse(text));
      if(studyDirty&&!confirm('Replace your unsaved route loads?')) return;
      studyLoads=loads; removedLoads=[]; studyDirty=false; resetEditor(); renderLoads();
      $('load-status').textContent='Opened '+loads.length+' loads.';native.acceptProject();
    } catch(e) {$('load-status').textContent=e.message;}
  });
  $('export-study').onclick=()=>native.save(JSON.stringify({format:'houston-route-loads',version:1,loads:studyLoads},null,2));
  $('import-study').onclick=()=>native.open();
  window.nativeFilesReady=true;
});
'''


class StudyFiles(QObject):
    saved = Signal()
    loaded = Signal(str)
    result = Signal(str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @Slot(str)
    def save(self, text):
        path, _ = QFileDialog.getSaveFileName(self.window, 'Save Houston route study', 'Houston-load-study.json', 'Route study (*.json)')
        if not path:
            return
        try:
            obj = json.loads(text)
            if obj.get('format') != 'houston-route-loads':
                raise ValueError('Unsupported route study')
            sim = self.window.simulation
            obj['simulation'] = {'format': 'texas-grid-desktop', 'version': 1,
                                 'model': sim.model, 'scenario_inputs': sim.spec()}
            Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding='utf-8')
            sim.dirty = False
            self.saved.emit()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self.window, 'Could not save study', str(exc))

    @Slot()
    def open(self):
        sim = self.window.simulation
        if sim.worker and sim.worker.isRunning():
            QMessageBox.information(self.window, 'Calculation running', 'Wait for the calculation to finish before opening another project.')
            return
        path, _ = QFileDialog.getOpenFileName(self.window, 'Open Houston route study', '', 'Route study (*.json)')
        if not path:
            return
        try:
            if Path(path).stat().st_size > 2_000_000:
                raise ValueError('Study exceeds 2 MB.')
            text = Path(path).read_text(encoding='utf-8-sig')
            obj = json.loads(text)
            # Validate both parts before changing the current project.
            if obj.get('format') != 'houston-route-loads' or not isinstance(obj.get('loads'), list):
                raise ValueError('Unsupported project file')
            if obj.get('simulation'):
                candidate = Path(self.window.work.name)/'candidate.gridstudy'
                candidate.write_text(json.dumps(obj['simulation']), encoding='utf-8')
                load_study(candidate)
            if not self.window.simulation.confirm_discard():
                return
            self.window.pending_simulation = obj.get('simulation')
            self.loaded.emit(text)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self.window, 'Could not open study', str(exc))

    @Slot()
    def acceptProject(self):
        payload = self.window.pending_simulation
        if not payload:
            return
        try:
            path = Path(self.window.work.name)/'simulation.gridstudy'
            path.write_text(json.dumps(payload), encoding='utf-8')
            model, spec = load_study(path)
            sim = self.window.simulation
            sim.model = model
            sim.populate_facilities(spec['load']['id'])
            sim.kind.setCurrentText(spec['kind'])
            sim.line.setCurrentIndex(sim.line.findData(spec['line']))
            sim.bus.setCurrentIndex(sim.bus.findData(spec['load']['bus_id']))
            sim.demand.setValue(spec['load']['p_mw'])
            sim.gen.setValue(spec['load']['onsite_gen_mw'])
            sim.pf.setValue(spec['load']['pf'])
            sim.removed_loads.clear()
            sim.undo_button.setEnabled(False)
            sim.invalidate_baseline('Project opened. Rerun calculations to refresh results.')
            sim.dirty = False
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self.window, 'Simulation inputs not restored', str(exc))
        finally:
            self.window.pending_simulation = None

    @Slot(str)
    def runMapped(self, text):
        sim = self.window.simulation
        if sim.worker and sim.worker.isRunning():
            QMessageBox.information(self.window, 'Calculation running', 'Wait for the current calculation to finish.')
            return
        try:
            routes = json.loads(text)
            if not isinstance(routes, list) or not 1 <= len(routes) <= 200:
                raise ValueError('Add between 1 and 200 mapped loads before simulation.')
            model = deepcopy(sim.model)
            model['loads'] = []
            names = set()
            for row in routes:
                load = dict(id=row['name'], bus_id=row.get('simulation_bus'), p_mw=row['p_mw'],
                            pf=row['pf'], onsite_gen_mw=row['onsite_gen_mw'])
                if load['id'] in names:
                    raise ValueError('Mapped load names must be unique.')
                if not load['bus_id']:
                    raise ValueError('Choose and save a simulation bus for '+load['id']+'. This is an assumed electrical connection, separate from its GIS route.')
                names.add(load['id'])
                validate_load(load, model)
                model['loads'].append(load)
            sim.model = model
            sim.removed_loads.clear()
            sim.undo_button.setEnabled(False)
            sim.populate_facilities()
            sim.kind.setCurrentText('Load change')
            sim.invalidate_baseline('Mapped loads transferred using your assumed bus connections.')
            sim.dirty = True
            sim.start_baseline()
            sim.worker.completed.connect(lambda result: self.result.emit(json.dumps(result)))
            self.window.tabs.setCurrentIndex(1)
        except (ValueError, KeyError, TypeError) as exc:
            QMessageBox.warning(self.window, 'Mapped loads need attention', str(exc))


class MapPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f'MAP JS {line}: {message}', flush=True)

    def acceptNavigationRequest(self, url, kind, main_frame):
        # Keep the native file bridge restricted to our own generated map.
        if main_frame and url.host() not in ('127.0.0.1', ''):
            return False
        return super().acceptNavigationRequest(url, kind, main_frame)


class HoustonWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Texas Grid Analysis • Project V3')
        self.resize(1560, 990)
        self.setMinimumSize(1050, 700)
        self.pending_simulation = None
        self.work = tempfile.TemporaryDirectory(prefix='texas-grid-map-')
        folder = Path(self.work.name)
        shutil.copytree(ROOT/'data/houston_map', folder, dirs_exist_ok=True)
        houston_generator.ROOT = folder
        houston_generator.main(['--no-browser'])
        page = (folder/'houston_grid.html').read_text(encoding='utf-8')
        page = page.replace('<title>Houston | Grid & Data Centers</title>', '<title>Texas Grid Analysis | Houston transmission map</title>')
        resource = QFile(':/qtwebchannel/qwebchannel.js')
        if not resource.open(QIODevice.ReadOnly):
            raise RuntimeError('Qt WebChannel script is unavailable')
        channel_script = bytes(resource.readAll()).decode('utf-8')
        resource.close()
        page = page.replace('</head>', '<script>'+channel_script+'</script></head>')
        bridge = BRIDGE_JS.replace('__BUS_OPTIONS__', json.dumps([b for b in default_model()['buses'] if b['vn_kv']==138]))
        page = page.replace('</script></body>', bridge+'</script></body>')
        page = page.replace('Save study downloads a file with your loads and route attachments. Open it to continue later.', 'Save study stores your loads and route attachments in a JSON file. Open it to continue later.')
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
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.web = QWebEngineView()
        self.page = MapPage(self.web)
        self.web.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.files = StudyFiles(self)
        self.channel.registerObject('studyFiles', self.files)
        self.page.setWebChannel(self.channel)
        self.tabs.addTab(self.web, 'Houston transmission map')
        # Preserve the existing solver without implying that GIS routes are its topology.
        from desktop.window import MainWindow
        self.simulation = MainWindow()
        self.simulation.save_button.setText('Save simulation only')
        self.simulation.open_button.setText('Open simulation only')
        self.tabs.addTab(self.simulation, 'Simulation & results')
        toolbar = QToolBar('Project', self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction('Save project', lambda: self.page.runJavaScript("document.getElementById('export-study').click()"))
        toolbar.addAction('Open project', self.files.open)
        toolbar.addSeparator()
        toolbar.addAction('Houston map', lambda: self.tabs.setCurrentIndex(0))
        toolbar.addAction('Simulation & results', lambda: self.tabs.setCurrentIndex(1))
        toolbar.addAction('Export results', self.simulation.export_file)
        self.statusBar().showMessage('Houston route attachments are study assumptions. Electrical simulation is available in the separate representative-network tab.')
        self.web.setUrl(QUrl(f'http://127.0.0.1:{self.server.server_port}/houston_grid.html'))
        self._closing = False

    def closeEvent(self, event):
        if self._closing:
            event.accept()
            return
        event.ignore()
        if self.simulation.worker and self.simulation.worker.isRunning():
            QMessageBox.information(self, 'Calculation running', 'Wait for the calculation to finish before closing.')
            return

        def checked(dirty):
            if dirty and QMessageBox.question(self, 'Unsaved route loads', 'Close without saving your route-load changes?', QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return
            if not self.simulation.confirm_discard():
                return
            self._closing = True
            self.server.shutdown()
            self.server.server_close()
            self.server_thread.join(timeout=2)
            self.work.cleanup()
            self.close()

        self.page.runJavaScript("typeof studyDirty !== 'undefined' && studyDirty", checked)
