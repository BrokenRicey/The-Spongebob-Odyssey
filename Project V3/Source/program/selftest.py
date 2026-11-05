"""Exercise the actual window, worker and bundled solver without external services."""
import json
import os
import platform
import time
from copy import deepcopy
from pathlib import Path
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from simulation.study import save_study, load_study, export_csv, run_baseline, run_scenario


def run(app,window):
    out=Path(os.environ.get('GRID_SELFTEST_DIR',str(Path.cwd()/'artifacts/desktop-qa')))
    out.mkdir(parents=True,exist_ok=True)
    report={'platform':platform.platform(),'checks':[]}
    def check(condition,message):
        if not condition:raise AssertionError(message)
        report['checks'].append(message)
    def settle():
        until=time.monotonic()+90
        while window.worker and window.worker.isRunning():
            app.processEvents();QTest.qWait(15)
            if time.monotonic()>until:raise TimeoutError('Worker exceeded 90 seconds')
        app.processEvents();QTest.qWait(50)
    try:
        # Fail the test immediately rather than block on a modal error.
        window.error=lambda message: (_ for _ in ()).throw(AssertionError(message))
        window.show();app.processEvents()
        start=time.perf_counter();QTest.mouseClick(window.baseline_button,Qt.LeftButton);settle()
        report['baseline_wall_seconds']=time.perf_counter()-start
        check(window.baseline['converged'],'Native baseline worker converges')
        baseline=deepcopy(window.baseline['totals'])
        check(len(window.baseline['loads'])>=10,'At least 10 modeled loads')
        window.demand.setValue(200);window.gen.setValue(25)
        QTest.mouseClick(window.scenario_button,Qt.LeftButton);settle()
        check(window.scenario['converged'],'Load change converges')
        check(window.scenario['loads']['DC_01']['net_grid_mw']==175,'Form MW and generation reach solver')
        check(window.baseline['totals']==baseline,'Scenario preserves baseline results')
        check(window.summary.item(0,2).text()==f"{window.scenario['totals']['min_voltage_pu']:.3f}",'Displayed result matches solver rounding')
        window.kind.setCurrentText('Line outage');window.line.setCurrentIndex(7)
        QTest.mouseClick(window.scenario_button,Qt.LeftButton);settle()
        check(window.scenario['lines'][window.line.currentData()]['in_service'] is False,'Selected outage opens correct line')
        window.dark=True;window.apply_theme();app.processEvents();window.grab().save(str(out/'dark.png'))
        window.dark=False;window.apply_theme();app.processEvents();window.grab().save(str(out/'light.png'))
        window.resize(1100,740);app.processEvents();QTest.qWait(150);window.grab().save(str(out/'compact.png'));window.resize(1560,990);QTest.qWait(150)
        window.search.setText('BUS_12');window.search_map()
        check(window.map.active==('buses','BUS_12'),'Search selects correct modeled ID')
        window.kind.setCurrentText('Disconnect load');QTest.mouseClick(window.scenario_button,Qt.LeftButton);settle()
        check(window.scenario['loads']['DC_01']['net_grid_mw']==0,'Disconnection removes facility and generator')
        window.kind.setCurrentText('AI training sweep');QTest.mouseClick(window.scenario_button,Qt.LeftButton);settle()
        check(len(window.scenario['sweep'])==16,'All 16 sweep points calculated')
        check(all(x['result']['converged'] for x in window.scenario['sweep']),'Every sweep point converges')
        window.grab().save(str(out/'sweep.png'))
        path=out/'roundtrip.gridstudy'
        save_study(path,window.baseline_model,window.scenario_spec,window.baseline,window.scenario)
        model,spec=load_study(path)
        check(model==window.baseline_model and spec==window.scenario_spec,'Study input round trip preserves all inputs')
        export_csv(out/'results.csv',window.baseline,window.scenario)
        check('sweep' in (out/'results.csv').read_text(encoding='utf-8-sig'),'CSV includes load sweep and numerical results')
        failed_model=deepcopy(model)
        for l in failed_model['loads']:l['p_mw']=10000
        result=run_baseline(failed_model)
        check(not result['converged'] and not result['buses'],'Nonconvergence has no stale numerical data')
        window.job_is_scenario=True;window.finish_job(dict(result,runtime_seconds=0))
        check(window.summary.item(0,2).text()=='—' and window.map.result['converged'] is False,'Failed scenario clears table and map results')
        window.dirty=False
        report['ok']=True
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        window.close();return 0
    except Exception:
        import traceback
        report['ok']=False;report['error']=traceback.format_exc()
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        window.dirty=False
        if window.worker:window.worker.wait(90000)
        return 1
