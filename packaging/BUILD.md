# Build the Windows package

The release uses Python 3.12.7 x64, NumPy 1.26.4, SciPy 1.13.1, PyInstaller 6.13.0 and Inno Setup 7.1.0. It bundles the full real and rewired matrices and runs on CPU. No CUDA runtime is shipped.

## Prepare

On Windows x64, install Python 3.12 and the official [Inno Setup compiler](https://jrsoftware.org/isdl.php). In PowerShell, from the repository root:

```powershell
py -3.12 -m venv .build-env
.build-env\Scripts\python.exe -m pip install -r packaging/requirements-build-lock.txt
.build-env\Scripts\python.exe scripts/download_data.py
```

Run `packaging/build.ps1 -CompilerPath 'C:\path\to\InnoSetup\ISCC.exe'`. The default compiler location is `.build-tools/InnoSetup/ISCC.exe` under this repository. Build outputs go to `dist/FlyWire-Pong` and `release/`.

PyInstaller's directory distribution contains required libraries and data; the small inner executable is not a standalone download. Publish the generated `FlyWire-Pong-Setup-1.0.0-Windows-x64.exe` as a Release asset. `-SkipFreeze` rebuilds only the installer. Update the filename and version together in the installer, build script, website and README when making a future release.

## Test

```powershell
dist\FlyWire-Pong\FlyWire-Pong.exe --self-test results/frozen-selftest.json
```

Validate a real install, startup, both graph variants, the anatomy page, duplicate launch and uninstall on a Windows test environment. The published 1.0.0 installer passed those checks on the Windows 11 build computer, including a self-test with Python/Conda removed from the child PATH and external proxy access unavailable. This does not certify every Windows 10/11 device.

The app listens only on `127.0.0.1:8751`. `--no-browser`, `--port`, `--ready-file` and `--shutdown` support local checks. A hidden page pauses simulation after 15 seconds without API contact; the server exits after ten minutes. Logs go to `%LOCALAPPDATA%/FlyWirePong/logs/desktop.log`.

The release is unsigned. SHA-256 checks file integrity, not publisher identity. Python and NumPy/SciPy library license metadata are bundled; FlyWire source terms remain separate from original code terms.
