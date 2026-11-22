# Maintainer: MyrnChef <myrnop@users.noreply.github.com>
pkgname=system-assistant
pkgver=1.6.0
pkgrel=1
pkgdesc="Modern GTK4 & Libadwaita system maintenance and post-install utility"
arch=('any')
url="https://github.com/myrnop/systemassistant"
license=('GPL-3.0-or-later')
depends=('python' 'python-gobject' 'gtk4' 'libadwaita' 'polkit')
source=("git+https://github.com/myrnop/systemassistant.git#tag=v${pkgver}")
sha256sums=('SKIP')

package() {
  cd "$srcdir/systemassistant"
  install -Dm755 system_assistant.py "$pkgdir/usr/share/system-assistant/system_assistant.py"
  install -dm755 "$pkgdir/usr/bin"
  printf '#!/bin/sh\nexec python3 /usr/share/system-assistant/system_assistant.py "$@"\n' > "$pkgdir/usr/bin/system-assistant"
  chmod 755 "$pkgdir/usr/bin/system-assistant"
  install -Dm644 io.github.myrnop.SystemAssistant.desktop "$pkgdir/usr/share/applications/io.github.myrnop.SystemAssistant.desktop"
  install -Dm644 io.github.myrnop.SystemAssistant.png "$pkgdir/usr/share/icons/hicolor/256x256/apps/io.github.myrnop.SystemAssistant.png"
  install -Dm644 io.github.myrnop.SystemAssistant.metainfo.xml "$pkgdir/usr/share/metainfo/io.github.myrnop.SystemAssistant.metainfo.xml"
}
