#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$(uname -s)" == "Linux" ]] || { echo "必须在 Linux 本机构建" >&2; exit 1; }
[[ "$(uname -m)" == "x86_64" ]] || { echo "必须在 x86-64 Linux 构建" >&2; exit 1; }
command -v dpkg-deb >/dev/null || { echo "缺少 dpkg-deb" >&2; exit 1; }

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.1.0"
PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3.12)"

"$PYTHON" "$ROOT/scripts/build_frontend.py"
"$PYTHON" "$ROOT/scripts/build_backend.py"
BUNDLE="$ROOT/dist/weekly-report-assistant"
file "$BUNDLE/weekly-report-assistant" | grep -q 'ELF 64-bit.*x86-64' || {
    echo "bundle 不是 Linux x86-64 ELF" >&2; exit 1;
}

BUILD_ROOT="$ROOT/build/linux-package"
DEB_ROOT="$BUILD_ROOT/deb"
TAR_ROOT="$BUILD_ROOT/weekly-report-assistant-$VERSION"
OUTPUT="$ROOT/dist/installers"
rm -rf "$BUILD_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN" "$DEB_ROOT/opt/weekly-report-assistant" \
    "$DEB_ROOT/lib/systemd/system" "$DEB_ROOT/etc/weekly-report-assistant" "$OUTPUT"
cp -a "$BUNDLE/." "$DEB_ROOT/opt/weekly-report-assistant/"
cp "$ROOT/packaging/linux/weekly-report-assistant.service" \
    "$DEB_ROOT/lib/systemd/system/weekly-report-assistant.service"
cp "$ROOT/packaging/linux/environment" "$DEB_ROOT/etc/weekly-report-assistant/environment"
cp "$ROOT/packaging/linux/preinst" "$ROOT/packaging/linux/postinst" \
    "$ROOT/packaging/linux/prerm" "$ROOT/packaging/linux/postrm" "$DEB_ROOT/DEBIAN/"
cp "$ROOT/packaging/linux/conffiles" "$DEB_ROOT/DEBIAN/conffiles"
chmod 0755 "$DEB_ROOT/DEBIAN/preinst" "$DEB_ROOT/DEBIAN/postinst" \
    "$DEB_ROOT/DEBIAN/prerm" "$DEB_ROOT/DEBIAN/postrm"
INSTALLED_SIZE="$(du -sk "$DEB_ROOT/opt" | awk '{print $1}')"
sed -e "s/@VERSION@/$VERSION/g" -e "s/@INSTALLED_SIZE@/$INSTALLED_SIZE/g" \
    "$ROOT/packaging/linux/control" > "$DEB_ROOT/DEBIAN/control"

DEB_PATH="$OUTPUT/weekly-report-assistant_${VERSION}_amd64.deb"
dpkg-deb --root-owner-group --build "$DEB_ROOT" "$DEB_PATH"

mkdir -p "$TAR_ROOT/bundle"
cp -a "$BUNDLE/." "$TAR_ROOT/bundle/"
cp "$ROOT/packaging/linux/weekly-report-assistant.service" \
    "$ROOT/packaging/linux/environment" "$ROOT/packaging/linux/install.sh" \
    "$ROOT/packaging/linux/uninstall.sh" "$TAR_ROOT/"
chmod 0755 "$TAR_ROOT/install.sh" "$TAR_ROOT/uninstall.sh"
TAR_PATH="$OUTPUT/weekly-report-assistant-${VERSION}-linux-x64.tar.gz"
tar -czf "$TAR_PATH" -C "$BUILD_ROOT" "weekly-report-assistant-$VERSION"

echo "LINUX_BUILD_OK deb=$DEB_PATH tar=$TAR_PATH"
