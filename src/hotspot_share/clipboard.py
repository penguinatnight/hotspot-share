import subprocess
import shutil
import base64

ALLOWED_IMAGE_MIMES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif', 'image/bmp'
}

def _run_pipe(cmd, input_bytes: bytes, timeout: int = 3) -> bool:
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            p.communicate(input=input_bytes, timeout=timeout)
            return p.returncode == 0
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            return False
    except Exception:
        return False

def set_system_clipboard_text(text: str) -> bool:
    if not text:
        return False

    raw_bytes = text.encode('utf-8')

    # 1. Try wl-copy (Wayland native)
    if shutil.which("wl-copy"):
        if _run_pipe(["wl-copy", "--type", "text/plain;charset=utf-8"], raw_bytes, timeout=2):
            return True

    # 2. Try xclip (X11)
    if shutil.which("xclip"):
        if _run_pipe(["xclip", "-selection", "clipboard", "-in"], raw_bytes, timeout=2):
            return True

    # 3. Try xsel (X11)
    if shutil.which("xsel"):
        if _run_pipe(["xsel", "--clipboard", "--input"], raw_bytes, timeout=2):
            return True

    return False

def set_system_clipboard_image(raw_bytes: bytes, mime: str = 'image/png') -> bool:
    if not raw_bytes:
        return False

    if mime not in ALLOWED_IMAGE_MIMES:
        mime = 'image/png'

    # 1. Try wl-copy (Wayland native)
    if shutil.which("wl-copy"):
        if _run_pipe(["wl-copy", "--type", mime], raw_bytes, timeout=3):
            return True

    # 2. Try xclip (X11)
    if shutil.which("xclip"):
        if _run_pipe(["xclip", "-selection", "clipboard", "-target", mime, "-in"], raw_bytes, timeout=3):
            return True

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

    # 3. Try X11 xsel (text fallback)
    if shutil.which("xsel"):
        try:
            res = subprocess.run(["xsel", "--clipboard", "--output"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=1)
            if res.returncode == 0 and res.stdout:
                return {'type': 'text', 'text': res.stdout.decode('utf-8', errors='ignore')}
        except Exception:
            pass

    return {'type': 'text', 'text': ''}

