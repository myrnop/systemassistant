# System Assistant

A native GTK 4 and Libadwaita system maintenance and post-install setup utility for Linux desktops.

![System Assistant Screenshot](Pic1.png?v=1.4.0)

## Features
- **Update System & Flatpak Apps:** Syncs native repositories, upgrades system packages (`dnf`, `apt`, `pacman`), and updates installed Flatpaks.
- **Mute Hardware PC Speaker:** Unloads and blacklists the `pcspkr` and `snd_pcsp` kernel modules.
- **Apps & Desktop Tweaks:** Quick one-click setup for common desktop utilities (GNOME Tweaks & Extension Manager, Spotify via Flathub, and Brave Browser).
- **Live Task Output Log:** Streams real-time terminal output directly inside the interface.

## Building & Running Locally

    flatpak-builder --user --install --force-clean build-dir io.github.myrnop.SystemAssistant.yml
    flatpak run io.github.myrnop.SystemAssistant

## License
Licensed under the [GNU General Public License v3.0](LICENSE).
