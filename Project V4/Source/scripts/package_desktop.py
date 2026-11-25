"""Bundle a tested portable build, developer source, attribution and hashes."""
import hashlib
import importlib.metadata
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'dist/Texas Grid Analysis'
OUT=ROOT.parent/'output'


def main():
    if not (APP/'Texas Grid Analysis.exe').exists():raise RuntimeError('Build TexasGrid.spec first')
    report=ROOT/'artifacts/packaged-final-qa/report.json'
    if not report.exists() or not json.loads(report.read_text())['ok']:
        raise RuntimeError('Packaged executable must pass self-test before release')
    OUT.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'DESKTOP-README.md',APP/'START-HERE.md')
    shutil.copy2(report,APP/'VERIFICATION.json')
    from simulation.study import default_model, run_baseline, run_scenario, save_study
    model=default_model()
    example={'kind':'Load change','line':'L08','load':dict(model['loads'][0],p_mw=600,bus_id='BUS_12')}
    baseline=run_baseline(model);scenario=run_scenario(model,example)
    assert baseline['converged'] and scenario['converged'] and scenario['violations']
    examples=APP/'Example studies';examples.mkdir(exist_ok=True)
    save_study(examples/'High demand at Bus 12.gridstudy',model,example,baseline,scenario)
    licenses=APP/'THIRD-PARTY-LICENSES';licenses.mkdir(exist_ok=True)
    shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt',licenses/'Python-LICENSE.txt')
    for dist in importlib.metadata.distributions():
        name=dist.metadata['Name']
        for entry in dist.files or []:
            # Preserve upstream notices without attempting to rewrite license text.
            if any(word in str(entry).lower() for word in ['license','copying','notice']) and '..' not in entry.parts:
                source=Path(dist.locate_file(entry))
                if source.is_file():
                    target=licenses/name/str(entry);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    (APP/'THIRD-PARTY-NOTICES.txt').write_text(
        'This portable application bundles Python, PySide6/Qt, pandapower, NumPy, SciPy, pandas and their dependencies.\n'
        'Upstream license and notice files are preserved in THIRD-PARTY-LICENSES and _internal package metadata.\n'
        'Qt libraries are dynamically loaded from _internal/PySide6 and may be replaced with compatible builds.\n'
        'PySide6 / Qt source and licensing: https://code.qt.io/ and https://www.qt.io/licensing/\n'
        'Python source: https://www.python.org/downloads/source/\n'
        'pandapower source: https://github.com/e2nIEE/pandapower\n'
        'The companion source archive contains the application code and reproducible build specification.\n'
        'Geographic snapshot provenance is recorded in _internal/data/github_houston.\n',encoding='utf-8')
    release=OUT/'Texas-Grid-Analysis-Windows-x64.zip'
    with zipfile.ZipFile(release,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in APP.rglob('*'):
            if p.is_file():z.write(p,Path(APP.name)/p.relative_to(APP))
    source=OUT/'Texas-Grid-Analysis-Source.zip'
    folders=['program','simulation','map','tests','scripts','data','app','docs']
    files=['main.py','desktop_launcher.py','TexasGrid.spec','requirements.txt','requirements-desktop.txt','DESKTOP-README.md']
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in files:z.write(ROOT/name,name)
        for folder in folders:
            for p in (ROOT/folder).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and not (ROOT/'map/output') in p.parents:z.write(p,p.relative_to(ROOT))
    checksums=[]
    for path in [release,source]:
        digest=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
        checksums.append(digest+'  '+path.name)
    (OUT/'SHA256SUMS.txt').write_text('\n'.join(checksums)+'\n',encoding='utf-8')
    shutil.copy2(ROOT/'DESKTOP-README.md',OUT/'START-HERE.md')
    print(json.dumps({p.name:p.stat().st_size for p in [release,source]},indent=2))


if __name__=='__main__':main()
