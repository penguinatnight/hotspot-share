import subprocess
import shutil
import base64

def set_system_clipboard_text(text: str) -> bool:
    if not text:
        return False

    # 1. Try wl-copy (Wayland native)
    if shutil.which("wl-copy"):
        try:
            p = subprocess.Popen(["wl-copy", "--type", "text/plain;charset=utf-8"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode('utf-8'), timeout=2)
            if p.returncode == 0:
                return True
        except Exception:
            pass

    # 2. Try xclip (X11)
    if shutil.which("xclip"):
        try:
            p = subprocess.Popen(["xclip", "-selection", "clipboard", "-in"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode('utf-8'), timeout=2)
            if p.returncode == 0:
                return True
        except Exception:
            pass

    # 3. Try xsel (X11)
    if shutil.which("xsel"):
        try:
            p = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode('utf-8'), timeout=2)
            if p.returncode == 0:
                return True
        except Exception:
            pass

    return False

def set_system_clipboard_image(raw_bytes: bytes, mime: str = 'image/png') -> bool:
    if not raw_bytes:
        return False

    # 1. Try wl-copy (Wayland native)
    if shutil.which("wl-copy"):
        try:
            p = subprocess.Popen(["wl-copy", "--type", mime], stdin=subprocess.PIPE)
            p.communicate(input=raw_bytes, timeout=3)
            if p.returncode == 0:
                return True
        except Exception:
            pass

    # 2. Try xclip (X11)
    if shutil.which("xclip"):
        try:
            p = subprocess.Popen(["xclip", "-selection", "clipboard", "-target", mime, "-in"], stdin=subprocess.PIPE)
            p.communicate(input=raw_bytes, timeout=3)
            if p.returncode == 0:
                return True
        except Exception:
            pass

    return False

def get_system_clipboard() -> dict:
    # 1. Try Wayland wl-paste
    if shutil.which("wl-paste"):
        # Check image first
        try:
            res = subprocess.run(["wl-paste", "--type", "image/png"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=1)
            if res.returncode == 0 and res.stdout:
                b64 = base64.b64encode(res.stdout).decode('ascii')
                return {'type': 'image', 'mime': 'image/png', 'data': f"data:image/png;base64,{b64}"}
        except Exception:
            pass

        try:
            res = subprocess.run(["wl-paste", "--no-newline"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=1)
            if res.returncode == 0 and res.stdout:
                return {'type': 'text', 'text': res.stdout.decode('utf-8', errors='ignore')}
        except Exception:
            pass

    # 2. Try X11 xclip
    if shutil.which("xclip"):
        try:
            res = subprocess.run(["xclip", "-selection", "clipboard", "-target", "image/png", "-out"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=1)
            if res.returncode == 0 and res.stdout:
                b64 = base64.b64encode(res.stdout).decode('ascii')
                return {'type': 'image', 'mime': 'image/png', 'data': f"data:image/png;base64,{b64}"}
        except Exception:
            pass

        try:
            res = subprocess.run(["xclip", "-selection", "clipboard", "-out"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=1)
            if res.returncode == 0 and res.stdout:
                return {'type': 'text', 'text': res.stdout.decode('utf-8', errors='ignore')}
        except Exception:
            pass

    return {'type': 'text', 'text': ''}
