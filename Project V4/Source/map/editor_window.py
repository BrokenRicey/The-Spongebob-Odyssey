"""Project V4 desktop shell and validated map-to-simulation bridge."""
import json
import mimetypes
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Signal, Slot, QThread, QUrl, QFile, QIODevice
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow, QFileDialog, QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

from simulation import editor
from simulation.study import export_csv

ROOT = Path(__file__).resolve().parents[1]


class SimulationJob(QThread):
    completed = Signal(object)

    def __init__(self, model, case, parent=None):
        super().__init__(parent)
        self.model, self.case = deepcopy(model), case

    def run(self):
        try:
            result = editor.run_model(self.model)
        except Exception as exc:
            result = dict(converged=False, status='failed', message=str(exc),
                          buses={}, lines={}, transformers={}, loads={}, totals={}, violations=[])
        self.completed.emit(result)


class EditorBridge(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @Slot()
    def ready(self):
        self.window.ready = True
        self.window.send_state()

    @Slot(str)
    def action(self, text):
        try:
            if len(text) > 1_000_000:
                raise ValueError('Edit is too large.')
            command = json.loads(text)
            if not isinstance(command, dict):
                raise ValueError('Invalid edit.')
            self.window.dispatch(command)
        except (ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
            self.window.message = str(exc)
            self.window.send_state()


class EditorPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, main_frame):
        if main_frame and url.host() not in ('127.0.0.1', ''):
            return False
        return super().acceptNavigationRequest(url, kind, main_frame)


class EditorWindow(QMainWindow):
    def __init__(self, model=None):
        super().__init__()
        self.setWindowTitle('Texas Grid Analysis — Project V4')
        self.resize(1520, 940)
        self.setMinimumSize(1000, 700)
        if model is None:
            from simulation.houston import default_houston_model
            model = default_houston_model()
        self.study = editor.EditorStudy(model)
        self.case = 'baseline'
        self.selected = None
        self.worker = None
        self.ready = self.dirty = self.scenario_started = False
        self.message = 'Edit your baseline, then press Run Simulation.'
        self.project_path = None
        self._closed = False
        self._serve_assets()
        self.web = QWebEngineView(self)
        self.page = EditorPage(self.web)
        self.web.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.bridge = EditorBridge(self)
        self.channel.registerObject('studyFiles', self.bridge)
        self.page.setWebChannel(self.channel)
        self.setCentralWidget(self.web)
        self.web.setUrl(QUrl(f'http://127.0.0.1:{self.server.server_port}/'))
        for title, shortcut, command in [('Save', QKeySequence.Save, 'save'),
                                          ('Open', QKeySequence.Open, 'open'),
                                          ('Undo', QKeySequence.Undo, 'undo'),
                                          ('Redo', QKeySequence.Redo, 'redo')]:
            action = QAction(title, self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked=False, command=command: self.bridge.action(json.dumps({'type': command})))
            self.addAction(action)

    def _serve_assets(self):
        assets = ROOT / 'map/assets'
        resource = QFile(':/qtwebchannel/qwebchannel.js')
        if not resource.open(QIODevice.ReadOnly):
            raise RuntimeError('Qt WebChannel is unavailable.')
        channel_script = bytes(resource.readAll())
        resource.close()
        paths = {'/': 'editor.html', '/editor.html': 'editor.html', '/editor.js': 'editor.js',
                 '/editor.css': 'editor.css', '/vendor/leaflet.js': 'vendor/leaflet.js',
                 '/vendor/leaflet.css': 'vendor/leaflet.css'}
        for path in (assets/'vendor/images').glob('*'):
            paths['/vendor/images/'+path.name] = 'vendor/images/'+path.name

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                key = urlsplit(self.path).path
                if key == '/qwebchannel.js':
                    body, mime = channel_script, 'application/javascript'
                elif key in paths:
                    path = assets/paths[key]
                    if not path.is_file():
                        self.send_error(404)
                        return
                    body = path.read_bytes()
                    mime = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', mime+'; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    @property
    def busy(self):
        return self.worker is not None

    def state(self):
        model = self.study.model(self.case)
        if self.selected and not any(r['id'] == self.selected['id'] for r in model.get(self.selected['section'], [])):
            self.selected = None
        return dict(case=self.case, model=model, baseline_model=self.study.baseline_model,
                    baseline=self.study.baseline, scenario=self.study.scenario,
                    result=getattr(self.study, self.case), busy=self.busy, dirty=self.dirty,
                    can_undo=bool(self.study._undo[self.case]), can_redo=bool(self.study._redo[self.case]),
                    selected=self.selected, message=self.message,
                    comparison_ready=bool(self.study.baseline and self.study.baseline.get('converged') and
                                          self.study.scenario and self.study.scenario.get('converged')))

    def send_state(self):
        if self.ready:
            self.page.runJavaScript('window.renderEditor('+json.dumps(self.state(), allow_nan=False)+')')

    def dispatch(self, command):
        kind = command.get('type')
        if self.busy:
            raise ValueError('Simulation is running. Wait for the results before editing.')
        if kind == 'select':
            section, key = command['section'], command['id']
            editor._row(self.study.model(self.case), section, key)
            self.selected = {'section': section, 'id': key}
        elif kind == 'set_case':
            case = command['case']
            self.study.model(case)
            if case == 'scenario' and not self.scenario_started:
                if not self.study.baseline or not self.study.baseline['converged']:
                    raise ValueError('Run your baseline before starting a comparison scenario.')
                self.study.reset_scenario(record_history=False)
                self.scenario_started = True
            self.case = case
            self.message = 'Edit this '+case+'; results update when you press Run Simulation.'
        elif kind == 'run':
            self.start_run()
            return
        elif kind == 'reset_scenario':
            self.study.reset_scenario()
            self.scenario_started = True
            self.case = 'scenario'
            self.dirty = True
            self.message = 'Scenario copied from the baseline. Undo is available.'
        elif kind in ('undo', 'redo'):
            changed = getattr(self.study, kind)(self.case)
            self.dirty |= changed
            self.message = ('Edit '+('undone' if kind == 'undo' else 'restored')+'. Run Simulation to update results.') if changed else 'No edits to '+kind+'.'
        elif kind == 'save':
            self.save_project()
        elif kind == 'open':
            self.open_project()
        elif kind == 'export':
            self.export_results()
        else:
            self.edit_command(command)
        self.send_state()

    def edit_command(self, command):
        kind = command['type']
        def mutation(model):
            if kind == 'add_load':
                return 'loads', editor.add_datacenter(model, command.get('name'), command['lat'], command['lon'],
                                                       command['p_mw'], command.get('pf', .95), command.get('onsite_gen_mw', 0))
            if kind == 'add_bus':
                return 'buses', editor.add_bus(model, command['lat'], command['lon'], command.get('vn_kv', 138), command.get('name') or None)
            if kind == 'add_line':
                row = editor.add_line(model, command['from_bus'], command['to_bus'], command.get('name') or None)
                return ('transformers' if 'hv_bus' in row else 'lines'), row
            section = command.get('section', 'lines')
            key = command['id']
            row = editor._row(model, section, key)
            if kind == 'toggle':
                editor.toggle_component(model, section, key)
            elif kind == 'move':
                if section == 'buses':
                    editor.move_bus(model, key, command['lat'], command['lon'])
                elif section == 'loads':
                    row = editor.move_datacenter(model, key, command['lat'], command['lon'])
                else:
                    raise ValueError('Drag a bus, data center, or a selected line bend.')
            elif kind == 'reconnect':
                editor.reconnect_line(model, key, command['from_bus'], command['to_bus'])
            elif kind == 'geometry':
                row['points'] = command['points']
                editor.validate_model(model)
                row['points'] = editor.line_points(model, row)
                row['length_km'] = max(.001, sum(editor.distance_km(a,b) for a,b in zip(row['points'],row['points'][1:])))
            elif kind == 'update':
                allowed = {'loads': {'p_mw','pf','onsite_gen_mw','bus_id'},
                           'buses': {'vn_kv'}, 'lines': {'length_km','r_ohm_per_km','x_ohm_per_km','c_nf_per_km','max_i_ka'},
                           'sources': {'vm_pu'}, 'transformers': {'hv_bus','lv_bus','sn_mva','vk_percent','vkr_percent'}}
                values = command['values']
                if not isinstance(values, dict) or set(values)-allowed.get(section,set()):
                    raise ValueError('Unsupported equipment setting.')
                row.update(values)
                if section == 'transformers' and ('hv_bus' in values or 'lv_bus' in values):
                    high = editor._row(model, 'buses', row['hv_bus'])
                    low = editor._row(model, 'buses', row['lv_bus'])
                    if high['vn_kv'] <= low['vn_kv']:
                        raise ValueError('Select a higher-voltage bus and a lower-voltage bus for this transformer.')
                    row.update(vn_hv_kv=high['vn_kv'], vn_lv_kv=low['vn_kv'])
            elif kind == 'delete':
                if section == 'buses':
                    attached = any(key in (x.get('from_bus'),x.get('to_bus'),x.get('hv_bus'),x.get('lv_bus'),x.get('bus_id'))
                                   for group in ('lines','transformers','loads','sources') for x in model.get(group, []))
                    if attached:
                        raise ValueError('This bus has attached equipment. Disable it, or reconnect/remove that equipment before deleting the bus.')
                model[section].remove(row)
                return None
            else:
                raise ValueError('Unknown map action: '+str(kind))
            return section, row
        result = self.study.edit(self.case, mutation)
        if result:
            section, row = result
            self.selected = dict(section=section, id=row['id'])
        self.dirty = True
        self.message = 'Changes saved in this '+self.case+'. Press Run Simulation to calculate their effects.'
        if self.case == 'baseline' and self.scenario_started:
            self.message = 'Baseline changed. Existing scenario edits are preserved; rerun both cases to compare.'
        if kind == 'add_load' and result:
            self.message = 'Added '+result[1]['id']+' at '+result[1]['bus_id']+'. Site transformers are assumed. Run Simulation to update results.'

    def start_run(self):
        if self.case == 'scenario' and not (self.study.baseline and self.study.baseline['converged']):
            raise ValueError('Run a converged baseline before calculating the comparison scenario.')
        setattr(self.study, self.case, None)
        self.message = 'Calculating '+self.case+'…'
        self.worker = SimulationJob(self.study.model(self.case), self.case, self)
        self.worker.completed.connect(self._run_complete)
        self.worker.finished.connect(self._job_finished)
        self.worker.start()
        self.send_state()

    def _run_complete(self, result):
        setattr(self.study, self.worker.case, result)
        self.dirty = True
        self.message = self.worker.case.capitalize()+': '+result['message']

    def _job_finished(self):
        job = self.worker
        self.worker = None
        job.deleteLater()
        self.send_state()

    def save_project(self, path=None):
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, 'Save Project V4', self.project_path or 'Houston V4.gridstudy', 'Grid study (*.gridstudy)')
        if not path:
            return False
        if not self.scenario_started:
            self.study.reset_scenario(record_history=False)
        self.study.save(path)
        self.project_path = str(path)
        self.dirty = False
        self.message = 'Saved '+Path(path).name
        return True

    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, 'Save changes?', 'Save this project before continuing?',
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        return self.save_project() if answer == QMessageBox.Save else answer == QMessageBox.Discard

    def open_project(self, path=None):
        if not self.confirm_discard():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, 'Open Project V4', '', 'Grid study (*.gridstudy)')
        if not path:
            return
        candidate = editor.EditorStudy.load(path)
        self.study = candidate
        self.project_path = str(path)
        self.case = 'baseline'
        self.scenario_started = True
        self.selected = None
        self.dirty = False
        self.message = 'Project loaded. Run the baseline and scenario to refresh results.'

    def export_results(self):
        if not self.study.baseline:
            raise ValueError('Run the baseline before exporting results.')
        path, selected = QFileDialog.getSaveFileName(self, 'Export results', 'Houston V4 results.csv', 'CSV (*.csv);;JSON study (*.json)')
        if path:
            if selected.startswith('CSV'):
                export_csv(path, self.study.baseline, self.study.scenario)
            else:
                if not self.scenario_started:
                    self.study.reset_scenario(record_history=False)
                self.study.save(path)
            self.message = 'Exported '+Path(path).name

    def shutdown(self):
        if not self._closed:
            self._closed = True
            self.server.shutdown()
            self.server.server_close()
            self.server_thread.join(timeout=2)

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(self, 'Simulation running', 'Wait for the simulation to finish before closing.')
            event.ignore()
        elif self.confirm_discard():
            self.shutdown()
            event.accept()
        else:
            event.ignore()
