import sys
import os


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont, QFontDatabase
    app=QApplication(sys.argv)
    if '--self-test' in sys.argv and os.environ.get('QT_QPA_PLATFORM')=='offscreen':
        # Qt's offscreen plugin does not enumerate Windows fonts automatically.
        for name in ['segoeui.ttf','segoeuib.ttf','seguisb.ttf','seguisym.ttf']:
            QFontDatabase.addApplicationFont(os.path.join(os.environ.get('WINDIR','C:\\Windows'),'Fonts',name))
    app.setFont(QFont('Segoe UI',10))
    from program.window import MainWindow
    if '--self-test' in sys.argv:
        window=MainWindow()
    else:
        from map.window import HoustonWindow
        window=HoustonWindow()
        if '--map-self-test' in sys.argv:
            from map.selftest import schedule
            schedule(app, window)
    if '--self-test' in sys.argv:
        from program.selftest import run
        return run(app,window)
    window.show()
    return app.exec()


if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception:
        import traceback
        from pathlib import Path
        folder=Path(os.environ.get('GRID_SELFTEST_DIR',str(Path.home()/'Texas Grid Analysis Logs')))
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        if '--self-test' not in sys.argv:
            try:
                from PySide6.QtWidgets import QApplication,QMessageBox
                app=QApplication.instance() or QApplication(sys.argv)
                QMessageBox.critical(None,'Texas Grid Analysis could not start',f'Diagnostic details were saved to {folder / "startup-error.log"}')
            except Exception:pass
        sys.exit(1)
