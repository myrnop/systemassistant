#!/usr/bin/env bash
set -e

PKG_NAME="system-assistant"
VERSION="1.4.0"
APP_ID="io.github.myrnop.SystemAssistant"
BUILD_ROOT="deb-build/${PKG_NAME}_${VERSION}_all"

rm -rf deb-build
mkdir -p "${BUILD_ROOT}/DEBIAN"
mkdir -p "${BUILD_ROOT}/usr/bin"
mkdir -p "${BUILD_ROOT}/usr/share/${PKG_NAME}"
mkdir -p "${BUILD_ROOT}/usr/share/applications"
mkdir -p "${BUILD_ROOT}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${BUILD_ROOT}/usr/share/metainfo"

cat << CTRL > "${BUILD_ROOT}/DEBIAN/control"
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, pciutils, pkexec
Maintainer: MyrnChef <myrnop@users.noreply.github.com>
Description: System maintenance and post-install setup utility
 A native GTK 4 and Libadwaita system maintenance, hardware overview,
 and post-install setup utility for Linux desktops.
CTRL

cp system_assistant.py "${BUILD_ROOT}/usr/share/${PKG_NAME}/system_assistant.py"
chmod 755 "${BUILD_ROOT}/usr/share/${PKG_NAME}/system_assistant.py"

cat << BIN > "${BUILD_ROOT}/usr/bin/system-assistant"
#!/usr/bin/env bash
exec python3 /usr/share/${PKG_NAME}/system_assistant.py "\$@"
BIN
chmod 755 "${BUILD_ROOT}/usr/bin/system-assistant"

cp "${APP_ID}.desktop" "${BUILD_ROOT}/usr/share/applications/${APP_ID}.desktop"
sed -i 's|^Exec=.*|Exec=system-assistant|' "${BUILD_ROOT}/usr/share/applications/${APP_ID}.desktop"

cp "${APP_ID}.png" "${BUILD_ROOT}/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png"
cp "${APP_ID}.metainfo.xml" "${BUILD_ROOT}/usr/share/metainfo/${APP_ID}.metainfo.xml"

dpkg-deb --build --root-owner-group "${BUILD_ROOT}"
mv "deb-build/${PKG_NAME}_${VERSION}_all.deb" "./${PKG_NAME}_${VERSION}_all.deb"
rm -rf deb-build
echo "Built ${PKG_NAME}_${VERSION}_all.deb successfully!"
