#!/usr/bin/env bash
# Build dist/drawapp_<version>_<arch>.deb
#
#   packaging/build_deb.sh            # for this machine's CPU
#   packaging/build_deb.sh amd64      # for Intel/AMD PCs
#   packaging/build_deb.sh arm64
#
# The package carries its own copy of Qt (PySide6) under /opt/drawapp, because
# Ubuntu does not ship PySide6. It only needs the system's python3.
set -euo pipefail

cd "$(dirname "$0")/.."
ARCH="${1:-$(dpkg --print-architecture)}"
case "$ARCH" in
  arm64) PLATFORM="aarch64-manylinux_2_39"; LIBC="2.39" ;;
  amd64) PLATFORM="x86_64-manylinux_2_34";  LIBC="2.34" ;;
  *) echo "unsupported architecture: $ARCH (use amd64 or arm64)" >&2; exit 1 ;;
esac
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)"
BUILD="build/deb-$ARCH"
ROOT="$BUILD/root"
LIB="$ROOT/opt/drawapp/lib"

rm -rf "$BUILD"
mkdir -p "$LIB" "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/doc/drawapp" dist

# Dependencies, pinned to the versions in uv.lock, for the target CPU.
uv export --no-dev --no-emit-project --no-hashes --format requirements-txt -o "$BUILD/requirements.txt" >/dev/null
uv pip install --quiet --target "$LIB" --python /usr/bin/python3 \
  --python-platform "$PLATFORM" --only-binary :all: -r "$BUILD/requirements.txt"
python3 packaging/prune_qt.py "$LIB"
cp -r src/drawapp "$LIB/drawapp"
find "$LIB" -name __pycache__ -type d -prune -exec rm -rf {} +

cat > "$ROOT/usr/bin/drawapp" <<'EOF'
#!/bin/sh
# DRAWAPP_LAUNCHER tells the app how to start itself at login.
exec env DRAWAPP_LAUNCHER=/usr/bin/drawapp PYTHONPATH=/opt/drawapp/lib /usr/bin/python3 -m drawapp "$@"
EOF
chmod 755 "$ROOT/usr/bin/drawapp"

cp packaging/drawapp.desktop "$ROOT/usr/share/applications/drawapp.desktop"
cp packaging/drawapp.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/drawapp.svg"
cp README.md "$ROOT/usr/share/doc/drawapp/README.md"

SIZE_KB="$(du -sk "$ROOT" | cut -f1)"
cat > "$ROOT/DEBIAN/control" <<EOF
Package: drawapp
Version: $VERSION
Architecture: $ARCH
Maintainer: Aman Gupta <amangupta0044@gmail.com>
Installed-Size: $SIZE_KB
Depends: python3 (>= 3.12), libc6 (>= $LIBC), libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-keysyms1, libxcb-image0, libxcb-render-util0, libxcb-shape0, libxcb-xkb1, libxcb-randr0, libxcb-xfixes0, libxcb-sync1, libxcb-shm0, libxcb-xinput0, libx11-xcb1, libegl1, libgl1, libfontconfig1, libfreetype6, libdbus-1-3
Section: graphics
Priority: optional
Description: Draw over any app with a pen tablet
 Touch the pen to the tablet and draw on top of whatever is on screen:
 pen, highlighter, arrows, sticky notes and screenshots. Needs an X11
 session; it does not work on Wayland.
EOF

cat > "$ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
# Precompile our own code so the first start is quick.
python3 -m compileall -q /opt/drawapp/lib/drawapp /opt/drawapp/lib/Xlib >/dev/null 2>&1 || true
EOF
cat > "$ROOT/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
find /opt/drawapp -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
EOF
chmod 755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/prerm"

find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT/opt" "$ROOT/usr/share" -type f -exec chmod 644 {} +
find "$LIB" -name '*.so*' -exec chmod 755 {} +

OUT="dist/drawapp_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$ROOT" "$OUT" >/dev/null
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
