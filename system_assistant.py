#!/usr/bin/env python3
import os
import platform
import shutil
import subprocess
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

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
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.startswith("ID="):
                    return line.strip().split("=")[1].strip('"').lower()
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
                if "[" in gpu_raw and "]" in gpu_raw:
                    gpu = gpu_raw.split("[")[-1].split("]")[0]
                else:
                    gpu = gpu_raw.split("(rev")[0].strip()
                break
    except Exception:
        pass

    return {
        "model": model,
        "cpu": cpu,
        "ram": ram,
        "gpu": gpu,
    }


class SystemAssistantWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(
            application=app,
            title="System Assistant",
            default_width=640,
            default_height=680,
        )
        self.distro = get_distro()
        self.pretty_os = get_os_pretty_name()
        self.kernel = platform.release()
        self.hw = get_hardware_info()

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
            margin_top=6,
            margin_bottom=6,
        )

        local_icon = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "io.github.myrnop.SystemAssistant.png",
        )
        if os.path.exists(local_icon):
            hero_icon = Gtk.Image.new_from_file(local_icon)
        else:
            hero_icon = Gtk.Image.new_from_icon_name("io.github.myrnop.SystemAssistant")
        hero_icon.set_pixel_size(76)

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

        hw_group = Adw.PreferencesGroup(title="System Hardware")
        hw_rows = [
            ("Device", self.hw["model"], "computer-symbolic"),
            ("Processor", self.hw["cpu"], "applications-electronics-symbolic"),
            ("Memory", self.hw["ram"], "drive-harddisk-symbolic"),
            ("Graphics", self.hw["gpu"], "video-display-symbolic"),
        ]
        for label_text, value_text, icon_name in hw_rows:
            row = Adw.ActionRow(title=label_text)
            row.add_prefix(Gtk.Image.new_from_icon_name(icon_name))
            val_label = Gtk.Label(label=value_text)
            val_label.add_css_class("dim-label")
            val_label.set_ellipsize(Pango.EllipsizeMode.END)
            val_label.set_max_width_chars(38)
            row.add_suffix(val_label)
            hw_group.add(row)

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
        maint_page.add(hw_tweaks_group)

        self.stack.add_titled_with_icon(
            maint_page, "maintenance", "Maintenance", "system-run-symbolic"
        )

        # --- TAB 3: TWEAKS & APPS ---
        apps_page = Adw.PreferencesPage()

        tweaks_group = Adw.PreferencesGroup(title="Desktop &amp; Codec Tweaks")
        self.row_rpmfusion = None
        if self.distro == "fedora":
            self.row_rpmfusion = self.create_switch_row(
                title="RPM Fusion &amp; Multimedia Codecs",
                subtitle="Enable RPM Fusion Free/Nonfree, OpenH264, and media codecs",
                icon_name="multimedia-player-symbolic",
                active=False,
            )
            tweaks_group.add(self.row_rpmfusion)

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

        software_group = Adw.PreferencesGroup(title="Essential Applications")
        self.row_tweaks = self.create_switch_row(
            title="GNOME Tweaks &amp; Extensions",
            subtitle="Install gnome-tweaks and Extension Manager",
            icon_name="applications-utilities-symbolic",
            active=False,
        )
        software_group.add(self.row_tweaks)

        self.row_spotify = self.create_switch_row(
            title="Spotify",
            subtitle="Install official Spotify client via Flathub",
            icon_name="folder-music-symbolic",
            active=False,
        )
        software_group.add(self.row_spotify)

        self.row_brave = self.create_switch_row(
            title="Brave Browser",
            subtitle="Configure Brave RPM repository and install browser",
            icon_name="web-browser-symbolic",
            active=False,
        )
        software_group.add(self.row_brave)
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

        self.run_btn = Gtk.Button(child=btn_content)
        self.run_btn.add_css_class("suggested-action")
        self.run_btn.add_css_class("pill")
        self.run_btn.set_halign(Gtk.Align.CENTER)
        self.run_btn.set_size_request(220, 42)
        self.run_btn.connect("clicked", self.on_run_clicked)
        bottom_box.append(self.run_btn)

        log_group = Adw.PreferencesGroup()
        self.log_expander = Adw.ExpanderRow(
            title="Task Output Log",
            subtitle="View live command execution details",
        )
        self.log_expander.add_prefix(
            Gtk.Image.new_from_icon_name("utilities-terminal-symbolic")
        )

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

    def on_about_clicked(self, button):
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="System Assistant",
            application_icon="io.github.myrnop.SystemAssistant",
            developer_name="MyrnChef",
            version="1.2.0",
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
            "pcspkr": self.row_pcspkr.get_active(),
            "rpmfusion": self.row_rpmfusion.get_active() if self.row_rpmfusion else False,
            "adw_gtk3": self.row_adw_gtk3.get_active(),
            "win_buttons": self.row_win_buttons.get_active(),
            "tweaks": self.row_tweaks.get_active(),
            "spotify": self.row_spotify.get_active(),
            "brave": self.row_brave.get_active(),
        }

        if not any(tasks.values()):
            self.show_toast("Select at least one task first")
            return

        self.run_btn.set_sensitive(False)
        self.spinner.start()
        self.btn_label.set_label("Running Tasks...")
        self.log_buffer.set_text("")
        self.log_expander.set_expanded(True)

        threading.Thread(target=self.execute_tasks, args=(tasks,), daemon=True).start()

    def execute_tasks(self, tasks):
        try:
            needs_root = (
                tasks["update"]
                or tasks["pkg_clean"]
                or tasks["journal_clean"]
                or tasks["pcspkr"]
                or (tasks["rpmfusion"] and self.distro == "fedora")
                or (tasks["adw_gtk3"] and self.distro in ["fedora", "arch"])
                or (tasks["tweaks"] and not host_which("gnome-tweaks"))
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
                    root_commands.append("pacman -Sc --noconfirm")

            if tasks["journal_clean"]:
                root_commands.append("journalctl --vacuum-time=7d")

            if tasks["pcspkr"]:
                root_commands.append("modprobe -r pcspkr snd_pcsp 2>/dev/null || true")
                root_commands.append(
                    "printf 'blacklist pcspkr\\nblacklist snd_pcsp\\n' > /etc/modprobe.d/blacklist-pcspkr.conf"
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

            if (
                tasks["brave"]
                and not host_which("brave-browser")
                and self.distro == "fedora"
            ):
                root_commands.append("dnf install -y dnf-plugins-core")
                root_commands.append(
                    "dnf config-manager addrepo --from-repofile=https://brave-browser-rpm-release.s3.brave.com/brave-browser.repo"
                )
                root_commands.append("dnf install -y brave-browser")

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

            self.log("\nAll selected tasks completed successfully!")
            self.show_toast("All selected tasks completed!")

        except subprocess.CalledProcessError as e:
            self.log(f"\nError: Command failed with exit code {e.returncode}")
            self.show_toast(f"Task failed (exit code {e.returncode})")
        finally:
            GLib.idle_add(self.reset_button)

    def reset_button(self):
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