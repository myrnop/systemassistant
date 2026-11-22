#!/usr/bin/env bash
set -euo pipefail

TOPDIR="$(pwd)/rpmbuild"
rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

cp system_assistant.py \
   io.github.myrnop.SystemAssistant.desktop \
   io.github.myrnop.SystemAssistant.png \
   io.github.myrnop.SystemAssistant.metainfo.xml \
   LICENSE \
   "$TOPDIR/SOURCES/"

rpmbuild --define "_topdir $TOPDIR" -bb system-assistant.spec

RPM_FILE=$(find "$TOPDIR/RPMS/noarch" -name "system-assistant-*.noarch.rpm" | head -n 1)
cp "$RPM_FILE" ./
rm -rf "$TOPDIR"
echo "Built $(basename "$RPM_FILE") successfully!"
