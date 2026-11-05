# Portable Windows application with embedded Houston map and loopback HTML server.
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

datas=[('data/model/houston_model.json','data/model'),('data/github_houston','data/github_houston'),('docs/ASSUMPTIONS.md','docs'),('map/assets','map/assets')]
datas+=collect_data_files('pandapower')
for name in ['pandapower','pandas','numpy','scipy','deepdiff','geojson','networkx','packaging']:
    datas+=copy_metadata(name)
a=Analysis(['main.py'],pathex=[],binaries=[],datas=datas,
    hiddenimports=['PySide6.QtTest'],
    excludes=['PySide6.QtWebEngineQuick','tkinter','IPython','pytest','fastapi','uvicorn','notebook','jupyter','numba','llvmlite'],
    hookspath=[],hooksconfig={'matplotlib':{'backends':['Agg']}},runtime_hooks=[],noarchive=False)
# Qt uses Windows' unversioned ICU API. Do not let unrelated tools on the build
# machine's PATH supply a same-named, version-suffixed ICU binary (e.g. Poppler).
a.binaries=[entry for entry in a.binaries if entry[0].lower() not in ('icuuc.dll','icuin.dll') and not entry[0].lower().startswith('icudt')]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Texas Grid Analysis',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='Texas Grid Analysis')
