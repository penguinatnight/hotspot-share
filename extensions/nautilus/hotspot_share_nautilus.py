"""
Hotspot Share - Nautilus / Nemo / Caja File Manager Extension
Adds right-click "Send via Hotspot Share" context menu to share files instantly.
"""

import os
import shutil
import subprocess
from urllib.parse import unquote
from gi.repository import Nautilus, GObject

class HotspotShareExtension(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        pass

    def get_shared_dir(self):
        xdg_download = os.environ.get("XDG_DOWNLOAD_DIR")
        if xdg_download and os.path.exists(xdg_download):
            target = os.path.join(xdg_download, "HotspotShare")
        elif os.path.exists(os.path.expanduser("~/Downloads")):
            target = os.path.expanduser("~/Downloads/HotspotShare")
        elif os.path.exists(os.path.expanduser("~/Desktop")):
            target = os.path.expanduser("~/Desktop/from-phone")
        else:
            target = os.path.expanduser("~/HotspotShare")
        os.makedirs(target, exist_ok=True)
        return target

    def menu_activate_cb(self, menu, files):
        dest_dir = self.get_shared_dir()
        for file_obj in files:
            uri = file_obj.get_uri()
            if uri.startswith("file://"):
                src_path = unquote(uri[7:])
                if os.path.exists(src_path):
                    base_name = os.path.basename(src_path)
                    dest_path = os.path.join(dest_dir, base_name)
                    try:
                        if os.path.isdir(src_path):
                            if os.path.exists(dest_path):
                                shutil.rmtree(dest_path)
                            shutil.copytree(src_path, dest_path)
                        else:
                            shutil.copy2(src_path, dest_path)
                    except Exception as e:
                        print(f"HotspotShare copy error: {e}")

        # Launch or focus Hotspot Share GUI
        try:
            subprocess.Popen(["hotspot-share-gui"])
        except Exception:
            pass

    def get_file_items(self, *args):
        # Nautilus 43+ passes (window, files), older passes (files)
        files = args[-1]
        if not files:
            return []

        item = Nautilus.MenuItem(
            name="HotspotShareExtension::SendFiles",
            label="Send via Hotspot Share",
            tip="Make selected files instantly available to connected phones",
            icon="hotspot-share"
        )
        item.connect("activate", self.menu_activate_cb, files)
        return [item]
