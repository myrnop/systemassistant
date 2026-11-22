Name:           system-assistant
Version:        1.5.0
Release:        1%{?dist}
Summary:        Modern GTK4 & Libadwaita system maintenance and post-install utility
License:        GPL-3.0-or-later
URL:            https://github.com/myrnop/systemassistant
BuildArch:      noarch

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       polkit

%description
A native GTK4 and Libadwaita utility to update system packages and Flatpaks,
mute the hardware PC speaker module, configure distro repositories and codecs,
and install essential desktop tools across Fedora, Ubuntu/Debian, and Arch Linux.

%install
mkdir -p %{buildroot}%{_datadir}/system-assistant
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/512x512/apps
mkdir -p %{buildroot}%{_metainfodir}
mkdir -p %{buildroot}%{_licensedir}/%{name}

install -m 0755 %{_sourcedir}/system_assistant.py %{buildroot}%{_datadir}/system-assistant/system_assistant.py
cat << 'WRAPPER' > %{buildroot}%{_bindir}/system-assistant
#!/bin/sh
exec python3 /usr/share/system-assistant/system_assistant.py "$@"
WRAPPER
chmod 0755 %{buildroot}%{_bindir}/system-assistant

install -m 0644 %{_sourcedir}/io.github.myrnop.SystemAssistant.desktop %{buildroot}%{_datadir}/applications/io.github.myrnop.SystemAssistant.desktop
install -m 0644 %{_sourcedir}/io.github.myrnop.SystemAssistant.png %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/io.github.myrnop.SystemAssistant.png
install -m 0644 %{_sourcedir}/io.github.myrnop.SystemAssistant.metainfo.xml %{buildroot}%{_metainfodir}/io.github.myrnop.SystemAssistant.metainfo.xml
install -m 0644 %{_sourcedir}/LICENSE %{buildroot}%{_licensedir}/%{name}/LICENSE

%files
%license LICENSE
%{_bindir}/system-assistant
%{_datadir}/system-assistant/system_assistant.py
%{_datadir}/applications/io.github.myrnop.SystemAssistant.desktop
%{_datadir}/icons/hicolor/512x512/apps/io.github.myrnop.SystemAssistant.png
%{_metainfodir}/io.github.myrnop.SystemAssistant.metainfo.xml

%changelog
* Sun Nov 22 2026 MyrnChef <myrnop@users.noreply.github.com> - 1.5.0-1
- Release v1.5.0 with Fedora, Ubuntu/Debian, and Arch Linux support
