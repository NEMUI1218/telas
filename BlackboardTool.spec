# -*- mode: python ; coding: utf-8 -*-
# 打包：python -m PyInstaller BlackboardTool.spec --noconfirm --clean
#
#   Windows → dist/BlackboardTool.exe（单文件）
#   macOS   → dist/BlackboardTool.app
#   Linux   → dist/BlackboardTool（单文件）
#
# 只能在哪个系统上打哪个系统的包。Mac 版可以交给 GitHub Actions（.github/workflows/build.yml）。
import sys

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    # macOS 上单文件的 .app 已被 PyInstaller 弃用，用目录模式再包成 .app
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='BlackboardTool',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='BlackboardTool')
    app = BUNDLE(
        coll,
        name='BlackboardTool.app',
        icon=None,
        bundle_identifier='io.github.blackboardtool',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='BlackboardTool',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
