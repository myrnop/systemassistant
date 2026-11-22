#!/usr/bin/env python3
import os
import platform
import re
import shutil
import subprocess
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango

IN_FLATPAK = os.path.exists("/.flatpak-info")


def wrap_host_cmd(cmd):
    if IN_FLATPAK:
        return ["flatpak-spawn", "--host"] + cmd
    return cmd


def host_which(binary):
    if IN_FLATPAK:
        res = subprocess.run(
            ["flatpak-spawn", "--host", "which", binary],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return res.returncode == 0
    return shutil.which(binary) is not None


def host_flatpak_installed(app_id):
    if not host_which("flatpak"):
        return False
    res = subprocess.run(
        wrap_host_cmd(["flatpak", "info", app_id]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0


def host_file_exists(path):
    if IN_FLATPAK:
        host_path = os.path.join("/run/host", path.lstrip("/"))
        if os.path.exists(host_path):
            return True
        res = subprocess.run(
            ["flatpak-spawn", "--host", "test", "-e", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return res.returncode == 0
    return os.path.exists(path)


def host_gsetting_get(schema, key):
    if not host_which("gsettings"):
        return ""
    try:
        out = subprocess.check_output(
            wrap_host_cmd(["gsettings", "get", schema, key]),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip().strip("'\"")
    except Exception:
        return ""


def get_os_release_path():
    if IN_FLATPAK and os.path.exists("/run/host/etc/os-release"):
        return "/run/host/etc/os-release"
    return "/etc/os-release"


def get_os_pretty_name():
    path = get_os_release_path()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.strip().split("=")[1].strip('"')
    return "Linux"


def get_distro():
    path = get_os_release_path()
    distro_id = "unknown"
    id_like = ""
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.startswith("ID="):
                    distro_id = line.strip().split("=", 1)[1].strip('"').lower()
                elif line.startswith("ID_LIKE="):
                    id_like = line.strip().split("=", 1)[1].strip('"').lower()
    if distro_id in ("ubuntu", "debian", "arch", "fedora"):
        return distro_id
    if "ubuntu" in id_like or "debian" in id_like:
        return "ubuntu"
    if "fedora" in id_like:
        return "fedora"
    if "arch" in id_like:
        return "arch"
    return distro_id


def get_uptime_str():
    try:
        with open("/proc/uptime") as f:
            seconds = int(float(f.read().split()[0]))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)
    except Exception:
        return "Unknown"


def get_storage_str():
    try:
        if IN_FLATPAK:
            out = subprocess.check_output(
                ["flatpak-spawn", "--host", "df", "-B1", "/"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            parts = out.strip().splitlines()[-1].split()
            total = int(parts[1])
            used = int(parts[2])
        else:
            usage = shutil.disk_usage("/")
            total = usage.total
            used = usage.used
        used_gb = round(used / (1024**3), 1)
        total_gb = round(total / (1024**3), 1)
        pct = round((used / total) * 100)
        return f"{used_gb} GB / {total_gb} GB ({pct}% used)"
    except Exception:
        return "Unknown"


def detect_gpu_vendor():
    try:
        out = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL).lower()
        gpu_lines = [
            line for line in out.splitlines()
            if "vga compatible controller" in line or "3d controller" in line
        ]
        joined = " ".join(gpu_lines)
        if any(vm in joined for vm in ("virtio", "qxl", "vmware", "virtualbox", "bochs", "cirrus", "hyper-v")):
            return "vm"
        if "nvidia" in joined:
            return "nvidia"
        if "amd" in joined or "ati" in joined or "radeon" in joined:
            return "amd"
        if "intel" in joined:
            return "intel"
    except Exception:
        pass
    return "unknown"


def get_hardware_info():
    model = "Linux PC"
    try:
        vendor_path = "/sys/class/dmi/id/sys_vendor"
        name_path = "/sys/class/dmi/id/product_name"
        if os.path.exists(name_path):
            with open(name_path) as f:
                prod = f.read().strip()
            vend = ""
            if os.path.exists(vendor_path):
                with open(vendor_path) as f:
                    vend = f.read().strip()
            if vend and not prod.lower().startswith(vend.lower()):
                model = f"{vend} {prod}"
            else:
                model = prod
    except Exception:
        pass

    cpu = "Unknown Processor"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    for noise in ["(R)", "(TM)", "Processor", "with Radeon Graphics"]:
                        cpu = cpu.replace(noise, "")
                    cpu = " ".join(cpu.split())
                    break
    except Exception:
        pass

    ram = "Unknown"
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    gb = round(kb / (1024 * 1024), 1)
                    ram = f"{gb} GB"
                    break
    except Exception:
        pass

    gpu = "Integrated / Standard Graphics"
    try:
        out = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "VGA compatible controller" in line or "3D controller" in line:
                gpu_raw = line.split(":", 2)[-1].strip()
                gpu_raw = re.sub(r"\s*\(rev [0-9a-fA-F]+\)\s*$", "", gpu_raw)
                brackets = re.findall(r"\[([^\]]+)\]", gpu_raw)
                meaningful = [b for b in brackets if b not in ("AMD/ATI", "Intel", "NVIDIA")]
                if meaningful:
                    gpu = meaningful[-1]
                elif brackets:
                    gpu = brackets[-1]
                else:
                    gpu = gpu_raw
                break
    except Exception:
        pass

    return {
        "model": model,
        "cpu": cpu,
        "ram": ram,
        "gpu": gpu,
        "storage": get_storage_str(),
        "uptime": get_uptime_str(),
    }


class SystemAssistantWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(
            application=app,
            title="System Assistant",
            default_width=640,
            default_height=710,
        )
        self.distro = get_distro()
        self.pretty_os = get_os_pretty_name()
        self.kernel = platform.release()
        self.hw = get_hardware_info()

        display = Gdk.Display.get_default()
        if display is not None:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            icon_theme.add_search_path(os.path.dirname(os.path.abspath(__file__)))

        self.toast_overlay = Adw.ToastOverlay()

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()

        self.stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(
            stack=self.stack,
            policy=Adw.ViewSwitcherPolicy.WIDE,
        )
        header.set_title_widget(switcher)

        about_btn = Gtk.Button(
            icon_name="help-about-symbolic",
            tooltip_text="About System Assistant",
        )
        about_btn.connect("clicked", self.on_about_clicked)
        header.pack_end(about_btn)

        toolbar_view.add_top_bar(header)

        # --- TAB 1: OVERVIEW ---
        overview_page = Adw.PreferencesPage()

        hero_group = Adw.PreferencesGroup()
        hero_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_top=4,
            margin_bottom=4,
        )

        local_icon = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "io.github.myrnop.SystemAssistant.png",
        )
        if os.path.exists(local_icon):
            hero_icon = Gtk.Image.new_from_file(local_icon)
        else:
            hero_icon = Gtk.Image.new_from_icon_name("io.github.myrnop.SystemAssistant")
        hero_icon.set_pixel_size(72)

        hero_title = Gtk.Label(label="System Assistant")
        hero_title.add_css_class("title-1")

        hero_subtitle = Gtk.Label(label=f"{self.pretty_os}  •  Kernel {self.kernel}")
        hero_subtitle.add_css_class("dim-label")
        hero_subtitle.add_css_class("caption")

        hero_box.append(hero_icon)
        hero_box.append(hero_title)
        hero_box.append(hero_subtitle)
        hero_group.add(hero_box)
        overview_page.add(hero_group)

        hw_group = Adw.PreferencesGroup(title="System Hardware &amp; Status")
        refresh_btn = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Refresh System Status",
            valign=Gtk.Align.CENTER,
        )
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", self.on_refresh_stats_clicked)
        hw_group.set_header_suffix(refresh_btn)

        self.hw_labels = {}
        hw_rows = [
            ("device", "Device", self.hw["model"], "computer-symbolic"),
            ("cpu", "Processor", self.hw["cpu"], "applications-electronics-symbolic"),
            ("ram", "Memory", self.hw["ram"], "drive-harddisk-symbolic"),
            ("gpu", "Graphics", self.hw["gpu"], "video-display-symbolic"),
            ("storage", "Disk Storage", self.hw["storage"], "drive-multidisk-symbolic"),
            ("uptime", "Uptime", self.hw["uptime"], "preferences-system-time-symbolic"),
        ]
        for key, label_text, value_text, icon_name in hw_rows:
            row = Adw.ActionRow(title=label_text)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))
            val_label = Gtk.Label(label=value_text)
            val_label.add_css_class("dim-label")
            val_label.set_ellipsize(Pango.EllipsizeMode.END)
            val_label.set_max_width_chars(38)
            row.add_suffix(val_label)
            hw_group.add(row)
            self.hw_labels[key] = val_label

        overview_page.add(hw_group)
        self.stack.add_titled_with_icon(
            overview_page, "overview", "Overview", "computer-symbolic"
        )

        # --- TAB 2: MAINTENANCE ---
        maint_page = Adw.PreferencesPage()

        updates_group = Adw.PreferencesGroup(title="Updates &amp; Storage Cleanup")
        self.row_update = self.create_switch_row(
            title="Update System &amp; Flatpak Apps",
            subtitle="Sync repositories, upgrade packages, and update Flatpaks",
            icon_name="software-update-available-symbolic",
            active=True,
        )
        updates_group.add(self.row_update)

        self.row_flatpak_clean = self.create_switch_row(
            title="Clean Unused Flatpak Runtimes",
            subtitle="Remove orphaned Flatpak runtimes and extensions",
            icon_name="user-trash-symbolic",
            active=False,
        )
        updates_group.add(self.row_flatpak_clean)

        self.row_pkg_clean = self.create_switch_row(
            title="Clear Package Manager Cache",
            subtitle="Purge cached package metadata and unused dependencies",
            icon_name="edit-clear-all-symbolic",
            active=False,
        )
        updates_group.add(self.row_pkg_clean)

        self.row_journal_clean = self.create_switch_row(
            title="Vacuum Old System Logs",
            subtitle="Remove archived systemd journal logs older than 7 days",
            icon_name="document-open-recent-symbolic",
            active=False,
        )
        updates_group.add(self.row_journal_clean)
        maint_page.add(updates_group)

        hw_tweaks_group = Adw.PreferencesGroup(title="Hardware &amp; Kernel")
        self.row_pcspkr = self.create_switch_row(
            title="Mute Hardware PC Speaker",
            subtitle="Unload and blacklist pcspkr &amp; snd_pcsp kernel modules",
            icon_name="audio-volume-muted-symbolic",
            active=False,
        )
        hw_tweaks_group.add(self.row_pcspkr)

        self.row_power_profiles = self.create_switch_row(
            title="Power Profiles Daemon",
            subtitle="Install and enable GNOME power mode switching (Balanced / Performance)",
            icon_name="battery-good-symbolic",
            active=False,
        )
        hw_tweaks_group.add(self.row_power_profiles)

        self.row_autocpufreq = self.create_switch_row(
            title="auto-cpufreq Optimizer",
            subtitle="Install and enable automatic CPU speed &amp; power optimization",
            icon_name="preferences-system-power-symbolic",
            active=False,
        )
        hw_tweaks_group.add(self.row_autocpufreq)
        maint_page.add(hw_tweaks_group)

        self.stack.add_titled_with_icon(
            maint_page, "maintenance", "Maintenance", "system-run-symbolic"
        )

        # --- TAB 3: TWEAKS & APPS ---
        apps_page = Adw.PreferencesPage()

        tweaks_group = Adw.PreferencesGroup(title="Desktop &amp; Codec Tweaks")
        self.gpu_vendor = detect_gpu_vendor()
        self.row_gpu = None
        if self.gpu_vendor == "nvidia":
            self.row_gpu = self.create_switch_row(
                title="NVIDIA Proprietary Drivers",
                subtitle="Install official NVIDIA GPU kernel modules and CUDA/NVENC support",
                icon_name="video-display-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_gpu)
        elif self.gpu_vendor in ("amd", "intel"):
            self.row_gpu = self.create_switch_row(
                title="Hardware Video Acceleration (VA-API)",
                subtitle="Enable GPU hardware video decoding for browsers and media players",
                icon_name="video-display-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_gpu)

        self.row_rpmfusion = None
        self.row_arch_pacman = None
        self.row_arch_yay = None
        self.row_arch_codecs_flatpak = None
        self.row_ubuntu_codecs = None
        self.row_ubuntu_flatpak = None
        self.row_ubuntu_firefox = None
        self.row_ubuntu_nala_appimage = None
        self.row_debian_repos = None
        if self.distro in ("ubuntu", "debian"):
            self.row_ubuntu_codecs = self.create_switch_row(
                title="Ubuntu Restricted Extras &amp; Codecs",
                subtitle="Install multimedia codecs, H.264/AAC playback, and core fonts",
                icon_name="multimedia-player-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_ubuntu_codecs)

            self.row_ubuntu_flatpak = self.create_switch_row(
                title="Setup Flatpak &amp; Flathub",
                subtitle="Install Flatpak and enable the Flathub app repository",
                icon_name="system-software-install-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_ubuntu_flatpak)

            self.row_ubuntu_firefox = self.create_switch_row(
                title="Official Mozilla Firefox (.deb)",
                subtitle="Replace Firefox Snap with Mozilla's native APT package",
                icon_name="web-browser-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_ubuntu_firefox)

            self.row_ubuntu_nala_appimage = self.create_switch_row(
                title="Nala &amp; AppImage Support",
                subtitle="Install faster Nala APT frontend and FUSE 2 runtime for AppImages",
                icon_name="utilities-terminal-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_ubuntu_nala_appimage)

        if self.distro == "debian":
            self.row_debian_repos = self.create_switch_row(
                title="Debian Contrib &amp; Non-Free Firmware",
                subtitle="Enable contrib, non-free, and non-free-firmware repositories",
                icon_name="system-software-install-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_debian_repos)

        if self.distro == "fedora":
            self.row_rpmfusion = self.create_switch_row(
                title="RPM Fusion &amp; Multimedia Codecs",
                subtitle="Enable RPM Fusion Free/Nonfree, OpenH264, and media codecs",
                icon_name="multimedia-player-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_rpmfusion)

        if self.distro == "arch":
            self.row_arch_pacman = self.create_switch_row(
                title="Enable Multilib &amp; Parallel Downloads",
                subtitle="Enable 32-bit [multilib] repo, Color, and ParallelDownloads in pacman.conf",
                icon_name="system-software-install-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_arch_pacman)

            self.row_arch_yay = self.create_switch_row(
                title="Install yay AUR Helper",
                subtitle="Build and install yay-bin for Arch User Repository packages",
                icon_name="utilities-terminal-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_arch_yay)

            self.row_arch_codecs_flatpak = self.create_switch_row(
                title="Flatpak, Flathub &amp; Multimedia Codecs",
                subtitle="Install Flatpak, Flathub remote, FFmpeg, and GStreamer plugins",
                icon_name="multimedia-player-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_arch_codecs_flatpak)

        self.row_adw_gtk3 = self.create_switch_row(
            title="Consistent Libadwaita GTK3 Theme",
            subtitle="Install adw-gtk3 so legacy GTK3 apps match Libadwaita",
            icon_name="preferences-desktop-theme-symbolic",
            active=False,
        )
        tweaks_group.add(self.row_adw_gtk3)

        self.row_win_buttons = self.create_switch_row(
            title="Window Minimize &amp; Maximize Buttons",
            subtitle="Enable minimize and maximize controls on GNOME titlebars",
            icon_name="window-maximize-symbolic",
            active=False,
        )
        tweaks_group.add(self.row_win_buttons)
        apps_page.add(tweaks_group)

        software_group = Adw.PreferencesGroup(title="Essential Applications &amp; Tools")
        self.row_tweaks = self.create_switch_row(
            title="GNOME Tweaks &amp; Extensions",
            subtitle="Install gnome-tweaks and Extension Manager",
            icon_name="applications-utilities-symbolic",
            active=False,
        )
        software_group.add(self.row_tweaks)

        self.row_dev_tools = self.create_switch_row(
            title="Developer CLI Essentials",
            subtitle="Install Git, GitHub CLI (gh), Python pip, curl, and wget",
            icon_name="utilities-terminal-symbolic",
            active=False,
        )
        software_group.add(self.row_dev_tools)

        self.row_spotify = self.create_switch_row(
            title="Spotify",
            subtitle="Install official Spotify client via Flathub",
            icon_name="folder-music-symbolic",
            active=False,
        )
        software_group.add(self.row_spotify)

        if self.distro in ("ubuntu", "debian"):
            brave_sub = "Configure Brave APT repository and install browser"
        elif self.distro == "arch":
            brave_sub = "Install Brave Browser via AUR (yay/paru) or Flathub"
        else:
            brave_sub = "Configure Brave RPM repository and install browser"
        self.row_brave = self.create_switch_row(
            title="Brave Browser",
            subtitle=brave_sub,
            icon_name="web-browser-symbolic",
            active=False,
        )
        software_group.add(self.row_brave)

        self.row_gaming = self.create_switch_row(
            title="Gaming Essentials",
            subtitle="Install Steam, GameMode, MangoHud, and ProtonUp-Qt",
            icon_name="input-gaming-symbolic",
            active=False,
        )
        software_group.add(self.row_gaming)
        apps_page.add(software_group)

        self.stack.add_titled_with_icon(
            apps_page, "tweaks", "Tweaks & Apps", "applications-utilities-symbolic"
        )

        # --- BOTTOM ACTION BAR & LIVE LOG ---
        bottom_clamp = Adw.Clamp(
            maximum_size=560,
            margin_top=8,
            margin_bottom=12,
            margin_start=16,
            margin_end=16,
        )
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        btn_content = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
        )
        self.spinner = Gtk.Spinner()
        self.btn_label = Gtk.Label(label="Run Selected Tasks")
        btn_content.append(self.spinner)
        btn_content.append(self.btn_label)

        actions_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
        )

        self.preset_btn = Gtk.Button(
            label="Recommended",
            tooltip_text="Select recommended fresh-install updates, codecs, and desktop tweaks",
        )
        self.preset_btn.add_css_class("pill")
        self.preset_btn.set_size_request(130, 42)
        self.preset_btn.connect("clicked", self.on_preset_recommended_clicked)
        actions_row.append(self.preset_btn)

        self.run_btn = Gtk.Button(child=btn_content)
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.add_css_class("pill")
        self.run_btn.set_size_request(210, 42)
        self.run_btn.connect("clicked", self.on_run_clicked)
        actions_row.append(self.run_btn)

        self.clear_btn = Gtk.Button(
            label="Clear All",
            tooltip_text="Turn off all selected toggles",
        )
        self.clear_btn.add_css_class("pill")
        self.clear_btn.set_size_request(110, 42)
        self.clear_btn.connect("clicked", self.on_clear_all_clicked)
        actions_row.append(self.clear_btn)

        bottom_box.append(actions_row)

        self.progress_bar = Gtk.ProgressBar(visible=False)
        self.progress_bar.add_css_class("osd")
        bottom_box.append(self.progress_bar)

        log_group = Adw.PreferencesGroup()
        self.log_expander = Adw.ExpanderRow(
            title="Task Output Log",
            subtitle="View live command execution details",
        )
        self.log_expander.add_prefix(
            Gtk.Image.new_from_icon_name("utilities-terminal-symbolic")
        )

        copy_btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text="Copy Log to Clipboard",
            valign=Gtk.Align.CENTER,
        )
        copy_btn.add_css_class("flat")
        copy_btn.connect("clicked", self.on_copy_log_clicked)
        self.log_expander.add_suffix(copy_btn)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(
            buffer=self.log_buffer,
            editable=False,
            cursor_visible=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=10,
            bottom_margin=10,
            left_margin=10,
            right_margin=10,
        )
        self.scrolled_log = Gtk.ScrolledWindow(
            min_content_height=140,
            child=self.log_view,
        )
        self.log_expander.add_row(self.scrolled_log)
        log_group.add(self.log_expander)
        bottom_box.append(log_group)

        credit_label = Gtk.Label(label="Made with ❤️ by MyrnChef")
        credit_label.add_css_class("dim-label")
        credit_label.add_css_class("caption")
        credit_label.set_halign(Gtk.Align.CENTER)
        bottom_box.append(credit_label)

        bottom_clamp.set_child(bottom_box)

        toolbar_view.set_content(self.stack)
        toolbar_view.add_bottom_bar(bottom_clamp)

        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)

        self.refresh_detected_states()

    def get_all_switch_rows(self):
        rows = [
            self.row_update,
            self.row_flatpak_clean,
            self.row_pkg_clean,
            self.row_journal_clean,
            self.row_pcspkr,
            self.row_power_profiles,
            self.row_autocpufreq,
            self.row_gpu,
            self.row_rpmfusion,
            self.row_arch_pacman,
            self.row_arch_yay,
            self.row_arch_codecs_flatpak,
            self.row_ubuntu_codecs,
            self.row_ubuntu_flatpak,
            self.row_ubuntu_firefox,
            self.row_ubuntu_nala_appimage,
            self.row_debian_repos,
            self.row_adw_gtk3,
            self.row_win_buttons,
            self.row_tweaks,
            self.row_dev_tools,
            self.row_spotify,
            self.row_brave,
            self.row_gaming,
        ]
        return [r for r in rows if r is not None]

    def on_clear_all_clicked(self, button):
        for row in self.get_all_switch_rows():
            row.set_active(False)
        self.show_toast("Cleared all selected tasks")

    def on_preset_recommended_clicked(self, button):
        for row in self.get_all_switch_rows():
            row.set_active(False)

        recommended = [
            self.row_update,
            self.row_gpu,
            self.row_adw_gtk3,
            self.row_win_buttons,
        ]
        if self.distro == "fedora":
            recommended.append(self.row_rpmfusion)
        elif self.distro in ("ubuntu", "debian"):
            recommended.extend([self.row_ubuntu_codecs, self.row_ubuntu_flatpak, self.row_debian_repos])
        elif self.distro == "arch":
            recommended.extend([self.row_arch_pacman, self.row_arch_codecs_flatpak])

        count = 0
        for row in recommended:
            if row is not None:
                row.set_active(True)
                count += 1

        self.show_toast(f"Selected {count} recommended fresh-install tasks")

    def on_refresh_stats_clicked(self, button):
        self.hw_labels["storage"].set_label(get_storage_str())
        self.hw_labels["uptime"].set_label(get_uptime_str())
        self.refresh_detected_states()
        self.show_toast("Refreshed system status")

    def refresh_detected_states(self):
        def _detect():
            states = {
                "gpu": (
                    host_which("nvidia-smi")
                    if self.gpu_vendor == "nvidia"
                    else (
                        host_which("vainfo")
                        or host_file_exists("/usr/lib64/dri/radeonsi_drv_video.so")
                        or host_file_exists("/usr/lib/dri/radeonsi_drv_video.so")
                        or host_file_exists("/usr/lib/x86_64-linux-gnu/dri/radeonsi_drv_video.so")
                        or host_file_exists("/usr/lib64/dri/iHD_drv_video.so")
                        or host_file_exists("/usr/lib/dri/iHD_drv_video.so")
                        or host_file_exists("/usr/lib/x86_64-linux-gnu/dri/iHD_drv_video.so")
                    )
                ),
                "pcspkr": host_file_exists("/etc/modprobe.d/blacklist-pcspkr.conf"),
                "power_profiles": host_which("powerprofilesctl"),
                "autocpufreq": host_which("auto-cpufreq"),
                "rpmfusion": host_file_exists("/etc/yum.repos.d/rpmfusion-free.repo"),
                "arch_pacman": (
                    host_file_exists("/etc/pacman.conf")
                    and "\n[multilib]" in open(
                        "/run/host/etc/pacman.conf"
                        if os.path.exists("/run/host/etc/pacman.conf")
                        else "/etc/pacman.conf"
                    ).read()
                ) if self.distro == "arch" else False,
                "arch_yay": bool(host_which("yay") or host_which("paru")),
                "arch_codecs_flatpak": bool(host_which("flatpak") and host_which("ffmpeg")),
                "ubuntu_codecs": host_file_exists("/usr/share/doc/ubuntu-restricted-extras/copyright"),
                "ubuntu_flatpak": bool(host_which("flatpak")) and (
                    "flathub" in subprocess.run(
                        wrap_host_cmd(["flatpak", "remotes"]),
                        capture_output=True,
                        text=True,
                    ).stdout
                ),
                "ubuntu_firefox": host_file_exists("/etc/apt/sources.list.d/mozilla.list") and bool(host_which("firefox")),
                "debian_repos": (
                    (
                        host_file_exists("/etc/apt/sources.list.d/debian.sources")
                        and "non-free-firmware" in open("/run/host/etc/apt/sources.list.d/debian.sources" if os.path.exists("/run/host/etc/apt/sources.list.d/debian.sources") else "/etc/apt/sources.list.d/debian.sources").read()
                    )
                    or (
                        host_file_exists("/etc/apt/sources.list")
                        and "non-free-firmware" in open("/run/host/etc/apt/sources.list" if os.path.exists("/run/host/etc/apt/sources.list") else "/etc/apt/sources.list").read()
                    )
                ) if self.distro == "debian" else False,
                "ubuntu_nala_appimage": bool(host_which("nala")) and (
                    host_file_exists("/usr/lib/x86_64-linux-gnu/libfuse.so.2")
                    or host_file_exists("/usr/lib/aarch64-linux-gnu/libfuse.so.2")
                    or host_file_exists("/lib/x86_64-linux-gnu/libfuse.so.2")
                ),
                "adw_gtk3": "adw-gtk3" in host_gsetting_get("org.gnome.desktop.interface", "gtk-theme"),
                "win_buttons": "minimize" in host_gsetting_get("org.gnome.desktop.wm.preferences", "button-layout"),
                "tweaks": host_which("gnome-tweaks"),
                "dev_tools": host_which("git") and host_which("gh"),
                "spotify": host_flatpak_installed("com.spotify.Client"),
                "brave": bool(host_which("brave-browser") or host_which("brave") or host_flatpak_installed("com.brave.Browser")),
                "gaming": bool((host_which("steam") or host_flatpak_installed("com.valvesoftware.Steam")) and host_which("gamemoderun")),
            }

            def _apply():
                self.set_row_badge(
                    self.row_pcspkr,
                    "Unload and blacklist pcspkr &amp; snd_pcsp kernel modules",
                    states["pcspkr"],
                    "Active",
                )
                self.set_row_badge(
                    self.row_power_profiles,
                    "Install and enable GNOME power mode switching (Balanced / Performance)",
                    states["power_profiles"],
                    "Installed",
                )
                self.set_row_badge(
                    self.row_autocpufreq,
                    "Install and enable automatic CPU speed &amp; power optimization",
                    states["autocpufreq"],
                    "Installed",
                )
                if self.row_gpu:
                    gpu_sub = (
                        "Install official NVIDIA GPU kernel modules and CUDA/NVENC support"
                        if self.gpu_vendor == "nvidia"
                        else "Enable GPU hardware video decoding for browsers and media players"
                    )
                    self.set_row_badge(
                        self.row_gpu,
                        gpu_sub,
                        states["gpu"],
                        "Installed",
                    )
                if self.row_rpmfusion:
                    self.set_row_badge(
                        self.row_rpmfusion,
                        "Enable RPM Fusion Free/Nonfree, OpenH264, and media codecs",
                        states["rpmfusion"],
                        "Enabled",
                    )
                if self.row_arch_pacman:
                    self.set_row_badge(
                        self.row_arch_pacman,
                        "Enable 32-bit [multilib] repo, Color, and ParallelDownloads in pacman.conf",
                        states["arch_pacman"],
                        "Enabled",
                    )
                if self.row_arch_yay:
                    self.set_row_badge(
                        self.row_arch_yay,
                        "Build and install yay-bin for Arch User Repository packages",
                        states["arch_yay"],
                        "Installed",
                    )
                if self.row_arch_codecs_flatpak:
                    self.set_row_badge(
                        self.row_arch_codecs_flatpak,
                        "Install Flatpak, Flathub remote, FFmpeg, and GStreamer plugins",
                        states["arch_codecs_flatpak"],
                        "Installed",
                    )
                if self.row_ubuntu_codecs:
                    self.set_row_badge(
                        self.row_ubuntu_codecs,
                        "Install multimedia codecs, H.264/AAC playback, and core fonts",
                        states["ubuntu_codecs"],
                        "Installed",
                    )
                if self.row_ubuntu_flatpak:
                    self.set_row_badge(
                        self.row_ubuntu_flatpak,
                        "Install Flatpak and enable the Flathub app repository",
                        states["ubuntu_flatpak"],
                        "Active",
                    )
                if self.row_ubuntu_firefox:
                    self.set_row_badge(
                        self.row_ubuntu_firefox,
                        "Replace Firefox Snap with Mozilla's native APT package",
                        states["ubuntu_firefox"],
                        "Installed",
                    )
                if self.row_ubuntu_nala_appimage:
                    self.set_row_badge(
                        self.row_ubuntu_nala_appimage,
                        "Install faster Nala APT frontend and FUSE 2 runtime for AppImages",
                        states["ubuntu_nala_appimage"],
                        "Installed",
                    )
                if self.row_debian_repos:
                    self.set_row_badge(
                        self.row_debian_repos,
                        "Enable contrib, non-free, and non-free-firmware repositories",
                        states["debian_repos"],
                        "Enabled",
                    )
                self.set_row_badge(
                    self.row_adw_gtk3,
                    "Install adw-gtk3 so legacy GTK3 apps match Libadwaita",
                    states["adw_gtk3"],
                    "Active",
                )
                self.set_row_badge(
                    self.row_win_buttons,
                    "Enable minimize and maximize controls on GNOME titlebars",
                    states["win_buttons"],
                    "Active",
                )
                self.set_row_badge(
                    self.row_tweaks,
                    "Install gnome-tweaks and Extension Manager",
                    states["tweaks"],
                    "Installed",
                )
                self.set_row_badge(
                    self.row_dev_tools,
                    "Install Git, GitHub CLI (gh), Python pip, curl, and wget",
                    states["dev_tools"],
                    "Installed",
                )
                self.set_row_badge(
                    self.row_spotify,
                    "Install official Spotify client via Flathub",
                    states["spotify"],
                    "Installed",
                )
                if self.row_ubuntu_codecs:
                    self.set_row_badge(
                        self.row_ubuntu_codecs,
                        "Install multimedia codecs, H.264/AAC playback, and core fonts",
                        states["ubuntu_codecs"],
                        "Installed",
                    )
                if self.row_ubuntu_flatpak:
                    self.set_row_badge(
                        self.row_ubuntu_flatpak,
                        "Install Flatpak and enable the Flathub app repository",
                        states["ubuntu_flatpak"],
                        "Active",
                    )
                if self.distro in ("ubuntu", "debian"):
                    brave_sub_applied = "Configure Brave APT repository and install browser"
                elif self.distro == "arch":
                    brave_sub_applied = "Install Brave Browser via AUR (yay/paru) or Flathub"
                else:
                    brave_sub_applied = "Configure Brave RPM repository and install browser"
                self.set_row_badge(
                    self.row_brave,
                    brave_sub_applied,
                    states["brave"],
                    "Installed",
                )
                self.set_row_badge(
                    self.row_gaming,
                    "Install Steam, GameMode, MangoHud, and ProtonUp-Qt",
                    states["gaming"],
                    "Installed",
                )
                return False

            GLib.idle_add(_apply)

        threading.Thread(target=_detect, daemon=True).start()

    def set_row_badge(self, row, base_subtitle, is_done, badge_text):
        if is_done:
            row.set_subtitle(f"{base_subtitle}  •  ✓ {badge_text}")
        else:
            row.set_subtitle(base_subtitle)

    def on_copy_log_clicked(self, button):
        start_iter = self.log_buffer.get_start_iter()
        end_iter = self.log_buffer.get_end_iter()
        text = self.log_buffer.get_text(start_iter, end_iter, False).strip()
        if not text:
            self.show_toast("Log is empty")
            return
        display = Gdk.Display.get_default()
        if display:
            display.get_clipboard().set(text)
            self.show_toast("Copied task output log to clipboard")

    def on_about_clicked(self, button):
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="System Assistant",
            application_icon="io.github.myrnop.SystemAssistant",
            developer_name="MyrnChef",
            version="1.6.0",
            comments="Made with ❤️ by MyrnChef\n\nA native GTK 4 and Libadwaita system maintenance and post-install setup utility for Linux desktops.",
            website="https://github.com/myrnop/systemassistant",
            issue_url="https://github.com/myrnop/systemassistant/issues",
            license_type=Gtk.License.GPL_3_0,
            developers=["MyrnChef https://github.com/myrnop"],
        )
        about.present()

    def create_switch_row(self, title, subtitle, icon_name, active=False):
        row = Adw.SwitchRow(title=title, subtitle=subtitle, active=active)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        row.add_prefix(icon)
        return row

    def show_toast(self, message):
        def _toast():
            toast = Adw.Toast(title=message, timeout=4)
            self.toast_overlay.add_toast(toast)
            return False

        GLib.idle_add(_toast)

    def log(self, message):
        def _append():
            end_iter = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end_iter, message + "\n")
            mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
            self.log_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
            return False

        GLib.idle_add(_append)

    def run_cmd(self, cmd):
        full_cmd = wrap_host_cmd(cmd)
        self.log(f"$ {' '.join(cmd)}")
        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in process.stdout:
            self.log(line.rstrip())
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

    def on_run_clicked(self, button):
        tasks = {
            "update": self.row_update.get_active(),
            "flatpak_clean": self.row_flatpak_clean.get_active(),
            "pkg_clean": self.row_pkg_clean.get_active(),
            "journal_clean": self.row_journal_clean.get_active(),
            "gpu": self.row_gpu.get_active() if self.row_gpu else False,
            "pcspkr": self.row_pcspkr.get_active(),
            "power_profiles": self.row_power_profiles.get_active(),
            "autocpufreq": self.row_autocpufreq.get_active(),
            "rpmfusion": self.row_rpmfusion.get_active() if self.row_rpmfusion else False,
            "arch_pacman": self.row_arch_pacman.get_active() if self.row_arch_pacman else False,
            "arch_yay": self.row_arch_yay.get_active() if self.row_arch_yay else False,
            "arch_codecs_flatpak": self.row_arch_codecs_flatpak.get_active() if self.row_arch_codecs_flatpak else False,
            "ubuntu_codecs": self.row_ubuntu_codecs.get_active() if self.row_ubuntu_codecs else False,
            "ubuntu_flatpak": self.row_ubuntu_flatpak.get_active() if self.row_ubuntu_flatpak else False,
            "ubuntu_firefox": self.row_ubuntu_firefox.get_active() if self.row_ubuntu_firefox else False,
            "ubuntu_nala_appimage": self.row_ubuntu_nala_appimage.get_active() if self.row_ubuntu_nala_appimage else False,
            "debian_repos": self.row_debian_repos.get_active() if self.row_debian_repos else False,
            "adw_gtk3": self.row_adw_gtk3.get_active(),
            "win_buttons": self.row_win_buttons.get_active(),
            "tweaks": self.row_tweaks.get_active(),
            "dev_tools": self.row_dev_tools.get_active(),
            "spotify": self.row_spotify.get_active(),
            "brave": self.row_brave.get_active(),
            "gaming": self.row_gaming.get_active(),
        }

        if not any(tasks.values()):
            self.show_toast("Select at least one task first")
            return

        self.run_btn.set_sensitive(False)
        self.spinner.start()
        self.btn_label.set_label("Running Tasks...")
        self.log_buffer.set_text("")
        self.log_expander.set_expanded(True)
        self.progress_bar.set_visible(True)
        self._pulse_active = True

        def _pulse_progress():
            if not getattr(self, "_pulse_active", False):
                return False
            self.progress_bar.pulse()
            return True

        GLib.timeout_add(120, _pulse_progress)

        threading.Thread(target=self.execute_tasks, args=(tasks,), daemon=True).start()

    def execute_tasks(self, tasks):
        try:
            needs_root = (
                tasks["update"]
                or tasks["pkg_clean"]
                or tasks["journal_clean"]
                or tasks["pcspkr"]
                or tasks["power_profiles"]
                or tasks["autocpufreq"]
                or (tasks["rpmfusion"] and self.distro == "fedora")
                or (tasks["arch_pacman"] and self.distro == "arch")
                or (tasks["arch_yay"] and self.distro == "arch")
                or (tasks["arch_codecs_flatpak"] and self.distro == "arch")
                or (tasks["ubuntu_codecs"] and self.distro in ["ubuntu", "debian"])
                or (tasks["ubuntu_flatpak"] and self.distro in ["ubuntu", "debian"])
                or (tasks["ubuntu_firefox"] and self.distro in ["ubuntu", "debian"])
                or (tasks["ubuntu_nala_appimage"] and self.distro in ["ubuntu", "debian"])
                or (tasks["debian_repos"] and self.distro == "debian")
                or (tasks["adw_gtk3"] and self.distro in ["fedora", "arch"])
                or (tasks["tweaks"] and not host_which("gnome-tweaks"))
                or tasks["dev_tools"]
                or (tasks["brave"] and not host_which("brave-browser"))
            )

            root_commands = []

            if tasks["update"]:
                if self.distro in ["ubuntu", "debian"]:
                    root_commands.append("apt update && apt upgrade -y")
                elif self.distro == "fedora":
                    root_commands.append("dnf update -y")
                elif self.distro == "arch":
                    root_commands.append("pacman -Syu --noconfirm")

            if tasks["pkg_clean"]:
                if self.distro in ["ubuntu", "debian"]:
                    root_commands.append("apt autoremove -y && apt clean")
                elif self.distro == "fedora":
                    root_commands.append("dnf clean all")
                elif self.distro == "arch":
                    root_commands.append(
                        "pacman -Sc --noconfirm && (pacman -Qtdq | pacman -Rns --noconfirm - || true)"
                    )

            if tasks["journal_clean"]:
                root_commands.append("journalctl --vacuum-time=7d")

            if tasks["gpu"]:
                if self.gpu_vendor == "nvidia":
                    if self.distro == "fedora":
                        root_commands.append(
                            "dnf install -y "
                            "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm "
                            "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm && "
                            "dnf install -y akmod-nvidia xorg-x11-drv-nvidia-cuda"
                        )
                    elif self.distro == "ubuntu":
                        root_commands.append(
                            "DEBIAN_FRONTEND=noninteractive apt-get update && "
                            "DEBIAN_FRONTEND=noninteractive apt-get install -y ubuntu-drivers-common && "
                            "ubuntu-drivers autoinstall"
                        )
                    elif self.distro == "debian":
                        root_commands.append(
                            "DEBIAN_FRONTEND=noninteractive apt-get update && "
                            "DEBIAN_FRONTEND=noninteractive apt-get install -y linux-headers-$(uname -r) nvidia-driver"
                        )
                    elif self.distro == "arch":
                        root_commands.append(
                            "pacman -S --needed --noconfirm nvidia-dkms nvidia-utils lib32-nvidia-utils"
                        )
                elif self.gpu_vendor in ("amd", "intel"):
                    if self.distro == "fedora":
                        root_commands.append(
                            "dnf install -y "
                            "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm "
                            "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm && "
                            "dnf swap -y mesa-va-drivers mesa-va-drivers-freeworld || true; "
                            "dnf install -y libva-utils"
                        )
                    elif self.distro in ("ubuntu", "debian"):
                        root_commands.append(
                            "DEBIAN_FRONTEND=noninteractive apt-get update && "
                            "DEBIAN_FRONTEND=noninteractive apt-get install -y mesa-va-drivers intel-media-va-driver vainfo"
                        )
                    elif self.distro == "arch":
                        pkg = "libva-mesa-driver lib32-libva-mesa-driver libva-utils" if self.gpu_vendor == "amd" else "intel-media-driver libva-utils"
                        root_commands.append(f"pacman -S --needed --noconfirm {pkg}")

            if tasks["pcspkr"]:
                root_commands.append("modprobe -r pcspkr snd_pcsp 2>/dev/null || true")
                root_commands.append(
                    "printf 'blacklist pcspkr\\nblacklist snd_pcsp\\n' > /etc/modprobe.d/blacklist-pcspkr.conf"
                )

            if tasks["power_profiles"]:
                if self.distro in ["ubuntu", "debian"]:
                    root_commands.append("apt install -y power-profiles-daemon")
                elif self.distro == "fedora":
                    root_commands.append("dnf install -y power-profiles-daemon")
                elif self.distro == "arch":
                    root_commands.append("pacman -S --noconfirm power-profiles-daemon")
                root_commands.append("systemctl enable --now power-profiles-daemon")

            if tasks["autocpufreq"]:
                if self.distro in ["ubuntu", "debian"]:
                    root_commands.append("apt install -y git")
                elif self.distro == "fedora":
                    root_commands.append("dnf install -y git")
                elif self.distro == "arch":
                    root_commands.append("pacman -S --noconfirm git")
                root_commands.append(
                    "rm -rf /tmp/auto-cpufreq && "
                    "git clone --depth=1 https://github.com/AdnanHodzic/auto-cpufreq.git /tmp/auto-cpufreq && "
                    "cd /tmp/auto-cpufreq && ./auto-cpufreq-installer --install && "
                    "rm -rf /tmp/auto-cpufreq && auto-cpufreq --install"
                )

            if tasks["ubuntu_codecs"] and self.distro in ["ubuntu", "debian"]:
                root_commands.append(
                    "echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections"
                )
                root_commands.append(
                    "DEBIAN_FRONTEND=noninteractive apt-get update && "
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y ubuntu-restricted-extras libavcodec-extra"
                )

            if tasks["ubuntu_flatpak"] and self.distro in ["ubuntu", "debian"]:
                root_commands.append(
                    "DEBIAN_FRONTEND=noninteractive apt-get update && "
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y flatpak gnome-software-plugin-flatpak"
                )
                root_commands.append(
                    "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"
                )

            if tasks["ubuntu_firefox"] and self.distro in ["ubuntu", "debian"]:
                root_commands.append("command -v snap >/dev/null 2>&1 && snap remove firefox 2>/dev/null || true")
                root_commands.append("install -d -m 0755 /etc/apt/keyrings")
                root_commands.append("DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y wget")
                root_commands.append(
                    "wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | "
                    "tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null"
                )
                root_commands.append(
                    "echo 'deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] "
                    "https://packages.mozilla.org/apt mozilla main' > /etc/apt/sources.list.d/mozilla.list"
                )
                root_commands.append(
                    "printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' > /etc/apt/preferences.d/mozilla"
                )
                root_commands.append(
                    "DEBIAN_FRONTEND=noninteractive apt-get update && "
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y --allow-downgrades firefox"
                )

            if tasks["ubuntu_nala_appimage"] and self.distro in ["ubuntu", "debian"]:
                root_commands.append(
                    "DEBIAN_FRONTEND=noninteractive apt-get update && "
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y nala && "
                    "(DEBIAN_FRONTEND=noninteractive apt-get install -y libfuse2t64 || "
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y libfuse2)"
                )

            if tasks["debian_repos"] and self.distro == "debian":
                root_commands.append(
                    "if [ -f /etc/apt/sources.list.d/debian.sources ]; then "
                    "sed -i '/^Components:/ { /non-free-firmware/! s/$/ contrib non-free non-free-firmware/ }' /etc/apt/sources.list.d/debian.sources; "
                    "elif [ -f /etc/apt/sources.list ]; then "
                    "sed -i -E '/^deb .* main/ { /non-free-firmware/! s/ main.*/ main contrib non-free non-free-firmware/ }' /etc/apt/sources.list; "
                    "fi && DEBIAN_FRONTEND=noninteractive apt-get update"
                )

            if tasks["arch_pacman"] and self.distro == "arch":
                root_commands.append(
                    "sed -i 's/^#Color/Color/' /etc/pacman.conf && "
                    "sed -i 's/^#ParallelDownloads.*/ParallelDownloads = 5/' /etc/pacman.conf && "
                    "sed -i '/^#\\[multilib\\]/,/^#Include/ s/^#//' /etc/pacman.conf && "
                    "pacman -Syu --noconfirm"
                )

            if tasks["arch_yay"] and self.distro == "arch":
                root_commands.append("pacman -S --needed --noconfirm base-devel git")
                root_commands.append(
                    "TARGET_USER=${PKEXEC_UID:+$(id -un $PKEXEC_UID)}; "
                    "TARGET_USER=${TARGET_USER:-${SUDO_USER:-$USER}}; "
                    "su - \"$TARGET_USER\" -c '"
                    "rm -rf /tmp/yay-bin && "
                    "git clone --depth=1 https://aur.archlinux.org/yay-bin.git /tmp/yay-bin && "
                    "cd /tmp/yay-bin && makepkg -s --noconfirm' && "
                    "pacman -U --noconfirm /tmp/yay-bin/yay-bin-*.pkg.tar.zst && "
                    "rm -rf /tmp/yay-bin"
                )

            if tasks["arch_codecs_flatpak"] and self.distro == "arch":
                root_commands.append(
                    "pacman -S --needed --noconfirm flatpak ffmpeg gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-libav && "
                    "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"
                )

            if tasks["rpmfusion"] and self.distro == "fedora":
                root_commands.append(
                    "dnf install -y "
                    "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm "
                    "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"
                )
                root_commands.append(
                    "dnf config-manager setopt fedora-cisco-openh264.enabled=1"
                )
                root_commands.append(
                    "dnf install -y @multimedia --setopt=install_weak_deps=False --exclude=PackageKit-gstreamer-plugin"
                )

            if tasks["adw_gtk3"]:
                if self.distro == "fedora":
                    root_commands.append("dnf install -y adw-gtk3-theme")
                elif self.distro == "arch":
                    root_commands.append("pacman -S --noconfirm adw-gtk-theme")

            if tasks["tweaks"] and not host_which("gnome-tweaks"):
                if self.distro in ["ubuntu", "debian"]:
                    root_commands.append(
                        "apt install -y gnome-tweaks gnome-shell-extension-manager"
                    )
                elif self.distro == "fedora":
                    root_commands.append(
                        "dnf install -y gnome-tweaks gnome-extensions-app"
                    )
                elif self.distro == "arch":
                    root_commands.append("pacman -S --noconfirm gnome-tweaks")

            if tasks["dev_tools"]:
                if self.distro in ["ubuntu", "debian"]:
                    root_commands.append(
                        "apt install -y git gh python3-pip curl wget"
                    )
                elif self.distro == "fedora":
                    root_commands.append(
                        "dnf install -y git gh python3-pip curl wget"
                    )
                elif self.distro == "arch":
                    root_commands.append(
                        "pacman -S --noconfirm git github-cli python-pip curl wget"
                    )

            if tasks["gaming"]:
                if self.distro == "fedora":
                    root_commands.append(
                        "dnf install -y "
                        "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm "
                        "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm && "
                        "dnf install -y steam gamemode mangohud"
                    )
                elif self.distro in ["ubuntu", "debian"]:
                    root_commands.append(
                        "dpkg --add-architecture i386 && "
                        "DEBIAN_FRONTEND=noninteractive apt-get update && "
                        "(DEBIAN_FRONTEND=noninteractive apt-get install -y steam-installer gamemode mangohud || "
                        "DEBIAN_FRONTEND=noninteractive apt-get install -y steam gamemode mangohud)"
                    )
                elif self.distro == "arch":
                    root_commands.append(
                        "sed -i '/^#\\[multilib\\]/,/^#Include/ s/^#//' /etc/pacman.conf && "
                        "pacman -Syu --needed --noconfirm steam gamemode lib32-gamemode mangohud lib32-mangohud"
                    )

            if tasks["brave"] and not (host_which("brave-browser") or host_which("brave")):
                if self.distro in ["ubuntu", "debian"]:
                    root_commands.append("DEBIAN_FRONTEND=noninteractive apt-get update")
                    root_commands.append("DEBIAN_FRONTEND=noninteractive apt-get install -y curl")
                    root_commands.append(
                        "curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg "
                        "https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg"
                    )
                    root_commands.append(
                        "echo 'deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] "
                        "https://brave-browser-apt-release.s3.brave.com/ stable main' > "
                        "/etc/apt/sources.list.d/brave-browser-release.list"
                    )
                    root_commands.append(
                        "DEBIAN_FRONTEND=noninteractive apt-get update && "
                        "DEBIAN_FRONTEND=noninteractive apt-get install -y brave-browser"
                    )
                elif self.distro == "fedora":
                    root_commands.append("dnf install -y dnf-plugins-core")
                    root_commands.append(
                        "dnf config-manager addrepo --from-repofile=https://brave-browser-rpm-release.s3.brave.com/brave-browser.repo"
                    )
                    root_commands.append("dnf install -y brave-browser")
                elif self.distro == "arch":
                    root_commands.append(
                        "TARGET_USER=${PKEXEC_UID:+$(id -un $PKEXEC_UID)}; "
                        "TARGET_USER=${TARGET_USER:-${SUDO_USER:-$USER}}; "
                        "if command -v yay >/dev/null 2>&1 || command -v paru >/dev/null 2>&1; then "
                        "AUR_HELPER=$(command -v yay || command -v paru); "
                        "echo \"$TARGET_USER ALL=(ALL) NOPASSWD: /usr/bin/pacman\" > /etc/sudoers.d/99-system-assistant-aur && "
                        "chmod 0440 /etc/sudoers.d/99-system-assistant-aur && "
                        "su - \"$TARGET_USER\" -c \"$AUR_HELPER -S --noconfirm brave-bin\"; "
                        "RC=$?; rm -f /etc/sudoers.d/99-system-assistant-aur; exit $RC; "
                        "else "
                        "pacman -S --needed --noconfirm flatpak && "
                        "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo && "
                        "flatpak install -y flathub com.brave.Browser; "
                        "fi"
                    )

            if needs_root and root_commands:
                self.log("Requesting administrator privileges...")
                combined_script = " && ".join(root_commands)
                self.run_cmd(["pkexec", "bash", "-c", combined_script])

            if tasks["adw_gtk3"]:
                if host_which("flatpak"):
                    self.run_cmd(
                        [
                            "flatpak",
                            "install",
                            "-y",
                            "flathub",
                            "org.gtk.Gtk3theme.adw-gtk3",
                            "org.gtk.Gtk3theme.adw-gtk3-dark",
                        ]
                    )
                if host_which("gsettings"):
                    self.run_cmd(
                        [
                            "gsettings",
                            "set",
                            "org.gnome.desktop.interface",
                            "gtk-theme",
                            "adw-gtk3-dark",
                        ]
                    )

            if tasks["win_buttons"] and host_which("gsettings"):
                self.run_cmd(
                    [
                        "gsettings",
                        "set",
                        "org.gnome.desktop.wm.preferences",
                        "button-layout",
                        ":minimize,maximize,close",
                    ]
                )

            if tasks["update"] and host_which("flatpak"):
                self.run_cmd(["flatpak", "update", "-y"])

            if tasks["flatpak_clean"] and host_which("flatpak"):
                self.run_cmd(["flatpak", "uninstall", "--unused", "-y"])

            if tasks["spotify"]:
                if host_which("flatpak"):
                    self.run_cmd(
                        ["flatpak", "install", "-y", "flathub", "com.spotify.Client"]
                    )
                else:
                    self.log("Flatpak is not installed. Skipping Spotify.")

            if tasks["gaming"]:
                if host_which("flatpak"):
                    self.run_cmd(
                        ["flatpak", "install", "-y", "flathub", "net.davidotek.pupgui2"]
                    )
                else:
                    self.log("Flatpak is not installed. Skipping ProtonUp-Qt.")

            self.log("\nAll selected tasks completed successfully!")
            self.show_toast("All selected tasks completed!")

            def _reset_and_refresh():
                for row in self.get_all_switch_rows():
                    row.set_active(False)
                self.refresh_detected_states()
                return False

            GLib.idle_add(_reset_and_refresh)
            self.hw_labels["storage"].set_label(get_storage_str())
            self.hw_labels["uptime"].set_label(get_uptime_str())
            self.refresh_detected_states()

        except subprocess.CalledProcessError as e:
            self.log(f"\nError: Command failed with exit code {e.returncode}")
            self.show_toast(f"Task failed (exit code {e.returncode})")
        finally:
            GLib.idle_add(self.reset_button)

    def reset_button(self):
        self._pulse_active = False
        self.progress_bar.set_visible(False)
        self.spinner.stop()
        self.run_btn.set_sensitive(True)
        self.btn_label.set_label("Run Selected Tasks")
        return False


class SystemAssistantApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.myrnop.SystemAssistant")

    def do_activate(self):
        win = SystemAssistantWindow(self)
        win.present()


if __name__ == "__main__":
    app = SystemAssistantApp()
    app.run(None)
