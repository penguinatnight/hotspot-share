import os
import sys
import subprocess
import tempfile
import base64
import io
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / "web" / "style.css"
CSS_CONTENT = CSS_PATH.read_text(encoding="utf-8")

sys.path.insert(0, str(ROOT / "src"))
from hotspot_share.qr import get_svg_qr

QR_SVG = get_svg_qr("http://192.168.1.6:8080")

# Generate a high-res, attractive sample PNG photo using PIL for the clipboard and preview
def generate_sample_image_data_uri():
    img = Image.new('RGB', (640, 320), color='#0f172a')
    draw = ImageDraw.Draw(img)
    # Sunset gradient
    for y in range(320):
        factor = y / 320.0
        r = int(24 + (239 - 24) * factor)
        g = int(24 + (68 - 24) * (factor ** 1.5))
        b = int(72 + (68 - 72) * factor)
        draw.line([(0, y), (640, y)], fill=(r, g, b))

    # Sun
    draw.ellipse([460, 40, 560, 140], fill='#fbbf24')
    draw.ellipse([475, 55, 545, 125], fill='#fef08a')

    # Mountains
    draw.polygon([(0, 320), (120, 180), (220, 240), (380, 140), (520, 260), (640, 170), (640, 320)], fill='#18181b')
    draw.polygon([(0, 320), (80, 240), (200, 290), (320, 210), (480, 290), (640, 230), (640, 320)], fill='#09090b')

    # Water reflection lines
    for ly in range(270, 320, 8):
        draw.line([(350, ly), (580, ly)], fill='#f59e0b', width=2)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

SAMPLE_IMG_URI = generate_sample_image_data_uri()

BASE_HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <title>Hotspot Share</title>
  <style>
    {css}
    body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text-primary);
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      overflow-x: hidden;
      min-height: 100vh;
    }}
    .window-container {{
      max-width: 820px;
      margin: 0 auto;
      padding: 16px 20px 32px;
      box-sizing: border-box;
    }}
    /* Extra refinement for crisp screenshot typography */
    .summary-speed {{ color: var(--success) !important; font-weight: 700 !important; }}
    .queue-full-name {{ font-size: 14.5px !important; font-weight: 600 !important; }}
  </style>
</head>
<body>
  <div class="window-container">
    {content}
  </div>
