from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPECPATH).parents[1]
datas = [
    (str(ROOT / "app" / "web" / "dist"), "app/web/dist"),
    (str(ROOT / "alembic"), "alembic"),
]
datas += collect_data_files("alembic")
datas += collect_data_files("docx")
hiddenimports = collect_submodules("uvicorn")
hiddenimports += collect_submodules("sqlalchemy.dialects.sqlite")

a = Analysis(
    [str(ROOT / "app" / "bootstrap.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="weekly-report-assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="weekly-report-assistant",
)
