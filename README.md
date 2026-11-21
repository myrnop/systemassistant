# System Assistant

A native GTK 4 and Libadwaita system maintenance and post-install setup utility for Linux desktops.

![System Assistant Screenshot](Pic1.png?v=1.4.0)

## Features

- **Overview:** Displays device model, CPU, RAM, GPU, live disk storage usage, and system uptime with a one-click refresh button.
- **Maintenance:**
  - Sync repositories and update native system packages & Flatpak apps
  - Clean unused Flatpak runtimes and extensions
  - Purge package manager cache and orphaned dependencies
  - Vacuum archived systemd journal logs older than 7 days
  - Mute hardware PC speaker (`pcspkr` & `snd_pcsp`)
  - Install and enable Power Profiles Daemon or `auto-cpufreq` optimizer
- **Tweaks & Apps:**
  - Configure RPM Fusion (Free & Nonfree), Cisco OpenH264, and multimedia codecs on Fedora
  - Install and apply consistent `adw-gtk3` theme for legacy GTK3 apps
  - Enable minimize and maximize window titlebar buttons on GNOME
  - Install GNOME Tweaks & Extension Manager, Developer CLI Essentials (`git`, `gh`, `pip`, `curl`, `wget`), Spotify, and Brave Browser
- **Live Output & Smart Detection:** Automatically detects already-installed apps and active tweaks, streams command output in real time, and lets you copy logs with one click.

## Download & Install

Download the latest `SystemAssistant.flatpak` bundle from [GitHub Releases](https://github.com/myrnop/systemassistant/releases) and install it:

```bash
flatpak install --user SystemAssistant.flatpak
flatpak run io.github.myrnop.SystemAssistant

## License
Licensed under the [GNU General Public License v3.0](LICENSE).
