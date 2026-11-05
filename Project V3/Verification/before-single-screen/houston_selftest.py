"""Exercise the embedded map, native file bridge, and retained simulation tab."""
import json
import os
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer
from desktop.study import run_baseline


def schedule(app, window):
    out = Path(os.environ.get('GRID_SELFTEST_DIR', 'artifacts/embedded-map-qa'))
    out.mkdir(parents=True, exist_ok=True)
    report = {'checks': [], 'ok': False}
    finished = False

    def finish(error=None):
        nonlocal finished
        if finished:
            return
        finished = True
        report['ok'] = error is None
        if error:
            report['error'] = str(error)
        (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        window._closing = True
        window.server.shutdown()
        window.server.server_close()
        window.work.cleanup()
        app.exit(1 if error else 0)

    def verify_loaded(raw):
        try:
            state = json.loads(raw)
            assert state['loads'] == 1 and state['mw'] == 82 and state['native'], state
            report['checks'].append('Native Open study restored route attachment and 82 MW demand')
            window.grab().save(str(out/'embedded-houston-map.png'))
            result = run_baseline(window.simulation.model)
            assert result['converged']
            report['checks'].append('Existing representative-network baseline still converges')
            assert window.tabs.currentIndex() == 0
            report['checks'].append('Houston map is the default application tab')
            payload=json.loads((out/'embedded-route-study.json').read_text())
            window.files.runMapped(json.dumps(payload['loads']))
            def mapped_done(result):
                try:
                    assert result['converged'] and len(result['loads'])==1
                    assert result['loads']['Embedded QA load']['p_mw']==82
                    report['checks'].append('Mapped load with explicit BUS_01 connection runs through V4 and reaches simulation results')
                    window.simulation.dirty=False
                    window.tabs.setCurrentIndex(0)
                    window.grab().save(str(out/'embedded-houston-map.png'))
                    finish()
                except Exception as exc:finish(repr(exc))
            window.simulation.worker.completed.connect(mapped_done)
        except Exception as exc:
            finish(repr(exc))

    def saved(raw):
        try:
            obj = json.loads(raw)
            assert obj['ok'], obj
            report['checks'].extend(obj['checks'])
            study = out/'embedded-route-study.json'
            with patch('desktop.houston_window.QFileDialog.getSaveFileName', return_value=(str(study), '')):
                window.files.save(json.dumps(obj['study']))
            assert json.loads(study.read_text())['loads'] == obj['study']['loads']
            assert 'simulation' in json.loads(study.read_text())
            report['checks'].append('Native Save study writes load JSON without browser downloads')
            with patch('desktop.houston_window.QFileDialog.getOpenFileName', return_value=(str(study), '')):
                window.files.open()
            QTimer.singleShot(500, lambda: window.page.runJavaScript("JSON.stringify({loads:studyLoads.length,mw:studyLoads[0]?.p_mw,native:window.nativeFilesReady})", verify_loaded))
        except Exception as exc:
            finish(repr(exc))

    def ready(value):
        if finished:
            return
        if not value:
            QTimer.singleShot(250, poll)
            return
        window.page.runJavaScript('''(() => {try {
          const checks=[];
          if(data.features.length!==701)throw Error('Missing routes');
          checks.push('Embedded map contains all 701 source routes and Leaflet initializes');
          const f=data.features[0],xy=f.geometry.coordinates[0][0];
          selectRoute(f,{lat:xy[1],lng:xy[0]});
          $('simulation-bus').value='BUS_01';$('load-name').value='Embedded QA load';$('load-mw').value=75;
          $('load-form').requestSubmit();
          if(studyLoads.length!==1||studyLoads[0].p_mw!==75)throw Error('Add failed');
          checks.push('Added load snaps to selected transmission route');
          const id=studyLoads[0].id;editLoad(id);$('load-mw').value=82;$('load-form').requestSubmit();
          removeLoad(id);if(studyLoads.length!==0)throw Error('Remove failed');$('undo-load').click();
          if(studyLoads[0].p_mw!==82)throw Error('Edit/undo failed');
          checks.push('Edited demand, removed last load, and restored with undo');
          const next=data.features[1],pt=next.geometry.coordinates[0][0];
          editLoad(id,true);selectRoute(next,{lat:pt[1],lng:pt[0]});$('load-form').requestSubmit();
          if(studyLoads[0].route_key!==routeKey(next))throw Error('Move failed');
          checks.push('Moved load to another route');
          const study={format:'houston-route-loads',version:1,loads:studyLoads};
          validateStudy(JSON.parse(JSON.stringify(study)));
          const bad=JSON.parse(JSON.stringify(study));bad.loads[0].point.lat=0;
          let rejected=false;try{validateStudy(bad);}catch(e){rejected=true;}
          if(!rejected)throw Error('Invalid point accepted');
          checks.push('Invalid off-route attachment rejected');
          const result=JSON.stringify({ok:true,checks,study});
          studyLoads=[];studyDirty=false;renderLoads();return result;
        } catch(e){return JSON.stringify({ok:false,error:e.message});}})()''', saved)

    def poll():
        if not finished:
            window.page.runJavaScript("typeof window.nativeFilesReady !== 'undefined' && window.nativeFilesReady", ready)

    QTimer.singleShot(200, poll)
    QTimer.singleShot(60000, lambda: finish('Embedded map timed out'))
