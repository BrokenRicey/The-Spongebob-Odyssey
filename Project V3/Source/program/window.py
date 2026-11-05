import json
import math
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSettings
from PySide6.QtGui import QColor, QFont, QAction
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QFormLayout, QScrollArea, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QFileDialog, QMessageBox,
    QLineEdit, QCheckBox, QProgressBar, QTextBrowser, QDialog, QInputDialog, QDialogButtonBox)
from simulation.study import (ROOT, KINDS, default_model, validate_load, run_baseline, run_scenario,
                           save_study, load_study, export_csv)
from map.diagram import GridMap, SweepChart, DARK, LIGHT


def fmt(value, digits=3):
    if value is None: return '—'
    if isinstance(value, bool): return 'Yes' if value else 'No'
    if isinstance(value, (int,float)): return f'{value:,.{digits}f}'
    return str(value)


class Runner(QThread):
    completed = Signal(object)
    failed = Signal(str)
    def __init__(self, model, spec=None):
        super().__init__(); self.model=deepcopy(model);self.spec=deepcopy(spec)
    def run(self):
        try:self.completed.emit(run_scenario(self.model,self.spec) if self.spec else run_baseline(self.model))
        except Exception as exc:self.failed.emit(str(exc))


def button(text, callback, primary=False):
    b=QPushButton(text);b.setCursor(Qt.PointingHandCursor);b.clicked.connect(callback)
    if primary:b.setObjectName('primary')
    return b


def label(text, name=None):
    w=QLabel(text)
    if name:w.setObjectName(name)
    return w


def table(headers):
    w=QTableWidget(0,len(headers));w.setHorizontalHeaderLabels(headers)
    w.verticalHeader().hide();w.setEditTriggers(QTableWidget.NoEditTriggers)
    w.setSelectionBehavior(QTableWidget.SelectRows);w.setAlternatingRowColors(True)
    w.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    w.setShowGrid(False);w.setWordWrap(False)
    return w


def fill_table(w, rows):
    w.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,value in enumerate(row):
            item=QTableWidgetItem(str(value));item.setToolTip(str(value));w.setItem(i,j,item)
    w.resizeRowsToContents()


