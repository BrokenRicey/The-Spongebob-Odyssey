"""End-to-end checks for the single-screen map/results application."""
import json
import os
import time
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTabBar, QLineEdit, QDoubleSpinBox, QDialogButtonBox


def schedule(app, window):
    out=Path(os.environ.get('GRID_SELFTEST_DIR','artifacts/single-screen-qa'));out.mkdir(parents=True,exist_ok=True)
    report={'checks':[],'ok':False}
    finished=False
    def finish(error=None):
        nonlocal finished
        if finished:return
        finished=True;report['ok']=error is None
        if error:report['error']=str(error)
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        window.simulation.dirty=False
        window._closing=True;window.server.shutdown();window.server.server_close()
        app.exit(1 if error else 0)
    def check(condition,text):
        if not condition:raise AssertionError(text)
        report['checks'].append(text)
    def js(code):
        result=[];window.page.runJavaScript(code,lambda value:result.append(value))
        until=time.monotonic()+10
        while not result:
            app.processEvents();QTest.qWait(10)
            if time.monotonic()>until:raise TimeoutError('JavaScript callback timed out')
        return result[0]
    def settle():
        until=time.monotonic()+60
        while window.simulation.worker and window.simulation.worker.isRunning():
            app.processEvents();QTest.qWait(10)
            if time.monotonic()>until:raise TimeoutError('Simulation timed out')
        app.processEvents();QTest.qWait(100)
    def run():
        sim=window.simulation
        try:
            sim.error=lambda message:(_ for _ in ()).throw(AssertionError(message))
            check(window.centralWidget() is sim and sim.map is window.web,'Houston map occupies the results workspace')
            check(not any(bar.isVisible() for bar in window.findChildren(QTabBar)),'No visible workspace tabs; controls, map and results share one screen')
            check(js('data.features.length')==701,'All 701 Houston transmission features loaded')
            check(js('insideDC.length')==48,'48 directory listings remain available')
            js("selectRoute(data.features[0],{lat:data.features[0].geometry.coordinates[0][0][1],lng:data.features[0].geometry.coordinates[0][0][0]})")
            app.processEvents();QTest.qWait(100)
            check(window.route is not None,'Clicking GIS route activates native attachment controls')
            window.attach_button.click()
            def fill_new_load():
                dialog=app.activeModalWidget()
                dialog.findChild(QLineEdit,'new_load_name').setText('ROUTE_TEST')
                dialog.findChild(QDoubleSpinBox,'new_load_demand').setValue(77)
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
            QTimer.singleShot(50,fill_new_load)
            window.add_load()
            new=next(l for l in sim.model['loads'] if l['id']=='ROUTE_TEST')
            check(new['p_mw']==77 and new['route_key']==window.route['route_key'],'Add load creates an attached load in the same model')
            sim.remove_load();check(not any(l['id']=='ROUTE_TEST' for l in sim.model['loads']),'Remove deletes the shared load')
            sim.undo_remove();check(sim.facility.currentData()=='ROUTE_TEST' and sim.model['loads'][-1]['route_key']==window.route['route_key'],'Undo restores load and route attachment')
            sim.remove_load();sim.facility.setCurrentIndex(0)
            bad=dict(sim.model['loads'][0]);bad['route_point']={'lat':0,'lng':0}
            try:window.validate_attachment(bad);raise AssertionError('Bad attachment accepted')
            except ValueError:report['checks'].append('Off-route attachment rejected by project validator')
            route=sim.model['loads'][0]['route_key']
            check(route==window.route['route_key'],'Selected load attaches directly in the shared simulation model')
            js("pick('loads','DC_02')");QTest.qWait(100);app.processEvents()
            check(sim.facility.currentData()=='DC_02','Map selection updates native load editor')
            sim.facility.setCurrentIndex(0)
            sim.start_baseline();settle()
            check(sim.baseline['converged'],'V4 baseline converges from single-screen controls')
            check(js('latestState.result.converged') is True,'Baseline results reach Houston map overlay')
            check(js('latestState.model.loads[0].route_key')==route,'Result rendering preserves GIS attachment location')
            sim.demand.setValue(120);sim.gen.setValue(20);sim.start_scenario();settle()
            check(sim.scenario['loads']['DC_01']['net_grid_mw']==100,'Scenario editor produces 100 MW net demand')
            check(js("latestState.mode==='Scenario' && latestState.result.loads.DC_01.net_grid_mw===100") is True,'Scenario result updates map without navigating away')
            sim.buses.cellClicked.emit(0,0);QTest.qWait(80)
            check(js("latestState.active[0]==='buses'") is True,'Clicking result row selects its map component')
            window.result_view.setCurrentIndex(2)
            check(sim.tabs.currentIndex()==2 and window.web.isVisible(),'Result selector changes tables while map remains visible')
            sim.kind.setCurrentText('Disconnect load');sim.start_scenario();settle()
            check(js("latestState.result.loads.DC_01.in_service===false") is True,'Disconnection state reaches map marker')
            path=out/'unified.gridstudy'
            with patch('map.window.QFileDialog.getSaveFileName',return_value=(str(path),'')):
                check(window.save_project(),'Unified project saves successfully')
            check(json.loads(path.read_text())['model']['loads'][0]['route_key']==route,'Project persists route attachments with simulation inputs')
            sim.model['loads'][0].pop('route_key');sim.model['loads'][0].pop('route_point');sim.dirty=False
            with patch('map.window.QFileDialog.getOpenFileName',return_value=(str(path),'')):
                window.open_project()
            check(sim.model['loads'][0]['route_key']==route,'Open project restores the shared load and attachment')
            sim.start_baseline();settle();sim.on_map_selected('loads','DC_01')
            sim.dark=False;sim.apply_theme();sim.map.fit();window.result_view.setCurrentIndex(3)
            QTest.qWait(800);app.processEvents();window.grab().save(str(out/'single-screen.png'))
            window.resize(1100,740);QTest.qWait(500);app.processEvents();window.grab().save(str(out/'compact.png'))
            sim.dirty=False;finish()
        except Exception:
            import traceback
            finish(traceback.format_exc())
    def poll():
        if finished:return
        if window.web.ready:run()
        else:QTimer.singleShot(100,poll)
    QTimer.singleShot(100,poll)
    QTimer.singleShot(90000,lambda:finish('Map initialization timed out'))
