#!/bin/bash
# Build a fast-starting, self-contained macOS .app bundle.
set -euo pipefail

cd "$(dirname "$0")"
PY="${PYTHON:-.venv/bin/python}"
PYINSTALLER="${PYINSTALLER:-.venv/bin/pyinstaller}"

[ -x "$PY" ] || { echo "Missing $PY. Create .venv and install requirements.txt first."; exit 1; }
[ -x "$PYINSTALLER" ] || { echo "Missing $PYINSTALLER."; exit 1; }

VERSION=$("$PY" -c "from blipkit import __version__; print(__version__)")
ARCH=$(uname -m)
rm -rf build dist/Blipkit.app dist/Blipkit

"$PYINSTALLER" main.py \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name Blipkit \
  --paths src \
  --osx-bundle-identifier com.blipkit.desktop \
  --collect-all customtkinter \
  --hidden-import soundfile \
  --hidden-import lameenc \
  --exclude-module matplotlib \
  --exclude-module scipy \
  --exclude-module pandas \
  --exclude-module test \
  --exclude-module tests \
  --distpath dist \
  --workpath build \
  --specpath build

APP="dist/Blipkit.app"
[ -d "$APP" ] || { echo "Build failed: $APP was not created."; exit 1; }
codesign --force --deep --sign - "$APP"

ZIP="dist/Blipkit-${VERSION}-macos-${ARCH}.zip"
rm -f "$ZIP"
(cd dist && /usr/bin/ditto -c -k --sequesterRsrc --keepParent \
  "Blipkit.app" "$(basename "$ZIP")")
shasum -a 256 "$ZIP" > dist/checksums.txt

echo "Built $APP"
echo "Archive $ZIP"