class MainWindow(QMainWindow):
    def __init__(self, map_widget=None):
        super().__init__()
        self.setWindowTitle('Texas Data Center Grid Analysis • Project V2')
        self.resize(1560,990);self.setMinimumSize(1100,740)
        self.settings=QSettings('Team11','TexasGridDesktop')
        self.dark=self.settings.value('theme','dark')=='dark'
        self.model=default_model();self.baseline_model=None;self.baseline=None;self.scenario=None
        self.removed_loads=[];self.scenario_spec=None;self.worker=None;self.loading=False;self.log=[];self.dirty=False
        self.map_widget=map_widget
        self.build_ui();self.populate_facilities();self.apply_theme();self.refresh_results()
        self.append_log('Ready. Run a baseline to calculate the local representative network.')

    def build_ui(self):
        root=QWidget();self.setCentralWidget(root);outer=QVBoxLayout(root);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        top=QFrame();top.setObjectName('topbar');tl=QHBoxLayout(top);tl.setContentsMargins(22,13,18,13)
        logo=label('TX','logo');tl.addWidget(logo)
        titles=QVBoxLayout();titles.setSpacing(1);titles.addWidget(label('Texas Data Center Grid Analysis','title'))
        titles.addWidget(label('TEAM 11  /  HOUSTON STUDY AREA','eyebrow'));tl.addLayout(titles);tl.addStretch()
        tl.addWidget(label('●  LOCAL & OFFLINE','badge'))
        self.theme_button=button('Light mode',self.toggle_theme);tl.addWidget(self.theme_button)
        self.open_button=button('Open study',self.open_file);tl.addWidget(self.open_button)
        self.save_button=button('Save study',self.save_file);tl.addWidget(self.save_button)
        self.export_button=button('Export results ↗',self.export_file,True);tl.addWidget(self.export_button)
        outer.addWidget(top)
        banner=QFrame();banner.setObjectName('banner');bl=QHBoxLayout(banner);bl.setContentsMargins(22,6,22,6)
        bl.addWidget(label('Representative network · Assumed connections and equipment parameters · No live telemetry','muted'))
        bl.addStretch();bl.addWidget(button('Sources & assumptions',self.show_sources));outer.addWidget(banner)
        self.main_split=QSplitter(Qt.Horizontal);outer.addWidget(self.main_split,1)
        left=QFrame();left.setObjectName('sidebar');left.setMinimumWidth(275);left.setMaximumWidth(355)
        ll=QVBoxLayout(left);ll.setContentsMargins(16,17,16,12);ll.setSpacing(11)
        ll.addWidget(label('Study setup','section'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame)
        form_widget=QWidget();form=QVBoxLayout(form_widget);form.setContentsMargins(0,0,4,0);form.setSpacing(12)
        form.addWidget(label('01   SELECT A FACILITY','eyebrow'))
        self.facility=QComboBox();self.facility.currentIndexChanged.connect(self.select_facility);form.addWidget(self.facility)
        self.facility_note=label('Synthetic study load · demand estimated','muted');self.facility_note.setWordWrap(True);form.addWidget(self.facility_note)
        fields=QFormLayout();fields.setSpacing(9);fields.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.bus=QComboBox()
        for b in self.model['buses']:
            if b['vn_kv']==138:self.bus.addItem(f"{b['id']}  ·  138 kV",b['id'])
        self.demand=QDoubleSpinBox();self.demand.setRange(0,10000);self.demand.setSuffix(' MW');self.demand.setDecimals(1)
        self.gen=QDoubleSpinBox();self.gen.setRange(0,10000);self.gen.setSuffix(' MW');self.gen.setDecimals(1)
        self.pf=QDoubleSpinBox();self.pf.setRange(.01,1);self.pf.setDecimals(3);self.pf.setSingleStep(.01)
        fields.addRow('Connection bus',self.bus);fields.addRow('Facility demand',self.demand);fields.addRow('Onsite generation',self.gen);fields.addRow('Power factor',self.pf);form.addLayout(fields)
        self.net_label=label('','netcard');self.net_label.setWordWrap(True);form.addWidget(self.net_label)
        self.apply_button=button('Apply to baseline inputs',self.apply_load);form.addWidget(self.apply_button)
        actions=QHBoxLayout()
        self.add_button=button('+ Add load',self.add_load);actions.addWidget(self.add_button)
        self.remove_button=button('Remove load',self.remove_load);actions.addWidget(self.remove_button)
        form.addLayout(actions)
        self.undo_button=button('Undo last removal',self.undo_remove);self.undo_button.setEnabled(False);form.addWidget(self.undo_button)
        help_text=label('Click a load on the map to edit it. Remove deletes it from this study; Undo restores it. Keep at least one load.','muted');help_text.setWordWrap(True);form.addWidget(help_text)
        form.addWidget(label('02   CONFIGURE A SCENARIO','eyebrow'))
        self.kind=QComboBox();self.kind.addItems(KINDS);self.kind.currentIndexChanged.connect(self.inputs_changed);form.addWidget(self.kind)
        self.line=QComboBox()
        for l in self.model['lines']:self.line.addItem(f"{l['id']}  ·  {l['from_bus']} → {l['to_bus']}",l['id'])
        self.line.currentIndexChanged.connect(self.inputs_changed);form.addWidget(self.line)
        self.scenario_hint=label('','hint');self.scenario_hint.setWordWrap(True);form.addWidget(self.scenario_hint)
        form.addWidget(label('03   ANALYSIS SCOPE','eyebrow'))
        scope=label('AC steady-state power flow\nVoltage: 0.95–1.05 pu\nLine / transformer loading: ≤ 100%','muted');scope.setWordWrap(True);form.addWidget(scope)
        fault=button('Fault study · unavailable',self.fault_info);form.addWidget(fault)
        form.addStretch();scroll.setWidget(form_widget);ll.addWidget(scroll,1)
        self.baseline_button=button('▶  Run baseline',self.start_baseline);self.baseline_button.setToolTip('Runs saved baseline inputs. Use Apply to baseline inputs to include changes from the editor.');ll.addWidget(self.baseline_button)
        self.scenario_button=button('▶  Run scenario',self.start_scenario,True);ll.addWidget(self.scenario_button)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setMaximumHeight(4);self.progress.hide();ll.addWidget(self.progress)
        self.run_status=label('No study run yet','muted');self.run_status.setWordWrap(True);ll.addWidget(self.run_status)
        self.main_split.addWidget(left)
        center=QSplitter(Qt.Vertical);self.main_split.addWidget(center)
        map_panel=QFrame();ml=QVBoxLayout(map_panel);ml.setContentsMargins(12,12,12,8);ml.setSpacing(8)
        mt=QHBoxLayout();self.mode=QComboBox();self.mode.addItems(['Baseline','Scenario','Change']);self.mode.currentTextChanged.connect(self.refresh_map);mt.addWidget(self.mode)
        self.map_caption=label('18 buses · 10 modeled loads','muted');mt.addWidget(self.map_caption);mt.addStretch()
        self.search=QLineEdit();self.search.setPlaceholderText('Find a bus, line or facility…');self.search.setMaximumWidth(270);self.search.returnPressed.connect(self.search_map);mt.addWidget(self.search)
        mt.addWidget(button('Find',self.search_map));ml.addLayout(mt)
        self.map=self.map_widget if self.map_widget is not None else GridMap();self.map.selected.connect(self.on_map_selected);ml.addWidget(self.map,1)
        mb=QHBoxLayout();self.gis=QCheckBox('Public GIS routes');self.gis.setChecked(True);self.gis.toggled.connect(self.layers_changed);mb.addWidget(self.gis)
        self.directory=QCheckBox('Directory locations');self.directory.setChecked(True);self.directory.toggled.connect(self.layers_changed);mb.addWidget(self.directory);mb.addStretch()
        for text,fn in [('−',lambda:self.map.zoom_by(1/1.2)),('+',lambda:self.map.zoom_by(1.2)),('Fit',self.map.fit)]:mb.addWidget(button(text,fn))
        ml.addLayout(mb)
        legend=label('● Bus     ▣ Study load     ━ Modeled line     ┄ Outage     ● Violation     ○ Directory only','muted');legend.setWordWrap(True);ml.addWidget(legend)
        center.addWidget(map_panel)
        self.tabs=QTabWidget();center.addWidget(self.tabs)
        self.affected=table(['Component','Issue','Baseline','Scenario','Limit'])
        self.buses=table(['Bus','Base (pu)','Case (pu)','Δ pu','Angle (°)','kV'])
        self.lines=table(['Branch','Base (%)','Case (%)','P (MW)','Q (MVAr)','State'])
        self.loads=table(['Facility','Bus','Gross MW','Onsite MW','Net MW','MVAr']);self.loads.cellClicked.connect(lambda r,c:self.on_map_selected('loads',self.loads.item(r,0).text()))
        self.chart=SweepChart();self.log_view=QTextBrowser()
        for w,n in [(self.affected,'Affected components'),(self.buses,'Bus voltages'),(self.lines,'Branch loading'),(self.loads,'Power usage'),(self.chart,'Load sweep'),(self.log_view,'Run log')]:self.tabs.addTab(w,n)
        self.buses.cellClicked.connect(lambda r,c:self.on_map_selected('buses',self.buses.item(r,0).text()))
        self.lines.cellClicked.connect(lambda r,c:self.on_map_selected('lines' if self.lines.item(r,0).text().startswith('L') else 'transformers',self.lines.item(r,0).text()))
        self.affected.cellClicked.connect(self.select_violation)
        center.setSizes([650,230]);center.setStretchFactor(0,3);center.setStretchFactor(1,1)
        right=QFrame();right.setObjectName('rightbar');right.setMinimumHeight(805)
        rl=QVBoxLayout(right);rl.setContentsMargins(16,18,16,16);rl.setSpacing(15)
        rl.addWidget(label('Results comparison','section'))
        self.summary=table(['Metric','Baseline','Scenario']);self.summary.setFixedHeight(244);rl.addWidget(self.summary)
        self.result_state=label('Run a baseline to begin.','hint');self.result_state.setWordWrap(True);rl.addWidget(self.result_state)
        rl.addWidget(label('Selected component','section'))
        self.selected_title=label('DC_01','selectedtitle');rl.addWidget(self.selected_title)
        self.detail=QTextBrowser();self.detail.setMinimumHeight(180);rl.addWidget(self.detail,1)
        rl.addWidget(label('MODEL CONTEXT','eyebrow'))
        context=label('138 / 345 kV representative network\n10 initial synthetic data-center loads\nPublic Houston geographic snapshot\nV4 simulation engine · AC Newton–Raphson','muted');context.setWordWrap(True);rl.addWidget(context)
        right_scroll=QScrollArea();right_scroll.setWidgetResizable(True);right_scroll.setWidget(right);right_scroll.setMinimumWidth(285);right_scroll.setMaximumWidth(355);right_scroll.setFrameShape(QFrame.NoFrame)
        self.main_split.addWidget(right_scroll);self.main_split.setSizes([300,930,310]);self.main_split.setStretchFactor(1,1)
        self.statusBar().showMessage('Local calculations • No account, API key, browser or internet connection required')
        for w in [self.demand,self.gen,self.pf]:w.valueChanged.connect(self.inputs_changed)
        self.bus.currentIndexChanged.connect(self.inputs_changed)
        save_action=QAction('Save',self);save_action.setShortcut('Ctrl+S');save_action.triggered.connect(self.save_file);self.addAction(save_action)
        open_action=QAction('Open',self);open_action.setShortcut('Ctrl+O');open_action.triggered.connect(self.open_file);self.addAction(open_action)

    def append_log(self,text):
        self.log.append(f"{datetime.now():%H:%M:%S}  {text}")
        self.log_view.setPlainText('\n'.join(self.log));self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def populate_facilities(self, selected=None):
        self.loading=True;self.facility.clear()
        for l in self.model['loads']:self.facility.addItem(l['id']+' · study load',l['id'])
        if selected:self.facility.setCurrentIndex(self.facility.findData(selected))
        self.loading=False;self.select_facility()
        self.remove_button.setEnabled(len(self.model['loads'])>1)

    def select_facility(self,*args):
        if self.loading:return
        key=self.facility.currentData()
        row=next((l for l in self.model['loads'] if l['id']==key),None)
        if not row:return
        self.loading=True;self.bus.setCurrentIndex(self.bus.findData(row['bus_id']));self.demand.setValue(row['p_mw']);self.gen.setValue(row['onsite_gen_mw']);self.pf.setValue(row['pf']);self.loading=False
        self.map.active=('loads',key);self.inputs_changed(mark_dirty=False);self.refresh_detail();self.map.update()

    def form_load(self):
        return dict(id=self.facility.currentData(),bus_id=self.bus.currentData(),p_mw=self.demand.value(),pf=self.pf.value(),onsite_gen_mw=self.gen.value())

    def spec(self):return dict(kind=self.kind.currentText(),line=self.line.currentData(),load=self.form_load())

    def inputs_changed(self,*args,mark_dirty=True):
        if self.loading:return
        p=self.demand.value();q=p*math.tan(math.acos(self.pf.value()))
        self.net_label.setText(f'NET GRID DEMAND\n{p-self.gen.value():,.1f} MW     {q:,.1f} MVAr')
        kind=self.kind.currentText();self.line.setEnabled(kind=='Line outage')
        hints={'Load change':'Uses the facility inputs above, applied to the saved baseline. Other loads stay at baseline values.',
               'Line outage':'Opens the selected modeled line in the saved baseline. Facility fields do not change this case.',
               'Disconnect load':'Disconnects the selected facility and its onsite generator from the saved baseline.',
               'AI training sweep':'16 steady-state points from 0–150% of all baseline gross P/Q loads. Onsite generation stays fixed.'}
        self.scenario_hint.setText(hints[kind])
        if mark_dirty:self.dirty=True
        if self.scenario is not None and self.scenario_spec!=self.spec():
            self.result_state.setText('Inputs changed. Displayed scenario is the last completed run; run again to update.')

    def apply_load(self):
        row=self.form_load()
        try:validate_load(row,self.model)
        except ValueError as exc:self.error(str(exc));return
        target=next(l for l in self.model['loads'] if l['id']==row['id']);target.update(row)
        self.invalidate_baseline('Baseline inputs changed. Run a new baseline.');self.dirty=True

    def invalidate_baseline(self,message):
        self.baseline=self.scenario=self.baseline_model=self.scenario_spec=None
        self.run_status.setText(message);self.refresh_results();self.append_log(message)

    def add_load(self):
        if len(self.model['loads'])>=200:self.error('The desktop study supports up to 200 loads.');return
        dialog=QDialog(self);dialog.setWindowTitle('Add a load');dialog.setMinimumWidth(420)
        layout=QVBoxLayout(dialog)
        note=label('Choose a connection and demand. The new load appears on the map when you click Add load.');note.setWordWrap(True);layout.addWidget(note)
        fields=QFormLayout();layout.addLayout(fields)
        used={l['id'] for l in self.model['loads']};i=1
        while f'DC_{i:02}' in used:i+=1
        name=QLineEdit(f'DC_{i:02}');name.setObjectName('new_load_name')
        bus=QComboBox();bus.setObjectName('new_load_bus')
        for j in range(self.bus.count()):bus.addItem(self.bus.itemText(j),self.bus.itemData(j))
        active=self.map.active
        chosen=active[1] if active and active[0]=='buses' else self.bus.currentData()
        bus.setCurrentIndex(max(0,bus.findData(chosen)))
        demand=QDoubleSpinBox();demand.setObjectName('new_load_demand');demand.setRange(0,10000);demand.setSuffix(' MW');demand.setValue(30)
        gen=QDoubleSpinBox();gen.setRange(0,10000);gen.setSuffix(' MW')
        pf=QDoubleSpinBox();pf.setRange(.01,1);pf.setDecimals(3);pf.setSingleStep(.01);pf.setValue(.95)
        for title,widget in [('Load name',name),('Connection bus',bus),('Demand',demand),('Onsite generation',gen),('Power factor',pf)]:fields.addRow(title,widget)
        error=label('');error.setWordWrap(True);layout.addWidget(error)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('Add load');layout.addWidget(buttons)
        def accept():
            key=name.text().strip()
            if not key or len(key)>40 or key in used:
                error.setText('Choose a unique load name of 1–40 characters.');return
            row=dict(id=key,bus_id=bus.currentData(),p_mw=demand.value(),onsite_gen_mw=gen.value(),pf=pf.value(),value_status='estimated',source_url='User study assumption')
            try:validate_load(row,self.model)
            except ValueError as exc:error.setText(str(exc));return
            self.model['loads'].append(row);self.populate_facilities(key)
            self.invalidate_baseline('Added '+key+'. Run a new baseline.');self.dirty=True;dialog.accept()
        buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def remove_load(self):
        if len(self.model['loads'])<=1:
            self.error('Keep at least one load. Use Disconnect load to study a disconnected facility.');return
        key=self.facility.currentData()
        index=next(i for i,l in enumerate(self.model['loads']) if l['id']==key)
        self.removed_loads.append((index,self.model['loads'].pop(index)))
        self.undo_button.setEnabled(True);self.populate_facilities()
        self.invalidate_baseline('Removed '+key+'. Undo is available. Run a new baseline.');self.dirty=True

    def undo_remove(self):
        if not self.removed_loads:return
        index,row=self.removed_loads[-1]
        if len(self.model['loads'])>=200 or any(l['id']==row['id'] for l in self.model['loads']):
            self.error('Cannot restore: load name is already used or the study has 200 loads.');return
        self.removed_loads.pop();self.model['loads'].insert(index,row)
        self.populate_facilities(row['id']);self.undo_button.setEnabled(bool(self.removed_loads))
        self.invalidate_baseline('Restored '+row['id']+'. Run a new baseline.');self.dirty=True

    def start_baseline(self):
        # Baseline inputs and the scenario editor are independent, including after reopen.
        self.scenario=None;self.scenario_spec=None;self.baseline=None
        self.refresh_results()
        self.baseline_model=deepcopy(self.model);self.start_job(self.baseline_model)

    def start_scenario(self):
        if not self.baseline or not self.baseline['converged']:
            self.error('Run a converged baseline before applying a scenario.');return
        self.scenario=None;self.scenario_spec=deepcopy(self.spec());self.refresh_results()
        self.start_job(self.baseline_model,self.scenario_spec)

    def start_job(self,model,spec=None):
        self.job_is_scenario=spec is not None;self.set_busy(True)
        self.worker=Runner(model,spec);self.worker.completed.connect(self.finish_job);self.worker.failed.connect(self.fail_job)
        self.worker.finished.connect(lambda:self.set_busy(False));self.worker.start()
        self.run_status.setText('Calculating scenario…' if spec else 'Calculating baseline…')

    def set_busy(self,busy):
        for w in [self.baseline_button,self.scenario_button,self.apply_button,self.add_button,self.remove_button,self.undo_button,self.open_button,self.save_button,self.export_button,self.facility,self.bus,self.demand,self.gen,self.pf,self.kind,self.line]:w.setEnabled(not busy)
        self.progress.setVisible(busy)
        if not busy:
            self.line.setEnabled(self.kind.currentText()=='Line outage')
            self.remove_button.setEnabled(len(self.model['loads'])>1)
            self.undo_button.setEnabled(bool(self.removed_loads))

    def finish_job(self,result):
        if self.job_is_scenario:self.scenario=result;self.mode.setCurrentText('Scenario')
        else:self.baseline=result;self.mode.setCurrentText('Baseline')
        self.dirty=True;self.refresh_results();self.run_status.setText(result['message'])
        self.append_log('Engine: '+result.get('engine','unknown'))
        self.append_log(('Scenario' if self.job_is_scenario else 'Baseline')+f": {result['message']} ({result['runtime_seconds']:.3f} s)")
        if 'sweep' in result:self.tabs.setCurrentWidget(self.chart)

    def fail_job(self,message):
        failed=dict(converged=False,status='failed',message=message,totals={},buses={},lines={},loads={},transformers={},violations=[])
        if self.job_is_scenario:self.scenario=failed;self.mode.setCurrentText('Scenario')
        else:self.baseline=failed
        self.refresh_results();self.run_status.setText('Calculation failed');self.append_log('Failed: '+message);self.error(message)

    def refresh_results(self):
        b=self.baseline or {};s=self.scenario or {}
        rows=[]
        for title,key,d in [('Min V (pu)','min_voltage_pu',3),('Line max %','max_loading_percent',1),('Loss MW','losses_mw',3),('Grid MW','grid_supply_mw',1),('Grid MVAr','grid_supply_mvar',1)]:
            rows.append([title,fmt(b.get('totals',{}).get(key),d),fmt(s.get('totals',{}).get(key),d)])
        rows.append(['Violations',len(b['violations']) if b.get('converged') else '—',len(s['violations']) if s.get('converged') else '—'])
        fill_table(self.summary,rows)
        for i in range(self.summary.rowCount()):self.summary.setRowHeight(i,32)
        active=s if self.scenario is not None else b
        violations=active.get('violations',[]);self.display_violations=violations
        vr=[]
        for v in violations:
            sec={'bus':'buses','line':'lines','transformer':'transformers'}[v['type']]
            old=b.get(sec,{}).get(v['id'],{}).get(v['metric'])
            limit='0.95–1.05 pu' if v['type']=='bus' else '≤ 100%'
            vr.append([v['id'],v['message'],fmt(old),fmt(v['value']),limit])
        fill_table(self.affected,vr);self.tabs.setTabText(0,f'Affected ({len(violations)})')
        for i in range(self.affected.rowCount()):
            for j in range(self.affected.columnCount()):self.affected.item(i,j).setForeground(QColor('#ef5660'))
        br=[]
        for bus in self.model['buses']:
            key=bus['id'];old=b.get('buses',{}).get(key,{}).get('vm_pu');row=active.get('buses',{}).get(key,{});new=s.get('buses',{}).get(key,{}).get('vm_pu')
            br.append([key,fmt(old),fmt(new),fmt(new-old if old is not None and new is not None else None),fmt(row.get('va_degree')),fmt(row.get('kv'),1)])
        fill_table(self.buses,br)
        lr=[]
        for sec in ['lines','transformers']:
            for line in self.model.get(sec,[]):
                key=line['id'];row=active.get(sec,{}).get(key,{})
                lr.append([key,fmt(b.get(sec,{}).get(key,{}).get('loading_percent'),1),fmt(s.get(sec,{}).get(key,{}).get('loading_percent'),1),fmt(row.get('p_from_mw',row.get('p_hv_mw')),2),fmt(row.get('q_from_mvar',row.get('q_hv_mvar')),2),('In service' if row.get('in_service',True) else 'Out of service') if row else 'Not run'])
        fill_table(self.lines,lr)
        fill_table(self.loads,[[key,r['bus_id'],fmt(r['p_mw'],1),fmt(r['onsite_gen_mw'],1),fmt(r['net_grid_mw'],1),fmt(r['q_mvar'],1)] for key,r in active.get('loads',{}).items()])
        self.chart.points=s.get('sweep',[]);self.chart.update()
        if active:
            if active.get('converged'):
                self.result_state.setText(f"{len(violations)} limit violation(s) · {active.get('totals',{}).get('unsupplied_buses',0)} unsupplied bus(es)\nSolved in {active.get('runtime_seconds',0):.3f} s")
            else:self.result_state.setText('Calculation unsuccessful. No valid current results. '+active.get('message',''))
        else:self.result_state.setText('No calculated results. Run a baseline to begin.')
        self.refresh_map();self.refresh_detail()

    def refresh_map(self,*args):
        mode=self.mode.currentText();self.map.mode=mode;self.map.baseline=self.baseline
        self.map.result=self.baseline if mode=='Baseline' else self.scenario
        model=deepcopy(self.baseline_model or self.model)
        if mode!='Baseline' and self.scenario and self.scenario.get('converged'):
            for load in model['loads']:
                r=self.scenario.get('loads',{}).get(load['id'])
                if r:load['bus_id']=r['bus_id']
        self.map.model=model
        state='not run' if self.map.result is None else ('solved' if self.map.result.get('converged') else 'failed')
        self.map_caption.setText(f"{len(model['buses'])} buses · {len(model['loads'])} loads · {mode.lower()} {state}")
        self.map.update()

    def refresh_detail(self):
        section,key=self.map.active;self.selected_title.setText(key)
        if section=='directory':
            props=self.map.directory[int(key)]['properties'];self.selected_title.setText('Directory location')
            self.detail.setPlainText('Approximate address location. Not an electrical load or verified grid connection.\n\n'+json.dumps(props,indent=2,ensure_ascii=False));return
        row=next((r for r in self.model.get(section,[]) if r['id']==key),{})
        text=[]
        if section=='loads':text+=['Synthetic study load',f"Assumed connection: {row.get('bus_id','')}",f"Gross demand: {row.get('p_mw',0):.1f} MW",f"Power factor: {row.get('pf',0):.3f}"]
        elif section=='buses':text += [str(row.get('vn_kv',''))+' kV',row.get('substation_name',''),'Electrical parameters assumed']
        else:text += ['Modeled equipment; assumed connectivity',f"{row.get('from_bus',row.get('hv_bus',''))} → {row.get('to_bus',row.get('lv_bus',''))}"]
        for title,result in [('BASELINE',self.baseline),('SCENARIO',self.scenario)]:
            text+=['',title]
            if result and result.get('converged'):
                r=result.get(section,{}).get(key,{})
                for k,v in r.items():text.append(f"{k.replace('_',' ')}: {fmt(v)}")
            else:text.append('No valid result')
        self.detail.setPlainText('\n'.join(text))

    def on_map_selected(self,section,key):
        if section=='loads' and self.worker and self.worker.isRunning():return
        if section=='loads':self.facility.setCurrentIndex(self.facility.findData(key))
        self.map.active=(section,key);self.refresh_detail();self.map.update()

    def select_violation(self,row,col):
        v=self.display_violations[row];self.on_map_selected({'bus':'buses','line':'lines','transformer':'transformers'}[v['type']],v['id'])

    def search_map(self):
        query=self.search.text().strip().lower()
        if not query:return
        for section in ['loads','buses','lines','transformers']:
            for row in self.model.get(section,[]):
                if query in row['id'].lower() or query in row.get('substation_name','').lower():
                    self.on_map_selected(section,row['id']);self.map.fit();self.statusBar().showMessage('Selected '+row['id']);return
        for i,f in enumerate(self.map.directory):
            if query in json.dumps(f['properties']).lower():self.on_map_selected('directory',str(i));self.map.fit();return
        self.statusBar().showMessage('No matching component or directory location.')

    def layers_changed(self):
        self.map.show_gis=self.gis.isChecked();self.map.show_directory=self.directory.isChecked();self.map.update()

    def toggle_theme(self):
        self.dark=not self.dark;self.settings.setValue('theme','dark' if self.dark else 'light');self.apply_theme()

    def apply_theme(self):
        c=DARK if self.dark else LIGHT;self.map.palette_colors=c;self.chart.colors=c;self.map.update();self.chart.update()
        self.theme_button.setText('☀  Light mode' if self.dark else '☾  Dark mode')
        alt='#142a38' if self.dark else '#f1f5f4';hover='#203e50' if self.dark else '#e9eee9'
        self.setStyleSheet(f'''
            QWidget {{ background:{c['panel']}; color:{c['text']}; font-family:'Segoe UI'; font-size:12px; }}
            QMainWindow, QSplitter {{ background:{c['bg']}; }}
            #topbar {{ border-bottom:1px solid {c['border']}; }}
            #banner {{ background:{c['bg']}; border-bottom:1px solid {c['border']}; }}
            #banner QLabel {{ background:transparent; }}
            #sidebar {{ border-right:1px solid {c['border']}; }}
            #rightbar {{ border-left:1px solid {c['border']}; }}
            #title {{ font-size:21px; font-weight:700; }}
            #logo {{ color:{c['accent']}; font-size:24px; font-weight:800; padding-right:10px; }}
            #eyebrow {{ color:{c['muted']}; font-size:10px; font-weight:700; letter-spacing:1px; }}
            #section {{ font-size:18px; font-weight:650; }}
            #muted {{ color:{c['muted']}; font-size:11px; }}
            #badge {{ color:{c['accent']}; font-size:10px; font-weight:700; padding:8px; }}
            #selectedtitle {{ color:{c['accent']}; font-size:22px; font-weight:600; }}
            #netcard {{ background:{alt}; border:1px solid {c['border']}; border-radius:6px; padding:12px; line-height:1.6; font-weight:600; }}
            #hint {{ background:{alt}; border-left:3px solid {c['accent']}; padding:10px; color:{c['muted']}; font-size:11px; }}
            QPushButton {{ border:1px solid {c['border']}; border-radius:5px; padding:8px 11px; font-weight:600; }}
            QPushButton:hover {{ background:{hover}; border-color:{c['accent']}; }}
            QPushButton:disabled {{ color:{c['muted']}; }}
            QPushButton#primary {{ background:{c['accent']}; color:{'#081722' if self.dark else '#ffffff'}; border-color:{c['accent']}; }}
            QComboBox, QDoubleSpinBox, QLineEdit {{ background:{c['bg']}; border:1px solid {c['border']}; border-radius:4px; padding:7px; selection-background-color:{c['accent']}; }}
            QComboBox QAbstractItemView {{ selection-background-color:{hover}; }}
            QTableWidget {{ border:0; alternate-background-color:{alt}; selection-background-color:{hover}; selection-color:{c['text']}; font-size:11px; }}
            QTableWidget::item {{ padding:6px 4px; border-bottom:1px solid {c['border']}; }}
            QHeaderView::section {{ background:{alt}; color:{c['muted']}; border:0; padding:9px 4px; font-size:10px; font-weight:600; }}
            QTabWidget::pane {{ border-top:1px solid {c['border']}; }}
            QTabBar::tab {{ padding:11px 12px; color:{c['muted']}; border-bottom:2px solid transparent; }}
            QTabBar::tab:selected {{ color:{c['accent']}; border-bottom:2px solid {c['accent']}; }}
            QTextBrowser {{ border:1px solid {c['border']}; border-radius:5px; padding:8px; font-size:12px; }}
            QScrollArea {{ border:0; }}
            QScrollBar:vertical {{ background:{c['panel']}; width:9px; }}
            QScrollBar::handle:vertical {{ background:{c['border']}; min-height:24px; border-radius:4px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
            QSplitter::handle {{ background:{c['border']}; width:1px; height:1px; }}
            QStatusBar {{ color:{c['muted']}; border-top:1px solid {c['border']}; font-size:10px; }}
            QProgressBar::chunk {{ background:{c['accent']}; }}
            QToolTip {{ background:{c['panel']}; color:{c['text']}; border:1px solid {c['accent']}; padding:8px; }}
        ''')

    def show_sources(self):
        dialog=QDialog(self);dialog.setWindowTitle('Sources, assumptions & study scope');dialog.resize(850,650)
        layout=QVBoxLayout(dialog);text=QTextBrowser();text.setOpenExternalLinks(False)
        contents=(ROOT/'docs/ASSUMPTIONS.md').read_text(encoding='utf-8')
        contents+='\n\n## Offline desktop additions\n\nThe public Houston GIS snapshot is bundled from BrokenRicey/The-Spongebob-Odyssey, revision '+(ROOT/'data/github_houston/REVISION.txt').read_text().strip()+'.\n\nPurple directory markers are approximate locations, not modeled demand or established electrical connections. Orange study loads are synthetic loads positioned beside their assumed bus. Streets and online tile services are not required. The bay outline is schematic.\n\nA load-change scenario uses the facility form. Outage/disconnection studies use saved baseline load values. The sweep scales all gross P/Q loads and keeps generation constant. Fault, SSO, transient and protection studies are unavailable.\n\n'
        contents+=(ROOT/'data/github_houston/DATA_CENTER_LOCATIONS.md').read_text(encoding='utf-8')
        text.setMarkdown(contents);layout.addWidget(text);layout.addWidget(button('Close',dialog.accept));dialog.exec()

    def fault_info(self):
        QMessageBox.information(self,'Fault study scope','Fault analysis is not available in this model. Validated source short-circuit strength, sequence impedances and fault-method verification are needed. Line outages and load disconnections are available as steady-state scenarios.')

    def error(self,message):QMessageBox.warning(self,'Study needs attention',message)

    def save_file(self):
        path,_=QFileDialog.getSaveFileName(self,'Save study','Houston study.gridstudy','Grid study (*.gridstudy)')
        if not path:return False
        try:
            # Preserve last-run inputs with results; keep the currently edited form separately.
            spec=self.scenario_spec or self.spec()
            save_study(path,self.baseline_model or self.model,spec,self.baseline,self.scenario)
            obj=json.loads(Path(path).read_text(encoding='utf-8'));obj['editor_inputs']=self.spec()
            Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')
            self.dirty=False;self.append_log('Saved study: '+path);return True
        except Exception as exc:self.error(str(exc));return False

    def confirm_discard(self):
        if not self.dirty:return True
        response=QMessageBox.question(self,'Unsaved study','Save this study before continuing?',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        return self.save_file() if response==QMessageBox.Save else response==QMessageBox.Discard

    def open_file(self):
        if not self.confirm_discard():return
        path,_=QFileDialog.getOpenFileName(self,'Open study','','Grid study (*.gridstudy);;JSON (*.json)')
        if not path:return
        try:
            model,spec=load_study(path)
            self.removed_loads.clear();self.undo_button.setEnabled(False);self.model=model;self.populate_facilities(spec['load']['id']);self.loading=True
            self.bus.setCurrentIndex(self.bus.findData(spec['load']['bus_id']));self.demand.setValue(spec['load']['p_mw']);self.gen.setValue(spec['load']['onsite_gen_mw']);self.pf.setValue(spec['load']['pf']);self.kind.setCurrentText(spec['kind']);self.line.setCurrentIndex(self.line.findData(spec['line']));self.loading=False
            self.invalidate_baseline('Study loaded. Saved results are retained in the file; rerun baseline to verify this session.');self.dirty=False;self.inputs_changed(mark_dirty=False)
        except Exception as exc:self.loading=False;self.error(str(exc))

    def export_file(self):
        if not self.baseline:self.error('Run a baseline before exporting results.');return
        path,kind=QFileDialog.getSaveFileName(self,'Export calculated results','Houston results.csv','CSV results (*.csv);;JSON study and results (*.json)')
        if not path:return
        try:
            if kind.startswith('CSV'):export_csv(path,self.baseline,self.scenario)
            else:save_study(path,self.baseline_model,self.scenario_spec or self.spec(),self.baseline,self.scenario)
            self.append_log('Exported results: '+path)
        except Exception as exc:self.error(str(exc))

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.statusBar().showMessage('Wait for the active calculation to finish before closing.');event.ignore();return
        if not self.confirm_discard():event.ignore();return
        event.accept()
