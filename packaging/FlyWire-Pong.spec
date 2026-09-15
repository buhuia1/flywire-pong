# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parent
assets = {
 'data': ['flywire_graph.npz','rewired_graph.npz','manifest.json','rewired_manifest.json',
          'anatomy_indices.npz','anatomy_manifest.json','DATA_LICENSE.md'],
 'results': ['pong_readout.npz','rewired_readout.npz','direct_readout.npz','training.json',
             'benchmark.json','cpu_backend_reference.npz'],
 'web': ['index.html','app.js','motion.js','style.css','brain.html','brain.js','brain.css','brain-data.json'],
}
datas = [(str(root/folder/file),folder) for folder,files in assets.items() for file in files]
datas += [(str(root/'THIRD_PARTY.md'),'.'),(str(root/'packaging/使用说明.txt'),'.'),
          (str(root/'packaging/LICENSE_PYTHON.txt'),'licenses'),
          (str(root/'电子果蝇_从接线图到游戏.md'),'.')]
datas += copy_metadata('numpy') + copy_metadata('scipy')
a=Analysis([str(root/'desktop_app.py')],pathex=[str(root)],binaries=[],datas=datas,
           hiddenimports=['scipy.sparse'],hookspath=[],hooksconfig={},runtime_hooks=[],
           excludes=['torch','pandas','matplotlib','IPython','pytest','tkinter'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='FlyWire-Pong',debug=False,
        bootloader_ignore_signals=False,strip=False,upx=False,console=False,
        version=str(root/'packaging/version.txt'))
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='FlyWire-Pong')
