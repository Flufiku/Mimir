# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Find llama-cpp-python library path
try:
    import llama_cpp
    llama_cpp_path = os.path.dirname(llama_cpp.__file__)
    llama_lib_path = os.path.join(llama_cpp_path, 'lib')
except ImportError:
    llama_lib_path = None

# Add llama-cpp lib directory if it exists
binaries = []
if llama_lib_path and os.path.exists(llama_lib_path):
    for file in os.listdir(llama_lib_path):
        if file.endswith(('.dll', '.so', '.dylib')):
            binaries.append((os.path.join(llama_lib_path, file), 'llama_cpp/lib'))

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=[('src/config.json', '.'), ('src/assets', 'assets')],
    hiddenimports=[
        'torch', 
        'transformers', 
        'llama_cpp', 
        'llama_cpp._ctypes_extensions',
        'faster_whisper', 
        'pyautogui', 
        'pystray', 
        'keyboard', 
        'sounddevice',
        'PIL._tkinter_finder',
        'pkg_resources.extern'
    ],
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
    a.binaries,
    a.datas,
    [],
    name='Mimir',
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
