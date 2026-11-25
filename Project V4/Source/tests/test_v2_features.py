import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from copy import deepcopy
from unittest.mock import patch
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLineEdit, QDoubleSpinBox
from PySide6.QtCore import QTimer
from simulation import TL_Senior_Simulation_V4 as v4
from program.window import MainWindow
from simulation.study import run_baseline, save_study, load_study

def test_map_really_calls_v4():
    from simulation.study import default_model
    with patch.object(v4,'run_power_flow',wraps=v4.run_power_flow) as solver:
        result=run_baseline(default_model())
        assert solver.call_count==1
        assert result['converged']
        assert result['engine']=='TL_Senior_Simulation_V4.run_power_flow'

def test_load_dialog_remove_undo_and_save(tmp_path):
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    original=deepcopy(w.model)
    def fill():
        d=app.activeModalWidget()
        assert isinstance(d,QDialog)
        d.findChild(QLineEdit,'new_load_name').setText('TEST_LOAD')
        d.findChild(QDoubleSpinBox,'new_load_demand').setValue(77)
        d.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
    QTimer.singleShot(50,fill)
    w.add_load()
    assert w.facility.currentData()=='TEST_LOAD'
    assert len(w.model['loads'])==11
    result=run_baseline(w.model)
    assert result['loads']['TEST_LOAD']['p_mw']==77
    w.baseline=result
    w.remove_load()
    assert w.baseline is None
    assert w.model==original
    w.undo_remove()
    assert w.facility.currentData()=='TEST_LOAD'
    path=tmp_path/'v2.gridstudy'
    save_study(path,w.model,w.spec())
    assert load_study(path)[0]==w.model
    while len(w.model['loads'])>1:w.remove_load()
    assert not w.remove_button.isEnabled()
    assert run_baseline(w.model)['converged']
    w.dirty=False;w.close()
