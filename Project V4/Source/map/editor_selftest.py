"""Exercise the real Qt/Leaflet bridge and baseline/scenario workflow."""
import json
import os
import time
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest


def schedule(app, window):
    out = Path(os.environ.get('GRID_SELFTEST_DIR', 'artifacts/v4-desktop'))
    out.mkdir(parents=True, exist_ok=True)
    report = {'ok': False, 'checks': []}

    def check(condition, text):
        if not condition:
            raise AssertionError(text)
        report['checks'].append(text)
        print('CHECK:', text, flush=True)

    def until(predicate, seconds=45):
        deadline = time.monotonic()+seconds
        while not predicate():
            app.processEvents()
            time.sleep(.01)  # Let the Python solver thread acquire the GIL.
            if time.monotonic() > deadline:
                raise TimeoutError('Desktop condition timed out')
        app.processEvents()
        QTest.qWait(150)

    def js(code):
        print('JS:', code[:160], flush=True)
        values = []
        window.page.runJavaScript(code, lambda value: values.append(value))
        until(lambda: bool(values), 10)
        return values[0]

    def action(command):
        window.bridge.action(json.dumps(command))
        app.processEvents()
        QTest.qWait(120)

    def click_equipment(key):
        needle = '<strong>'+key+'</strong>'
        return js("(()=>{const target=Object.values(editorMap._layers).find(x=>x.getTooltip?.()?.getContent()?.startsWith("+json.dumps(needle)+"));if(!target)return false;target.fire('click',{});return true})()")

    def run():
        try:
            until(lambda: window.ready)
            check(js("document.title.includes('V4')"), 'Project V4 embedded page loaded')
            check(len(window.study.baseline_model['lines']) > 700, 'Houston route network is active')
            check(js("Object.values(editorMap._layers).filter(x=>x instanceof L.Polyline).length > 700"), 'Houston network rendered in Leaflet')
            window.grab().save(str(out/'01-baseline-editor.png'))
            js("document.getElementById('run-button').click()")
            until(lambda: not window.busy)
            check(window.study.baseline and window.study.baseline['converged'], 'Manual baseline button calculated full Houston network')
            baseline_model = deepcopy(window.study.baseline_model)
            baseline_result = deepcopy(window.study.baseline)
            js("document.getElementById('case-scenario').click()")
            check(window.case == 'scenario', 'Scenario tab creates independent baseline copy')
            check(not window.study._undo['scenario'], 'First scenario fork has no phantom undo edit')
            line = window.study.scenario_model['lines'][0]
            check(click_equipment(line['id']), 'Transmission route has a full-width interactive selection layer')
            until(lambda: window.selected and window.selected['id'] == line['id'])
            js("document.querySelector('#selection-content .disable').click()")
            until(lambda: not window.study.scenario_model['lines'][0].get('in_service', True))
            check(not window.study.scenario_model['lines'][0]['in_service'], 'Clicking Disable in the line inspector edits the solver network')
            js("document.getElementById('undo-button').click()")
            until(lambda: window.study.scenario_model['lines'][0].get('in_service', True))
            load = window.study.scenario_model['loads'][0]
            action(dict(type='select', section='buses', id=load['bus_id']))
            check(load['bus_id'] in js("document.getElementById('selection-title').textContent"), 'Map selection populates equipment inspector')
            action(dict(type='toggle', section='buses', id=load['bus_id']))
            supply = window.study.scenario_model['sources'][-1]
            bus = next(b for b in window.study.scenario_model['buses'] if b['id'] == supply['bus_id'])
            js("document.querySelector('[data-tool=load]').click();editorMap.fire('click',{latlng:L.latLng("+str(bus['lat'])+','+str(bus['lon'])+")});true")
            check(js("document.getElementById('editor-dialog').open"), 'Plus tool and map placement open data-center dialog')
            js("document.querySelector('#dialog-fields [name=name]').value='QA_DATA_CENTER';document.querySelector('#dialog-fields [name=p_mw]').value='2';document.getElementById('dialog-submit').click()")
            until(lambda: any(x['id'] == 'QA_DATA_CENTER' for x in window.study.scenario_model['loads']))
            check(any(x['id'] == 'QA_DATA_CENTER' for x in window.study.scenario_model['loads']), 'Placed data center joins network through bridge')
            check(window.study.baseline_model == baseline_model and window.study.baseline == baseline_result, 'Combined edits preserve baseline inputs and results')
            check(window.study.scenario is None and not window.busy, 'Editing does not automatically run simulation')
            js("document.getElementById('run-button').click()")
            until(lambda: not window.busy)
            result = window.study.scenario
            check(result and result['converged'], 'Edited scenario converges')
            check(not result['loads'][load['id']]['supplied'], 'Disabled bus removes supply to attached load')
            check(result['totals']['unserved_load_mw'] >= load['p_mw'], 'Unserved demand appears in comparison')
            check(window.state()['comparison_ready'], 'Baseline/scenario comparison is current')
            check('MW' in js("document.getElementById('metrics-body').textContent"), 'Calculated metrics reach visible comparison table')
            window.grab().save(str(out/'02-scenario-results.png'))
            action(dict(type='undo'))
            check(not any(x['id'] == 'QA_DATA_CENTER' for x in window.study.scenario_model['loads']), 'Undo reverses latest cumulative edit')
            action(dict(type='redo'))
            check(any(x['id'] == 'QA_DATA_CENTER' for x in window.study.scenario_model['loads']), 'Redo restores data center')
            js("document.querySelector('[data-tool=bus]').click();editorMap.fire('click',{latlng:L.latLng("+str(bus['lat']+.005)+','+str(bus['lon']+.005)+")});true")
            js("document.querySelector('#dialog-fields [name=name]').value='QA_BUS';document.getElementById('dialog-submit').click()")
            until(lambda: any(x['id']=='QA_BUS' for x in window.study.scenario_model['buses']))
            check(True, 'Plus Bus places an editable bus')
            js("document.querySelector('[data-tool=line]').click()")
            check(click_equipment(supply['id']), 'Draw tool can select the bus underneath a supply symbol')
            click_equipment('QA_BUS')
            until(lambda: any(x.get('to_bus')=='QA_BUS' for x in window.study.scenario_model['lines']))
            added_line = next(x for x in window.study.scenario_model['lines'] if x['to_bus']=='QA_BUS')
            check(added_line['from_bus']==bus['id'], 'Draw Line joins the selected buses')
            js("document.querySelector('[data-tool=move]').click()")
            action(dict(type='select',section='buses',id='QA_BUS'))
            js("(()=>{const m=Object.values(editorMap._layers).find(x=>x.options?.icon?.options?.className==='bus-drag');m.setLatLng(["+str(bus['lat']+.006)+','+str(bus['lon']+.006)+"]);m.fire('dragend',{});return true})()")
            until(lambda: abs(next(x for x in window.study.scenario_model['buses'] if x['id']=='QA_BUS')['lat']-(bus['lat']+.006))<1e-8)
            check(True, 'Dragging a bus updates connected route geometry')
            action(dict(type='select',section='loads',id='QA_DATA_CENTER'))
            js("(()=>{const m=Object.values(editorMap._layers).find(x=>x.options?.icon?.options?.className?.includes('load-marker selected'));m.setLatLng(["+str(bus['lat']+.00001)+','+str(bus['lon']+.00001)+"]);m.fire('dragend',{});return true})()")
            until(lambda: abs(next(x for x in window.study.scenario_model['loads'] if x['id']=='QA_DATA_CENTER')['lat']-(bus['lat']+.00001))<1e-8)
            check(True, 'Dragging a data center reconnects its electrical load')
            before = deepcopy(window.study.scenario_model)
            action(dict(type='update', section='loads', id='QA_DATA_CENTER', values={'p_mw': -1}))
            check(window.study.scenario_model == before, 'Invalid edit rejected atomically')
            action(dict(type='reset_scenario'))
            check(window.study.scenario_model == baseline_model, 'Reset restores full baseline topology')
            action(dict(type='undo'))
            check(window.study.scenario_model == before, 'Scenario reset is undoable')
            path = out/'verified-project.gridstudy'
            check(window.save_project(str(path)), 'Both edited networks save successfully')
            window.open_project(str(path))
            check(window.study.scenario_model == before, 'Project reload restores cumulative edits')
            check(window.study.baseline is None and window.study.scenario is None, 'Reload clears archived result freshness')
            window.send_state()
            window.resize(1100, 740)
            QTest.qWait(300)
            check(js('document.documentElement.scrollWidth <= window.innerWidth+1'), 'Minimum-size layout has no page overflow')
            window.grab().save(str(out/'03-minimum-layout.png'))
            report.update(ok=True, baseline_totals=baseline_result['totals'], scenario_totals=result['totals'])
        except Exception as exc:
            import traceback
            report['error'] = str(exc)
            report['traceback'] = traceback.format_exc()
            window.grab().save(str(out/'failure.png'))
        finally:
            (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            window.dirty = False
            window.shutdown()
            app.exit(0 if report['ok'] else 1)

    QTimer.singleShot(700, run)