</body>
</html>
"""

def make_header(active_tab="upload"):
    up = "active" if active_tab == "upload" else ""
    fl = "active" if active_tab == "files" else ""
    cl = "active" if active_tab == "clip" else ""
    return f"""
    <header class="header">
      <div class="tabs-container">
        <button class="tab-btn {up}" style="{'color:#fff;background:var(--slider-thumb);' if up else ''}">Upload</button>
        <button class="tab-btn {fl}" style="{'color:#fff;background:var(--slider-thumb);' if fl else ''}">Files</button>
        <button class="tab-btn {cl}" style="{'color:#fff;background:var(--slider-thumb);' if cl else ''}">Clipboard</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn-theme" title="Refresh">
          <svg viewBox="0 0 24 24" style="fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;"><path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        </button>
        <button class="btn-theme" title="Theme">
          <svg viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z"/></svg>
        </button>
      </div>
    </header>
    """

# ----------------------------------------------------------------------
# 1. SCREENSHOT 1: Live Multi-Transfer, Wi-Fi 6 Speedometer & Cancelled Queue
# ----------------------------------------------------------------------
CONTENT_SCREENSHOT1 = make_header("upload") + """
  <main>
    <section class="system-status-bar">
      <div class="status-row-top">
        <div class="device-presence">
          <div class="beacon-dot connected"></div>
          <span id="deviceNameLabel">Connected: Samsung Galaxy S24 Ultra (Wi-Fi 6)</span>
          <button class="btn-rename">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
            <span>Device / Storage</span>
          </button>
        </div>
        <div class="storage-metrics">
          <span id="diskSpaceText">Phone: 142.8 GB free / 256 GB &bull; PC: 343.6 GB free (73% free)</span>
        </div>
      </div>
      <div class="storage-bar-track">
        <div class="storage-bar-fill" style="width: 44%;"></div>
      </div>
    </section>

    <!-- Queue Summary Banner with real-time 48.5 MB/s speed and Cancel button -->
    <div class="queue-summary" id="queueSummary" style="display: flex;">
      <div class="summary-header">
        <span id="summaryCount" style="font-weight:600;color:var(--text-primary);">Receiving: 4K_Vacation_Cinematic.mp4 (1.8 GB / 2.4 GB)</span>
        <div class="summary-metrics">
          <span class="summary-speed" id="summarySpeed">⚡ 48.5 MB/s</span>
          <span class="summary-eta" id="summaryEta" style="color:var(--text-secondary);">12s left</span>
          <button type="button" class="btn-cancel" id="summaryCancelBtn">Cancel All</button>
        </div>
      </div>
      <div class="progress-track">
        <div class="progress-fill" id="summaryProgressFill" style="width: 75%; background: linear-gradient(90deg, #2563eb, #38bdf8);"></div>
      </div>
    </div>

    <!-- Active Transfers List -->
    <div class="queue-container" id="uploadQueue">
      <!-- Active Card -->
      <div class="queue-card active-transfer" style="border-left: 4px solid #38bdf8;">
        <div class="queue-title-row">
          <div class="queue-title-left">
            <div class="queue-full-name">4K_Vacation_Cinematic.mp4</div>
            <div class="queue-sender-info">From: Samsung Galaxy S24 Ultra &bull; High-speed Wi-Fi 6 streaming</div>
          </div>
          <div class="queue-title-right">
            <span class="queue-badge receiving" style="background:#0284c7;color:#fff;">Receiving 75%</span>
            <button type="button" class="btn-cancel">Cancel</button>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: 75%; background: linear-gradient(90deg, #2563eb, #38bdf8);"></div>
        </div>
        <div class="queue-stats-row">
          <span>1.8 GB of 2.4 GB &bull; 48.5 MB/s</span>
          <span style="color:#38bdf8;font-weight:600;">75%</span>
        </div>
      </div>

      <!-- Completed Card -->
      <div class="queue-card" style="border-left: 4px solid var(--success);">
        <div class="queue-title-row">
          <div class="queue-title-left">
            <div class="queue-full-name">Design_System_Assets_2026.zip</div>
            <div class="queue-sender-info">Saved directly to ~/Downloads/HotspotShare</div>
          </div>
          <div class="queue-title-right">
            <span class="queue-badge done">✓ Completed</span>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: 100%; background: var(--success);"></div>
        </div>
        <div class="queue-stats-row">
          <span>642.8 MB &bull; Integrity Verified</span>
          <span style="color:var(--success);font-weight:600;">100%</span>
        </div>
      </div>

      <!-- Cancelled Card -->
      <div class="queue-card" style="border-left: 4px solid var(--warning); opacity: 0.85;">
        <div class="queue-title-row">
          <div class="queue-title-left">
            <div class="queue-full-name">Raw_Camera_Roll_Archive.tar.gz</div>
            <div class="queue-sender-info">Cancelled by user at 350 MB / 1.2 GB</div>
          </div>
          <div class="queue-title-right">
            <span class="queue-badge cancelled">✕ Cancelled</span>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: 28%; background: var(--text-muted);"></div>
        </div>
        <div class="queue-stats-row">
          <span>Transfer aborted safely</span>
          <span style="color:var(--warning);font-weight:600;">28%</span>
        </div>
      </div>
    </div>

    <!-- Dropzone -->
    <div class="dropzone" id="dropzone" style="margin-top: 18px; padding: 28px 16px;">
      <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
      <h3>Drop files or folders here</h3>
      <p>Direct Wi-Fi 6 Transfer &bull; Unlimited file size &bull; No Internet required</p>
      <div class="action-buttons">
        <button type="button" class="btn-primary">Select Files</button>
        <button type="button" class="btn-secondary">Select Folder</button>
      </div>
    </div>
  </main>
"""

# ----------------------------------------------------------------------
# 2. SCREENSHOT 2: Mobile Smartphone Responsive View
# ----------------------------------------------------------------------
CONTENT_SCREENSHOT2 = """
<div style="display:flex; justify-content:center; align-items:center; min-height:85vh; padding: 20px 0;">
  <div style="width: 380px; background: #000000; border: 3px solid #27272a; border-radius: 40px; padding: 18px; box-shadow: 0 25px 60px rgba(0,0,0,0.8); position: relative;">
    <!-- Phone speaker / notch -->
    <div style="width: 90px; height: 18px; background: #27272a; border-radius: 20px; margin: 0 auto 16px;"></div>

    <header class="header" style="margin-bottom: 12px; padding: 0 0 12px 0;">
      <div class="tabs-container" style="transform: scale(0.9); transform-origin: left center;">
        <button class="tab-btn active" style="color:#fff;background:var(--slider-thumb);">Upload</button>
        <button class="tab-btn">Files</button>
        <button class="tab-btn">Clipboard</button>
      </div>
      <button class="btn-theme" style="width:30px;height:30px;"><svg viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z"/></svg></button>
    </header>

    <section class="system-status-bar" style="margin-bottom: 14px; padding: 10px 12px;">
      <div class="status-row-top">
        <div class="device-presence">
          <div class="beacon-dot connected"></div>
          <span style="font-weight:600;font-size:12.5px;color:var(--text-primary);">Galaxy S24 ⇄ Linux PC</span>
        </div>
      </div>
      <div class="storage-bar-track" style="margin-top: 6px;">
        <div class="storage-bar-fill" style="width: 58%;"></div>
      </div>
    </section>

    <div class="queue-summary" style="display:flex; margin-bottom: 14px; padding: 12px;">
      <div class="summary-header" style="flex-direction:column; align-items:flex-start; gap:4px;">
        <span style="font-weight:600;font-size:12.5px;color:var(--text-primary);">Uploading: IMG_8492_RAW.dng</span>
        <div class="summary-metrics" style="width:100%; justify-content:space-between;">
          <span class="summary-speed" style="color:var(--success);font-weight:700;font-size:12px;">⚡ 45.2 MB/s</span>
          <span class="summary-eta" style="font-size:11px;">ETA: 2s left</span>
        </div>
      </div>
      <div class="progress-track" style="margin-top:6px;">
        <div class="progress-fill" style="width: 82%; background: linear-gradient(90deg, #2563eb, #38bdf8);"></div>
      </div>
    </div>

    <div class="queue-container" style="display:flex; flex-direction:column; gap:8px; margin-bottom: 14px;">
      <div class="queue-card active-transfer" style="padding: 10px 12px;">
        <div class="queue-title-row">
          <span style="font-size:12px;font-weight:600;color:var(--text-primary);">IMG_8492_RAW.dng</span>
          <span class="queue-badge uploading" style="font-size:10px;padding:2px 6px;">82%</span>
        </div>
        <div class="progress-track" style="margin: 4px 0;">
          <div class="progress-fill" style="width: 82%; background: #38bdf8;"></div>
        </div>
        <div class="queue-stats-row" style="font-size:11px;">
          <span>112 MB / 136 MB</span>
          <span style="color:#38bdf8;font-weight:600;">82%</span>
        </div>
      </div>

      <div class="queue-card" style="padding: 10px 12px;">
        <div class="queue-title-row">
          <span style="font-size:12px;font-weight:600;color:var(--text-primary);">Holiday_Highlights.mp4</span>
          <span class="queue-badge done" style="font-size:10px;padding:2px 6px;">✓ Sent</span>
        </div>
        <div class="progress-track" style="margin: 4px 0;">
          <div class="progress-fill" style="width: 100%; background: var(--success);"></div>
        </div>
        <div class="queue-stats-row" style="font-size:11px;">
          <span>480 MB &bull; Transferred</span>
          <span style="color:var(--success);font-weight:600;">100%</span>
        </div>
      </div>
    </div>

    <div class="dropzone" style="padding: 20px 14px; border-radius: 14px;">
      <svg viewBox="0 0 24 24" style="width:32px;height:32px;fill:var(--primary);margin-bottom:6px;"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
      <h3 style="font-size:14px;margin-bottom:2px;">Share Photos &amp; Videos</h3>
      <p style="font-size:11px;margin-bottom:10px;color:var(--text-secondary);">Direct browser upload &bull; No app install</p>
      <button type="button" class="btn-primary" style="width:100%;padding:10px;font-size:13px;border-radius:10px;">Select From Phone Gallery</button>
    </div>
  </div>
</div>
"""

# ----------------------------------------------------------------------
# 3. SCREENSHOT 3: File Explorer, Directory Navigation, ZIP Download & Previews
# ----------------------------------------------------------------------
CONTENT_SCREENSHOT3 = make_header("files") + """
  <main>
    <section class="system-status-bar">
      <div class="status-row-top">
        <div class="device-presence">
          <div class="beacon-dot connected"></div>
          <span style="font-weight:600;color:var(--text-primary);">Shared Directory: ~/Downloads/HotspotShare</span>
        </div>
        <div class="storage-metrics">
          <span>18 Items &bull; 4.8 GB Total</span>
        </div>
      </div>
      <div class="storage-bar-track">
        <div class="storage-bar-fill" style="width: 32%;"></div>
      </div>
    </section>

    <!-- Breadcrumbs -->
    <div class="breadcrumbs" id="breadcrumbs" style="margin-top: 14px; margin-bottom: 12px;">
      <span class="crumb" style="cursor:pointer;color:var(--primary);font-weight:600;">from-phone</span>
      <span class="crumb-separator">/</span>
      <span class="crumb" style="cursor:pointer;color:var(--primary);font-weight:600;">Vacation_2026</span>
      <span class="crumb-separator">/</span>
      <span class="crumb-current" style="font-weight:600;">Media</span>
    </div>

    <!-- Toolbar -->
    <div class="files-toolbar">
      <input type="text" class="search-input" placeholder="Filter files..." value="mp4, raw" style="color:var(--text-primary);">
      <button class="btn-secondary" style="padding:6px 14px;font-size:13px;">+ Folder</button>
      <button class="btn-secondary" style="padding:6px 14px;font-size:13px;">Refresh</button>
      <button class="btn-primary" style="padding:6px 16px;font-size:13px;">Download All (ZIP)</button>
      <button class="btn-secondary" style="padding:6px 14px;font-size:13px;color:var(--danger);">Clear All</button>
    </div>

    <!-- File List -->
    <div class="file-list" style="display:flex; flex-direction:column; gap:10px;">
      <!-- Folder Item -->
      <div class="file-item is-folder">
        <div class="file-info">
          <svg class="file-icon" viewBox="0 0 24 24" style="fill:#38bdf8;"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
          <div class="file-details">
            <div class="file-title">Drone_RAW_Footage/</div>
            <div class="file-sub">24 items &bull; Today 21:40</div>
          </div>
        </div>
        <div class="file-actions">
          <button class="action-btn">Open</button>
          <a class="action-btn" href="#" style="color:#38bdf8;">ZIP</a>
          <button class="action-btn btn-del">Delete</button>
        </div>
      </div>

      <!-- Video File Item -->
      <div class="file-item">
        <div class="file-info">
          <svg class="file-icon" viewBox="0 0 24 24" style="fill:#c084fc;"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z"/></svg>
          <div class="file-details">
            <div class="file-title">Sunset_Timelapse_4K.mp4</div>
            <div class="file-sub">842.5 MB &bull; Today 22:10</div>
          </div>
        </div>
        <div class="file-actions">
          <button class="action-btn" style="color:var(--success);font-weight:600;">Preview</button>
          <a class="action-btn" href="#">Download</a>
          <button class="action-btn btn-del">Delete</button>
        </div>
      </div>

      <!-- Audio File Item -->
      <div class="file-item">
        <div class="file-info">
          <svg class="file-icon" viewBox="0 0 24 24" style="fill:#fb923c;"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
          <div class="file-details">
            <div class="file-title">Acoustic_Concert_Audio.flac</div>
            <div class="file-sub">58.4 MB &bull; Today 21:55</div>
          </div>
        </div>
        <div class="file-actions">
          <button class="action-btn" style="color:var(--success);font-weight:600;">Preview</button>
          <a class="action-btn" href="#">Download</a>
          <button class="action-btn btn-del">Delete</button>
        </div>
      </div>

      <!-- Image File Item -->
      <div class="file-item">
        <div class="file-info">
          <svg class="file-icon" viewBox="0 0 24 24" style="fill:#34d399;"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>
          <div class="file-details">
            <div class="file-title">Dolomites_Panorama_HDR.png</div>
            <div class="file-sub">18.2 MB &bull; Today 21:30</div>
          </div>
        </div>
        <div class="file-actions">
          <button class="action-btn" style="color:var(--success);font-weight:600;">Preview</button>
          <a class="action-btn" href="#">Download</a>
          <button class="action-btn btn-del">Delete</button>
        </div>
      </div>

      <!-- Archive File Item -->
      <div class="file-item">
        <div class="file-info">
          <svg class="file-icon" viewBox="0 0 24 24" style="fill:#facc15;"><path d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-6 10h-2v-2h2v2zm0-4h-2v-2h2v2zm-4-4h2v2h-2V8z"/></svg>
          <div class="file-details">
            <div class="file-title">Full_Project_Backup.zip</div>
            <div class="file-sub">1.45 GB &bull; Today 20:15</div>
          </div>
        </div>
        <div class="file-actions">
          <a class="action-btn" href="#">Download</a>
          <button class="action-btn btn-del">Delete</button>
        </div>
      </div>
    </div>
  </main>
"""

# ----------------------------------------------------------------------
# 4. SCREENSHOT 4: Multimodal Clipboard (Text & Image Sync with Ctrl+V)
# ----------------------------------------------------------------------
CONTENT_SCREENSHOT4 = make_header("clip") + f"""
  <main>
    <section class="system-status-bar">
      <div class="status-row-top">
        <div class="device-presence">
          <div class="beacon-dot connected"></div>
          <span style="font-weight:600;color:var(--text-primary);">Multimodal Clipboard Sync (Linux PC ⇄ Phone)</span>
        </div>
        <div class="storage-metrics">
          <span style="color:var(--success);font-weight:600;">✓ Desktop Ctrl+V Ready</span>
        </div>
      </div>
      <div class="storage-bar-track">
        <div class="storage-bar-fill" style="width: 25%;"></div>
      </div>
    </section>

    <div class="clip-wrapper" style="margin-top: 16px;">
      <!-- PC Image Clipboard Card -->
      <div class="clip-card">
        <div class="clip-header">
          <span style="font-weight:600;color:var(--text-primary);">PC CLIPBOARD (IMAGE COPIED FROM LINUX DESKTOP)</span>
          <div style="display:flex;gap:6px;align-items:center;">
            <button class="btn-secondary" style="padding:4px 10px;font-size:12px;">Fetch from PC</button>
            <button class="btn-secondary" style="padding:4px 10px;font-size:12px;">✕ Reset</button>
          </div>
        </div>

        <div class="clip-image-preview" style="display:flex; flex-direction:column; gap:10px; margin-top:10px;">
          <div style="width:100%;display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:12.5px;color:var(--text-secondary);">Image from PC (image/png &bull; 2.4 MB &bull; Copied with Ctrl+C on Linux)</div>
            <button class="action-btn btn-del">✕ Close Preview</button>
          </div>
          <img class="clip-img-tag" src="{SAMPLE_IMG_URI}" alt="Copied Image from PC" style="width:100%;max-height:180px;object-fit:cover;border-radius:10px;border:1px solid var(--border);">
          <div class="clip-actions" style="margin-top:4px;">
            <a class="btn-primary" href="#" style="font-size:13px;padding:8px 18px;">Save Image to Phone</a>
            <button class="btn-secondary" style="font-size:13px;padding:8px 16px;">Copy Image</button>
            <button class="btn-secondary" style="font-size:13px;padding:8px 16px;">Save to Files</button>
          </div>
        </div>
      </div>

      <!-- Text & Image Send to PC Card -->
      <div class="clip-card" style="margin-top: 14px;">
        <div class="clip-header">
          <span style="font-weight:600;color:var(--text-primary);">SEND TEXT &amp; CODE TO PC (INSTANT CTRL+V BUFFER)</span>
        </div>
        <div style="margin-top: 10px;">
          <textarea class="clip-box" style="height:75px;font-family:monospace;font-size:13.5px;line-height:1.5;color:var(--text-primary);">git clone https://github.com/penguinatnight/hotspot-share
cd hotspot-share && make install-user
# Direct Wi-Fi 6 pairing active &bull; Press Ctrl+V on PC</textarea>
          <div class="clip-actions" style="margin-top:10px;">
            <button class="btn-secondary" style="font-size:13px;padding:8px 16px;">✕ Clear Text</button>
            <button class="btn-secondary" style="font-size:13px;padding:8px 16px;">Copy Text</button>
            <button class="btn-primary" style="font-size:13px;padding:8px 20px;">Send Text to PC (Ctrl+V)</button>
          </div>
        </div>
      </div>

      <!-- Send Image to PC Clipboard Card -->
      <div class="clip-card" style="margin-top: 14px;">
        <div class="clip-header">
          <span style="font-weight:600;color:var(--text-primary);">SEND IMAGE TO PC CLIPBOARD</span>
        </div>
        <p style="font-size:12.5px;color:var(--text-secondary);margin:8px 0 12px;">
          Select or paste an image here to copy it directly into your PC's clipboard. You can immediately press <b>Ctrl+V</b> in Discord, Telegram, Slack, LibreOffice, GIMP, or any PC app.
        </p>
        <div class="clip-actions">
          <button class="btn-secondary" style="font-size:13px;padding:8px 18px;">Select Image to Copy</button>
          <button class="btn-primary" style="font-size:13px;padding:8px 20px;">Send Image to PC (Ctrl+V)</button>
        </div>
      </div>
    </div>
  </main>
"""

# ----------------------------------------------------------------------
# 5. SCREENSHOT 5: QR Code Device Pairing & Secure PIN Dashboard
# ----------------------------------------------------------------------
CONTENT_SCREENSHOT5 = make_header("upload") + f"""
  <main>
    <section class="system-status-bar">
      <div class="status-row-top">
        <div class="device-presence">
          <div class="beacon-dot" style="background: #e3b341; box-shadow: 0 0 10px #e3b341;"></div>
          <span style="font-weight:600;color:var(--text-primary);">Waiting for phone connection... (Wi-Fi AP Active)</span>
          <button class="btn-rename">
            <span>Refresh</span>
          </button>
        </div>
        <div class="storage-metrics">
          <span>PC Storage: 343.6 GB free / 468.3 GB (73% free)</span>
        </div>
      </div>
      <div class="storage-bar-track">
        <div class="storage-bar-fill" style="width: 27%;"></div>
      </div>
    </section>

    <!-- Connect Card with Crisp QR Canvas/SVG -->
    <section class="qr-connect-card" style="display: flex; margin-top: 18px; padding: 22px 24px;">
      <div class="qr-box">
        {QR_SVG}
      </div>
      <div class="qr-details" style="padding-left: 10px;">
        <div class="qr-title" style="font-size:18px;font-weight:700;color:var(--text-primary);">Connect Your Phone</div>
        <div class="qr-desc" style="font-size:13px;line-height:1.5;color:var(--text-secondary);">
          Make sure your laptop is connected to your phone's Wi-Fi hotspot, then scan this QR code with your phone camera. No app install needed.
        </div>
        <div style="display:flex;gap:12px;align-items:center;margin-top:6px;">
          <div class="qr-link-badge" style="font-size:14px;font-weight:700;color:var(--text-primary);">http://192.168.1.6:8080</div>
          <div style="background:rgba(50,215,75,0.15);border:1px solid rgba(50,215,75,0.4);color:var(--success);padding:6px 12px;border-radius:8px;font-size:12.5px;font-weight:700;">
            PAIRING PIN: 4829
          </div>
        </div>
      </div>
    </section>

    <!-- Dropzone Area -->
    <div class="dropzone" id="dropzone" style="margin-top: 20px; padding: 40px 24px;">
      <svg viewBox="0 0 24 24" style="width:44px;height:44px;fill:var(--text-secondary);margin-bottom:10px;"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
      <h3 style="font-size:18px;margin-bottom:4px;">Drop files or folders here</h3>
      <p style="font-size:13px;color:var(--text-secondary);margin-bottom:16px;">Direct Wi-Fi 6 Transfer &bull; Saves directly to ~/Downloads/HotspotShare</p>
      <div class="action-buttons">
        <button type="button" class="btn-primary" style="padding:10px 24px;font-size:14px;">Select Files</button>
        <button type="button" class="btn-secondary" style="padding:10px 24px;font-size:14px;">Select Folder</button>
      </div>
    </div>
  </main>
"""

def render_screenshot(content, out_path, width=1280, height=850):
    html = BASE_HTML_WRAPPER.format(css=CSS_CONTENT, content=content)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
        tmp_html = f.name

    try:
        cmd = [
            "google-chrome",
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            f"--screenshot={out_path}",
            f"file://{tmp_html}"
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Generated {out_path} ({width}x{height})")
    finally:
        Path(tmp_html).unlink(missing_ok=True)

def main():
    dest_dir = ROOT / "assets" / "screenshots"
    dest_dir.mkdir(parents=True, exist_ok=True)

    render_screenshot(CONTENT_SCREENSHOT1, dest_dir / "screenshot1.png", 1280, 850)
    render_screenshot(CONTENT_SCREENSHOT2, dest_dir / "screenshot2.png", 640, 850)
    render_screenshot(CONTENT_SCREENSHOT3, dest_dir / "screenshot3.png", 1280, 850)
    render_screenshot(CONTENT_SCREENSHOT4, dest_dir / "screenshot4.png", 1280, 920)
    render_screenshot(CONTENT_SCREENSHOT5, dest_dir / "screenshot5.png", 1280, 850)

if __name__ == "__main__":
    main()
