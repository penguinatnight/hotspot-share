let currentPath = '';
let allItems = [];
let currentPcImageData = null;
let cachedNickname = localStorage.getItem('hotspot_device_nickname') || '';
let cachedCustomModel = localStorage.getItem('hotspot_phone_model') || '';
let cachedStorageGb = parseInt(localStorage.getItem('hotspot_phone_storage_gb') || '0', 10);
let currentConnectedPhoneIp = '';
let currentConnectedPhoneName = '';
let isLocalClient = false;
let pcHostName = '';
let activeServerTransferId = null;

let pendingClipImageFile = null;
let pendingClipImageBase64 = null;

let authToken = localStorage.getItem('hotspot_share_token') || '';
const _urlParams = new URLSearchParams(window.location.search);
if (_urlParams.get('token')) {
  authToken = _urlParams.get('token');
  localStorage.setItem('hotspot_share_token', authToken);
}

function authHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (authToken) {
    headers['Authorization'] = 'Bearer ' + authToken;
  }
  return headers;
}

let pinModalShown = false;

function showPinAuthModal(msg = '') {
  if (pinModalShown) return;
  pinModalShown = true;

  const html = `
    <h3 style="margin-bottom:12px;font-size:18px;">PIN Verification</h3>
    <p style="color:var(--text-secondary);font-size:14px;margin-bottom:16px;">
      This Hotspot Share server requires pairing. Enter the 4-digit PIN shown on the PC screen:
    </p>
    ${msg ? `<p style="color:#ef4444;font-size:13px;margin-bottom:12px;">${escapeHtml(msg)}</p>` : ''}
    <div style="display:flex;gap:8px;justify-content:center;margin-bottom:20px;">
      <input type="text" id="pinAuthInput" maxlength="6" placeholder="PIN" autocomplete="one-time-code" inputmode="numeric" pattern="[0-9]*"
        style="width:140px;font-size:24px;text-align:center;letter-spacing:4px;padding:8px 12px;border-radius:8px;border:1px solid var(--border-color);background:var(--bg-card);color:var(--text-primary);"
        onkeydown="if(event.key==='Enter') submitPinAuth()">
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end;">
      <button class="btn-primary" onclick="submitPinAuth()">Pair & Connect</button>
    </div>
  `;
  document.getElementById('modalBody').innerHTML = html;
  document.getElementById('modal').classList.add('active');
  setTimeout(() => {
    const inp = document.getElementById('pinAuthInput');
    if (inp) inp.focus();
  }, 100);
}

async function submitPinAuth() {
  const inp = document.getElementById('pinAuthInput');
  const pin = inp ? inp.value.trim() : '';
  if (!pin) return;

  try {
    const res = await fetch('/api/auth/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin })
    });
    const data = await res.json();
    if (res.ok && data.status === 'ok' && data.token) {
      authToken = data.token;
      localStorage.setItem('hotspot_share_token', authToken);
      pinModalShown = false;
      document.getElementById('modal').classList.remove('active');
      showToast('Paired successfully!');
      sendHeartbeatAndPollStatus();
      loadFiles();
      loadClip();
    } else {
      pinModalShown = false;
      showPinAuthModal(data.message || 'Invalid PIN code. Please try again.');
    }
  } catch (e) {
    pinModalShown = false;
    showPinAuthModal('Connection error: ' + e.message);
  }
}


function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatSpeed(bytesPerSec) {
  if (bytesPerSec >= 1024 * 1024) {
    return (bytesPerSec / (1024 * 1024)).toFixed(1) + ' MB/s';
  }
  const kb = bytesPerSec / 1024;
  return Math.round(kb).toLocaleString() + ' KB/s';
}

function detectHardwareProfile() {
  const profile = {
    model: '',
    gpu: '',
    vendor: '',
    cores: navigator.hardwareConcurrency || 8,
    ramGb: navigator.deviceMemory || 8,
    screenWidth: Math.round(window.screen.width * (window.devicePixelRatio || 1)),
    screenHeight: Math.round(window.screen.height * (window.devicePixelRatio || 1)),
    dpr: window.devicePixelRatio || 1,
    ua: navigator.userAgent
  };

  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      if (debugInfo) {
        profile.gpu = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || '';
        profile.vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || '';
      }
    }
  } catch (e) {}

  const gpu = profile.gpu;
  const w = Math.min(profile.screenWidth, profile.screenHeight);
  const h = Math.max(profile.screenWidth, profile.screenHeight);
  const ua = profile.ua;

  // 1. Direct UA non-frozen model match
  const uaMatch = ua.match(/;\s*([A-Za-z0-9\-\s_+]+)\s*(?:Build\/|\))/);
  if (uaMatch && uaMatch[1] && uaMatch[1].trim().toUpperCase() !== 'K') {
    profile.model = uaMatch[1].trim();
    return profile;
  }

  // 2. Apple iOS resolution fingerprinting
  if (/iPhone/i.test(ua)) {
    if (h >= 2796) profile.model = 'iPhone 15/16 Pro Max';
    else if (h >= 2556) profile.model = 'iPhone 15/16 Pro';
    else if (h >= 2532) profile.model = 'iPhone 13/14/15';
    else profile.model = 'Apple iPhone';
    return profile;
  }
  if (/iPad/i.test(ua)) {
    profile.model = 'Apple iPad';
    return profile;
  }

  // 3. Android WebGL GPU SoC & Physical Display Profiler
  if (/Android/i.test(ua)) {
    if (/Adreno.*750/i.test(gpu)) {
      profile.model = (w >= 1400) ? 'Samsung Galaxy S24 Ultra' : 'Samsung Galaxy S24+ (Snapdragon)';
    } else if (/Adreno.*740/i.test(gpu)) {
      profile.model = (w >= 1400) ? 'Samsung Galaxy S23 Ultra' : 'Samsung Galaxy S23+';
    } else if (/Adreno.*730/i.test(gpu)) {
      profile.model = (w >= 1400) ? 'Samsung Galaxy S22 Ultra' : 'Samsung Galaxy S22+';
    } else if (/Adreno.*660/i.test(gpu)) {
      profile.model = (w >= 1400) ? 'Samsung Galaxy S21 Ultra' : 'Samsung Galaxy S21';
    } else if (/Adreno.*650/i.test(gpu)) {
      profile.model = 'Samsung Galaxy S20 / POCO F3';
    } else if (/Adreno.*642/i.test(gpu)) {
      profile.model = 'Samsung Galaxy A52s 5G';
    } else if (/Adreno.*619/i.test(gpu)) {
      profile.model = 'Samsung Galaxy A52 5G / A34';
    } else if (/Mali-G615/i.test(gpu)) {
      profile.model = 'Samsung Galaxy A55 5G';
    } else if (/Mali-G68/i.test(gpu)) {
      profile.model = 'Samsung Galaxy A54 5G';
    } else if (/Mali-G715|Immortalis-G715/i.test(gpu)) {
      profile.model = (w >= 1344) ? 'Google Pixel 8 Pro' : 'Google Pixel 8';
    } else if (/Mali-G710/i.test(gpu)) {
      profile.model = (w >= 1400) ? 'Google Pixel 7 Pro' : 'Google Pixel 7';
    } else if (/Mali-G78/i.test(gpu)) {
      profile.model = (w >= 1400) ? 'Google Pixel 6 Pro' : 'Samsung Galaxy S21 / Pixel 6';
    } else if (/Mali-G77/i.test(gpu)) {
      profile.model = 'Samsung Galaxy S20 (Exynos)';
    } else if (/Xclipse 940/i.test(gpu)) {
      profile.model = 'Samsung Galaxy S24 (Exynos)';
    } else if (/Xclipse 920/i.test(gpu)) {
      profile.model = 'Samsung Galaxy S22 (Exynos)';
    } else if (/Mali-G57/i.test(gpu)) {
      profile.model = 'Samsung Galaxy A14 5G / A15';
    } else {
      profile.model = 'Android Smartphone';
    }
  } else if (/Macintosh/i.test(ua)) {
    profile.model = 'Apple Mac';
  } else if (/Windows/i.test(ua)) {
    profile.model = 'Windows PC';
  } else if (/Linux/i.test(ua)) {
    profile.model = 'Linux Desktop';
  }
  return profile;
}

async function getPhoneStorageInfo() {
  let quota = 0;
  let usage = 0;
  if (navigator.storage && navigator.storage.estimate) {
    try {
      const est = await navigator.storage.estimate();
      if (est && est.quota) {
        quota = est.quota;
        usage = est.usage || 0;
      }
    } catch (e) {}
  }

  // If user specified custom physical capacity
  if (cachedStorageGb > 0) {
    const totalBytes = cachedStorageGb * 1024 * 1024 * 1024;
    // Estimate used based on web sandbox or realistic 35% OS overhead
    const usedBytes = Math.min(totalBytes * 0.9, Math.max(totalBytes * 0.28, usage * 10));
    const freeBytes = Math.max(0, totalBytes - usedBytes);
    return {
      free_bytes: freeBytes,
      total_bytes: totalBytes,
      used_bytes: usedBytes,
      free_str: formatBytes(freeBytes),
      total_str: formatBytes(totalBytes),
      pct_free: Math.round((freeBytes / totalBytes) * 100),
      pct_used: Math.round((usedBytes / totalBytes) * 100),
      is_physical: true
    };
  }

  if (quota > 0) {
    const free = Math.max(0, quota - usage);
    return {
      free_bytes: free,
      total_bytes: quota,
      used_bytes: usage,
      free_str: formatBytes(free),
      total_str: formatBytes(quota),
      pct_free: Math.round((free / quota) * 100),
      pct_used: Math.round((usage / quota) * 100),
      is_physical: false
    };
  }
  return null;
}

function openDeviceSettingsModal() {
  const profile = detectHardwareProfile();
  const currentModel = cachedCustomModel || cachedNickname || (profile.model !== 'Linux Desktop' && profile.model !== 'Windows PC' && profile.model !== 'Apple Mac' ? profile.model : '') || 'Samsung Galaxy A54 5G';
  const currentStorage = cachedStorageGb || 128;

  const html = `
    <h3 style="font-size:17px;font-weight:600;margin-bottom:4px;">Device & Storage Configuration</h3>
    <p style="font-size:12px;color:var(--text-secondary);margin-bottom:12px;">
      Auto-profiled GPU: <b>${escapeHtml(profile.gpu || 'Mobile GPU')}</b> &bull; Display: <b>${profile.screenWidth}x${profile.screenHeight}</b>
    </p>

    <div class="config-group">
      <label class="config-label">Device Name / Model</label>
      <input type="text" id="cfgDeviceName" class="config-input" value="${escapeHtml(currentModel)}" placeholder="e.g. Samsung Galaxy S24 Ultra">
      
      <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-top:6px;">QUICK SELECT POPULAR MODELS:</div>
      <div class="presets-grid">
        <button type="button" class="preset-chip" onclick="setCfgModel('Samsung Galaxy S24 Ultra')">S24 Ultra</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Samsung Galaxy S23 Ultra')">S23 Ultra</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Samsung Galaxy A55 5G')">Galaxy A55 5G</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Samsung Galaxy A54 5G')">Galaxy A54 5G</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Samsung Galaxy A35 5G')">Galaxy A35 5G</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Samsung Galaxy A15 5G')">Galaxy A15 5G</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Google Pixel 9 Pro XL')">Pixel 9 Pro XL</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Google Pixel 8 Pro')">Pixel 8 Pro</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Google Pixel 8a')">Pixel 8a</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('iPhone 16 Pro Max')">iPhone 16 Pro Max</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('iPhone 15 Pro')">iPhone 15 Pro</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('OnePlus 12')">OnePlus 12</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('POCO X6 Pro')">POCO X6 Pro</button>
        <button type="button" class="preset-chip" onclick="setCfgModel('Xiaomi 14')">Xiaomi 14</button>
      </div>
    </div>

    <div class="config-group" style="margin-top:12px;">
      <label class="config-label">Phone Total Storage Capacity</label>
      <div class="presets-grid">
        <button type="button" class="preset-chip ${currentStorage === 64 ? 'active' : ''}" onclick="setCfgStorage(64)">64 GB</button>
        <button type="button" class="preset-chip ${currentStorage === 128 ? 'active' : ''}" onclick="setCfgStorage(128)">128 GB</button>
        <button type="button" class="preset-chip ${currentStorage === 256 ? 'active' : ''}" onclick="setCfgStorage(256)">256 GB</button>
        <button type="button" class="preset-chip ${currentStorage === 512 ? 'active' : ''}" onclick="setCfgStorage(512)">512 GB</button>
        <button type="button" class="preset-chip ${currentStorage === 1024 ? 'active' : ''}" onclick="setCfgStorage(1024)">1 TB</button>
      </div>
      <input type="number" id="cfgStorageCustom" class="config-input" style="margin-top:6px;" value="${currentStorage}" placeholder="Storage in GB">
    </div>

    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="saveDeviceConfig()">Save & Apply</button>
    </div>
  `;
  document.getElementById('modalBody').innerHTML = html;
  document.getElementById('modal').classList.add('active');
}

function setCfgModel(name) {
  document.getElementById('cfgDeviceName').value = name;
}

function setCfgStorage(gb) {
  document.getElementById('cfgStorageCustom').value = gb;
}

async function saveDeviceConfig() {
  const name = document.getElementById('cfgDeviceName').value.trim();
  const gb = parseInt(document.getElementById('cfgStorageCustom').value, 10) || 128;

  if (name) {
    cachedNickname = name;
    cachedCustomModel = name;
    localStorage.setItem('hotspot_device_nickname', name);
    localStorage.setItem('hotspot_phone_model', name);
  }
  cachedStorageGb = gb;
  localStorage.setItem('hotspot_phone_storage_gb', gb.toString());

  try {
    await fetch('/api/rename_device', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        ip: isLocalClient ? currentConnectedPhoneIp : '',
        name: name
      })
    });
  } catch (e) {}

  closeModal();
  showToast('Device updated: ' + (name || `${gb} GB`));
  sendHeartbeatAndPollStatus();
}

let lastActiveTransferCount = 0;

async function sendHeartbeatAndPollStatus() {
  try {
    const hw = detectHardwareProfile();
    let modelToSend = '';
    let nickToSend = '';

    if (!isLocalClient) {
      modelToSend = cachedCustomModel || cachedNickname || (hw.model !== 'Linux Desktop' && hw.model !== 'Windows PC' && hw.model !== 'Apple Mac' ? hw.model : '') || '';
      nickToSend = cachedNickname || cachedCustomModel || '';
      if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
        try {
          const hints = await navigator.userAgentData.getHighEntropyValues(['model']);
          if (hints.model) modelToSend = hints.model;
        } catch (e) {}
      }
    }

    const phoneStorage = (!isLocalClient) ? await getPhoneStorageInfo() : null;

    const hbRes = await fetch('/api/heartbeat', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        ua: navigator.userAgent,
        model: modelToSend,
        nickname: nickToSend,
        storage: phoneStorage
      })
    });
    if (hbRes.status === 401) {
      showPinAuthModal();
      return;
    }

    const res = await fetch('/api/status?_t=' + Date.now(), { 
      cache: 'no-store',
      headers: authHeaders()
    });
    const data = await res.json();
    if (data.auth_required && !authToken) {
      showPinAuthModal();
    }
    
    isLocalClient = data.is_local_client;
    pcHostName = data.pc_name || 'PC';
    
    const beacon = document.getElementById('beaconDot');
    const deviceLabel = document.getElementById('deviceNameLabel');
    const qrCard = document.getElementById('qrConnectCard');
    const diskText = document.getElementById('diskSpaceText');
    const diskBar = document.getElementById('storageBarFill');

    if (isLocalClient) {
      // Desktop View
      if (data.connected && data.phones && data.phones.length > 0) {
        const p = data.phones[0];
        currentConnectedPhoneIp = p.ip;
        currentConnectedPhoneName = p.device_name;
        beacon.className = 'beacon-dot connected';
        deviceLabel.innerText = 'Connected: ' + p.device_name;
        qrCard.style.display = 'none';

        if (p.storage && p.storage.total_bytes > 0) {
          diskText.innerText = p.device_name + ': ' + p.storage.free_str + ' free | PC: ' + (data.pc_disk ? data.pc_disk.free_str + ' free' : '');
          diskBar.style.width = p.storage.pct_used + '%';
        } else if (data.pc_disk) {
          diskText.innerText = p.device_name + ' | PC: ' + data.pc_disk.free_str + ' free / ' + data.pc_disk.total_str;
          diskBar.style.width = data.pc_disk.pct_used + '%';
        }
      } else {
        currentConnectedPhoneIp = '';
        currentConnectedPhoneName = '';
        beacon.className = 'beacon-dot';
        deviceLabel.innerText = 'Waiting for phone...';
        if (data.pc_disk) {
          diskText.innerText = 'PC: ' + data.pc_disk.free_str + ' free / ' + data.pc_disk.total_str + ' (' + data.pc_disk.pct_free + '% free)';
          diskBar.style.width = data.pc_disk.pct_used + '%';
        }
        if (data.qr_svg) {
          document.getElementById('qrSvgContainer').innerHTML = data.qr_svg;
          document.getElementById('qrUrlBadge').innerText = data.server_url;
          qrCard.style.display = 'flex';
        }
      }
    } else {
      // Phone View
      beacon.className = 'beacon-dot connected';
      const myDisplayName = cachedNickname || cachedCustomModel || (hw.model !== 'Linux Desktop' && hw.model !== 'Windows PC' && hw.model !== 'Apple Mac' ? hw.model : '') || 'Phone';
      deviceLabel.innerText = `${myDisplayName} ⇄ ${pcHostName}`;
      qrCard.style.display = 'none';

      if (phoneStorage && phoneStorage.total_bytes > 0) {
        diskText.innerText = 'Phone: ' + phoneStorage.free_str + ' free | PC: ' + (data.pc_disk ? data.pc_disk.free_str + ' free' : '');
        diskBar.style.width = phoneStorage.pct_used + '%';
      } else if (data.pc_disk) {
        diskText.innerText = 'PC: ' + data.pc_disk.free_str + ' free / ' + data.pc_disk.total_str;
        diskBar.style.width = data.pc_disk.pct_used + '%';
      }

      if (data.cancel_all_time && overallStartTime > 0 && data.cancel_all_time * 1000 > overallStartTime) {
        if (activeUploads > 0 || uploadQueue.length > 0) {
          cancelAllUploads();
        }
      }
    }

    syncIncomingServerTransfers(data.transfers);

  } catch (err) {}
}

function syncIncomingServerTransfers(transfers) {
  if (!transfers) return;
  if (activeUploads > 0 || uploadQueue.length > 0) return;

  const list = Array.isArray(transfers) ? transfers : (transfers.active || []).concat(transfers.recent || []);
  const active = list.filter(t => t.status === 'transferring');
  const recent = list.filter(t => t.status === 'completed' || t.status === 'cancelled' || t.status === 'error' || t.status === 'done');
  const summaryBanner = document.getElementById('queueSummary');
  const queueContainer = document.getElementById('uploadQueue');

  if (active.length === 0 && recent.length === 0) {
    if (activeServerTransferId) {
      activeServerTransferId = null;
      summaryBanner.style.display = 'none';
      if (queueContainer) queueContainer.innerHTML = '';
      if (activeTabId === 'files') loadFiles();
    }
    return;
  }

  if (active.length > 0) {
    const t = active[0];
    activeServerTransferId = t.id;
    const filename = t.name || t.filename || 'file';
    const sender = t.sender || t.device_name || 'Phone';
    const transferred = t.transferred_bytes || 0;
    const total = t.total_bytes || 0;
    const pct = total > 0 ? Math.min(100, Math.round((transferred / total) * 100)) : (t.progress_pct || 0);
    const speedStr = t.speed_str || (t.speed_mb ? `${t.speed_mb} MB/s` : (t.speed_bps ? formatSpeed(t.speed_bps) : '0 MB/s'));
    const speedBytes = t.speed_bps || ((t.speed_mb || 0) * 1024 * 1024);
    const remBytes = Math.max(0, total - transferred);
    const etaSec = speedBytes > 1024 ? Math.round(remBytes / speedBytes) : (t.eta_seconds || 0);
    
    summaryBanner.style.display = 'flex';
    document.getElementById('summaryCount').innerText = `Receiving from ${sender}: ${filename} (${formatBytes(transferred)} / ${formatBytes(total)})`;
    document.getElementById('summaryProgressFill').style.width = pct + '%';
    document.getElementById('summarySpeed').innerText = speedStr;
    document.getElementById('summaryEta').innerText = etaSec > 0 ? `${formatTimeRemaining(etaSec)} left` : '';
    
    const cancelBtn = document.getElementById('summaryCancelBtn');
    cancelBtn.style.display = 'inline-flex';
    cancelBtn.onclick = () => {
      fetch('/api/cancel_transfer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: t.id })
      });
    };

    if (queueContainer) {
      let card = document.getElementById(`server-${t.id}`);
      if (!card) {
        queueContainer.innerHTML = `
          <div class="queue-card active-transfer" id="server-${t.id}">
            <div class="queue-title-row">
              <div class="queue-title-left">
                <div class="queue-full-name" title="${escapeHtml(filename)}">${escapeHtml(filename)}</div>
              </div>
              <div class="queue-title-right">
                <span class="queue-badge uploading" id="server-${t.id}-badge">Receiving</span>
                <button type="button" class="btn-cancel" onclick="cancelServerTransfer('${t.id}')">Cancel</button>
              </div>
            </div>
            <div class="progress-track">
              <div class="progress-fill" id="server-${t.id}-fill" style="width: ${pct}%;"></div>
            </div>
            <div class="queue-stats-row">
              <span id="server-${t.id}-info">${formatBytes(transferred)} / ${formatBytes(total)} • ${speedStr}${etaSec > 0 ? ' • ' + formatTimeRemaining(etaSec) + ' left' : ''}</span>
              <span id="server-${t.id}-pct">${pct}%</span>
            </div>
          </div>
        `;
      } else {
        const fill = document.getElementById(`server-${t.id}-fill`);
        if (fill) fill.style.width = pct + '%';
        const pctEl = document.getElementById(`server-${t.id}-pct`);
        if (pctEl) pctEl.innerText = pct + '%';
        const infoEl = document.getElementById(`server-${t.id}-info`);
        if (infoEl) {
          const etaStr = etaSec > 0 ? ` • ${formatTimeRemaining(etaSec)} left` : '';
          infoEl.innerText = `${formatBytes(transferred)} / ${formatBytes(total)} • ${speedStr}${etaStr}`;
        }
      }
    }
  } else if (recent.length > 0) {
    const r = recent[0];
    const filename = r.name || r.filename || 'file';
    const sender = r.sender || r.device_name || 'Phone';
    const isCompleted = r.status === 'completed' || r.status === 'done';
    summaryBanner.style.display = 'flex';
    document.getElementById('summaryCount').innerText = isCompleted ? `Received from ${sender}: ${filename}` : `Transfer ${r.status}`;
    document.getElementById('summaryProgressFill').style.width = isCompleted ? '100%' : '0%';
    document.getElementById('summarySpeed').innerText = isCompleted ? 'Completed' : (r.status === 'cancelled' ? 'Cancelled' : 'Failed');
    document.getElementById('summaryEta').innerText = '';
    document.getElementById('summaryCancelBtn').style.display = 'none';

    if (queueContainer) {
      let card = document.getElementById(`server-${r.id}`);
      if (card) {
        const badge = document.getElementById(`server-${r.id}-badge`);
        if (badge) {
          badge.className = isCompleted ? 'queue-badge done' : 'queue-badge cancelled';
          badge.innerText = isCompleted ? 'Done' : (r.status === 'cancelled' ? 'Cancelled' : 'Failed');
        }
        const infoEl = document.getElementById(`server-${r.id}-info`);
        if (infoEl) {
          infoEl.innerText = `${formatBytes(r.total_bytes || 0)} • ${isCompleted ? 'Saved to Desktop/from-phone' : r.status}`;
        }
      }
    }

    if (activeServerTransferId) {
      activeServerTransferId = null;
      if (activeTabId === 'files') loadFiles();
    }
  }
}

function cancelServerTransfer(transferId) {
  fetch('/api/cancel_transfer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: transferId })
  }).catch(() => {});
}

// Background Keepalive (Screen WakeLock & Silent Audio Channel for Mobile Backgrounding)
let wakeLock = null;
let keepAliveAudio = null;

async function activateBackgroundKeepalive() {
  try {
    if ('wakeLock' in navigator && !wakeLock) {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => {
        wakeLock = null;
        if (activeUploads > 0 || uploadQueue.length > 0) {
          setTimeout(activateBackgroundKeepalive, 1000);
        }
      });
    }
  } catch (err) {}

  try {
    if (!keepAliveAudio) {
      // 1-second silent WAV loop to keep mobile CPU and network timers active when backgrounded
      keepAliveAudio = new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA');
      keepAliveAudio.loop = true;
      keepAliveAudio.volume = 0.001;
    }
    keepAliveAudio.play().catch(() => {});
  } catch (err) {}
}

function releaseBackgroundKeepalive() {
  if (wakeLock) {
    wakeLock.release().then(() => { wakeLock = null; }).catch(() => {});
  }
  if (keepAliveAudio) {
    try { keepAliveAudio.pause(); } catch(e) {}
  }
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    if (activeUploads > 0 || uploadQueue.length > 0) {
      activateBackgroundKeepalive();
      processQueue();
    }
  }
});

const uploadQueue = [];
let activeUploads = 0;
const MAX_CONCURRENT = 2; // Multi-stream transfer for Wi-Fi 6 saturation

let totalBytesToUpload = 0;
let totalBytesUploaded = 0;
let totalFilesCount = 0;
let completedFilesCount = 0;
let overallStartTime = 0;
let lastCalculatedSpeed = 0;
let activeTabId = 'upload';

function updateSliderPosition(tabId) {
  const btn = document.getElementById('btn-' + tabId);
  const slider = document.getElementById('sliderIndicator');
  if (btn && slider) {
    slider.style.width = btn.offsetWidth + 'px';
    slider.style.transform = `translateX(${btn.offsetLeft}px)`;
  }
}

function switchTab(tabId) {
  activeTabId = tabId;
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.id === 'btn-' + tabId);
  });
  updateSliderPosition(tabId);

  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.getElementById('tab-' + tabId).classList.add('active');
  if (tabId === 'files') loadFiles();
  if (tabId === 'clip') loadClip();
}

async function manualRefresh() {
  showToast('Refreshing...');
  const rBtn = document.getElementById('refreshBtn');
  if (rBtn) rBtn.style.opacity = '0.5';
  try {
    await sendHeartbeatAndPollStatus();
    if (activeTabId === 'files') await loadFiles();
    if (activeTabId === 'clip') await loadClip(true);
    showToast('Refreshed');
  } catch (e) {
    showToast('Refresh error');
  } finally {
    if (rBtn) rBtn.style.opacity = '1';
  }
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.innerText = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2400);
}

function formatTimeRemaining(seconds) {
  if (seconds <= 0 || !isFinite(seconds)) return '0s';
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.ceil(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const remM = Math.floor(m % 60);
  return `${h}h ${remM}m`;
}

function showIndexingStatus(text) {
  const banner = document.getElementById('indexingBanner');
  const span = document.getElementById('indexingText');
  span.innerText = text;
  banner.style.display = 'flex';
}

function hideIndexingStatus() {
  document.getElementById('indexingBanner').style.display = 'none';
}

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const folderInput = document.getElementById('folderInput');

['dragenter', 'dragover'].forEach(name => {
  dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.add('dragover'); });
});

['dragleave', 'drop'].forEach(name => {
  dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.remove('dragover'); });
});

dropzone.addEventListener('drop', async e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  showIndexingStatus("Analyzing dragged items...");
  const items = e.dataTransfer.items;
  if (items && items.length) {
    const list = await scanDataTransferItems(items);
    hideIndexingStatus();
    enqueueFiles(list);
  } else if (e.dataTransfer.files.length) {
    const list = Array.from(e.dataTransfer.files).map(f => ({ file: f, relPath: f.name }));
    hideIndexingStatus();
    enqueueFiles(list);
  } else {
    hideIndexingStatus();
  }
});

fileInput.addEventListener('change', () => {
  if (fileInput.files.length) {
    showIndexingStatus(`Loading ${fileInput.files.length} selected files...`);
    setTimeout(() => {
      const list = Array.from(fileInput.files).map(f => ({ file: f, relPath: f.name }));
      hideIndexingStatus();
      enqueueFiles(list);
      fileInput.value = '';
    }, 10);
  }
});

folderInput.addEventListener('change', () => {
  if (folderInput.files.length) {
    showIndexingStatus(`Reading folder tree (${folderInput.files.length} items)...`);
    setTimeout(() => {
      const list = Array.from(folderInput.files).map(f => ({
        file: f,
        relPath: f.webkitRelativePath || f.name
      }));
      hideIndexingStatus();
      enqueueFiles(list);
      folderInput.value = '';
    }, 10);
  }
});

async function scanDataTransferItems(items) {
  const result = [];
  const queue = [];
  let scannedCount = 0;
  let scannedBytes = 0;

  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    if (item.webkitGetAsEntry) {
      const entry = item.webkitGetAsEntry();
      if (entry) queue.push(entry);
    } else {
      const f = item.getAsFile();
      if (f) {
        result.push({ file: f, relPath: f.name });
        scannedCount++;
        scannedBytes += f.size;
      }
    }
  }

  async function traverse(entry, parentPath = '') {
    if (entry.isFile) {
      const file = await new Promise(res => entry.file(res));
      const relPath = parentPath ? `${parentPath}/${file.name}` : file.name;
      result.push({ file, relPath });
      scannedCount++;
      scannedBytes += file.size;
      if (scannedCount % 10 === 0) {
        showIndexingStatus(`Indexing folder... Found ${scannedCount} files (${formatBytes(scannedBytes)})`);
      }
    } else if (entry.isDirectory) {
      const dirReader = entry.createReader();
      const newPath = parentPath ? `${parentPath}/${entry.name}` : entry.name;
      const entries = await readAllEntries(dirReader);
      for (const child of entries) {
        await traverse(child, newPath);
      }
    }
  }

  function readAllEntries(dirReader) {
    return new Promise(resolve => {
      let entries = [];
      function read() {
        dirReader.readEntries(res => {
          if (res.length) {
            entries = entries.concat(res);
            read();
          } else {
            resolve(entries);
          }
        });
      }
      read();
    });
  }

  for (const entry of queue) {
    await traverse(entry, '');
  }
  return result;
}

function enqueueFiles(itemsList) {
  if (!itemsList.length) return;
  activateBackgroundKeepalive();

  if (uploadQueue.length === 0 && activeUploads === 0) {
    totalBytesToUpload = 0;
    totalBytesUploaded = 0;
    totalFilesCount = 0;
    completedFilesCount = 0;
    overallStartTime = Date.now();
    lastCalculatedSpeed = 0;
  }

  itemsList.forEach(item => {
    const cardId = 'upload-' + Math.random().toString(36).substr(2, 9);
    totalBytesToUpload += item.file.size;
    totalFilesCount++;

    const task = {
      file: item.file,
      relPath: item.relPath,
      cardId: cardId,
      retries: 0,
      cancelled: false,
      xhr: null,
      loadedBytes: 0
    };
    uploadQueue.push(task);
    renderQueueCard(task);
  });

  updateSummaryBanner();
  processQueue();
}

function markTaskCancelledUI(task, reason = 'Cancelled') {
  const card = document.getElementById(task.cardId);
  if (card) {
    card.classList.remove('active-transfer');
    const badge = document.getElementById(`${task.cardId}-badge`);
    if (badge) {
      badge.className = 'queue-badge cancelled';
      badge.innerText = 'Cancelled';
    }
    const cancelBtn = document.getElementById(`${task.cardId}-cancel`);
    if (cancelBtn) cancelBtn.style.display = 'none';
    const fill = document.getElementById(`${task.cardId}-fill`);
    if (fill) fill.style.width = '0%';
    const pct = document.getElementById(`${task.cardId}-pct`);
    if (pct) pct.innerText = '0%';
    const info = document.getElementById(`${task.cardId}-info`);
    if (info) info.innerText = reason;
  }
}

function cancelUploadTask(cardId) {
  fetch('/api/cancel_transfer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: cardId })
  }).catch(() => {});

  const taskIdx = uploadQueue.findIndex(t => t.cardId === cardId);
  if (taskIdx !== -1) {
    const [t] = uploadQueue.splice(taskIdx, 1);
    t.cancelled = true;
    totalBytesToUpload = Math.max(0, totalBytesToUpload - t.file.size);
    totalFilesCount = Math.max(0, totalFilesCount - 1);
    markTaskCancelledUI(t, 'Cancelled from queue');
    updateSummaryBanner();
    showToast('Cancelled ' + t.file.name);
  }
}

function cancelAllUploads() {
  fetch('/api/cancel_all', { method: 'POST' }).catch(() => {});

  while (uploadQueue.length > 0) {
    const t = uploadQueue.shift();
    t.cancelled = true;
    if (t.xhr) {
      try { t.xhr.abort(); } catch (e) {}
    }
    markTaskCancelledUI(t, 'Cancelled');
  }

  showToast('All uploads cancelled');
  const banner = document.getElementById('queueSummary');
  document.getElementById('summaryCount').innerText = 'Uploads cancelled';
  document.getElementById('summaryProgressFill').style.width = '0%';
  document.getElementById('summarySpeed').innerText = 'Cancelled';
  document.getElementById('summaryEta').innerText = '';
  document.getElementById('summaryCancelBtn').style.display = 'none';

  setTimeout(() => {
    if (activeUploads === 0 && uploadQueue.length === 0) {
      banner.style.display = 'none';
      releaseBackgroundKeepalive();
    }
  }, 2500);
}

function renderQueueCard(task) {
  const container = document.getElementById('uploadQueue');
  const card = document.createElement('div');
  card.className = 'queue-card';
  card.id = task.cardId;
  card.innerHTML = `
    <div class="queue-title-row">
      <div class="queue-title-left">
        <div class="queue-full-name">${escapeHtml(task.relPath)}</div>
      </div>
      <div class="queue-title-right">
        <span class="queue-badge" id="${task.cardId}-badge">Queued</span>
        <button type="button" class="btn-cancel" id="${task.cardId}-cancel" onclick="cancelUploadTask('${task.cardId}')">Cancel</button>
      </div>
    </div>
    <div class="progress-track">
      <div class="progress-fill" id="${task.cardId}-fill"></div>
    </div>
    <div class="queue-stats-row">
      <span id="${task.cardId}-info">0 B / ${formatBytes(task.file.size)}</span>
      <span id="${task.cardId}-pct">0%</span>
    </div>
  `;
  container.appendChild(card);
}

function updateSummaryBanner() {
  const banner = document.getElementById('queueSummary');
  if (totalFilesCount === 0) {
    banner.style.display = 'none';
    return;
  }
  banner.style.display = 'flex';
  const currentTotal = totalBytesUploaded;
  const pct = totalBytesToUpload > 0 ? Math.min(100, Math.round((currentTotal / totalBytesToUpload) * 100)) : 0;
  document.getElementById('summaryCount').innerText = `Uploading ${completedFilesCount}/${totalFilesCount} files (${formatBytes(currentTotal)} / ${formatBytes(totalBytesToUpload)})`;
  document.getElementById('summaryProgressFill').style.width = pct + '%';
  
  if (completedFilesCount === totalFilesCount && activeUploads === 0) {
    document.getElementById('summarySpeed').innerText = 'Complete';
    document.getElementById('summaryEta').innerText = '';
    document.getElementById('summaryCancelBtn').style.display = 'none';
    setTimeout(() => {
      if (activeUploads === 0 && uploadQueue.length === 0) {
        banner.style.display = 'none';
        releaseBackgroundKeepalive();
        if (activeTabId === 'files') loadFiles();
      }
    }, 3000);
  }
}

function processQueue() {
  while (activeUploads < MAX_CONCURRENT && uploadQueue.length > 0) {
    const task = uploadQueue.shift();
    if (!task.cancelled) {
      startUploadTask(task);
    }
  }
}

async function startUploadTask(task) {
  if (task.cancelled) return;
  activeUploads++;
  activateBackgroundKeepalive();

  const card = document.getElementById(task.cardId);
  if (card) {
    card.classList.add('active-transfer');
  }

  const badge = document.getElementById(`${task.cardId}-badge`);
  if (badge) {
    badge.className = 'queue-badge uploading';
    badge.innerText = 'Active';
  }

  // Query server to check if partial file exists for seamless resumption
  let startOffset = 0;
  try {
    const res = await fetch(`/api/upload_status?id=${encodeURIComponent(task.cardId)}&name=${encodeURIComponent(task.file.name)}&relPath=${encodeURIComponent(task.relPath)}&targetDir=${encodeURIComponent(currentPath)}&_t=${Date.now()}`, {
      headers: authHeaders()
    });
    if (res.status === 401) {
      activeUploads--;
      showPinAuthModal();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      if (data.offset && data.offset < task.file.size) {
        startOffset = data.offset;
      }
    }
  } catch (e) {}

  uploadTaskChunk(task, startOffset);
}

function uploadTaskChunk(task, offset) {
  if (task.cancelled) {
    activeUploads--;
    processQueue();
    return;
  }

  const xhr = new XMLHttpRequest();
  task.xhr = xhr;
  task.currentOffset = offset;
  let lastLoaded = 0;
  let lastTime = Date.now();

  xhr.upload.onprogress = (e) => {
    if (task.cancelled) return;
    const currentLoaded = offset + (e.lengthComputable ? e.loaded : 0);
    const totalSize = task.file.size;
    const pct = Math.min(100, Math.round((currentLoaded / totalSize) * 100));
    const now = Date.now();
    const timeDiff = (now - lastTime) / 1000;
    
    let speedStr = '';
    let fileEtaStr = '';
    if (timeDiff > 0.12) {
      const speed = (e.loaded - lastLoaded) / timeDiff;
      if (speed > 1024) {
        speedStr = ` • ${formatSpeed(speed)}`;
        const remainingFileBytes = Math.max(0, totalSize - currentLoaded);
        const fileEta = remainingFileBytes / speed;
        fileEtaStr = ` • ${formatTimeRemaining(fileEta)} left`;
      }
      lastLoaded = e.loaded;
      lastTime = now;

      // Update overall speed & total queue ETA
      const overallElapsed = (now - overallStartTime) / 1000;
      if (overallElapsed > 0.3) {
        const cumulativeTransferred = totalBytesUploaded + currentLoaded;
        lastCalculatedSpeed = cumulativeTransferred / overallElapsed;
        document.getElementById('summarySpeed').innerText = formatSpeed(lastCalculatedSpeed);
        
        const overallRemainingBytes = Math.max(0, totalBytesToUpload - cumulativeTransferred);
        if (lastCalculatedSpeed > 1024 && overallRemainingBytes > 0) {
          const overallEta = overallRemainingBytes / lastCalculatedSpeed;
          document.getElementById('summaryEta').innerText = `${formatTimeRemaining(overallEta)} left`;
        }
      }
    }

    const fill = document.getElementById(`${task.cardId}-fill`);
    if (fill) fill.style.width = pct + '%';
    const pctEl = document.getElementById(`${task.cardId}-pct`);
    if (pctEl) pctEl.innerText = pct + '%';
    const info = document.getElementById(`${task.cardId}-info`);
    if (info) info.innerText = `${formatBytes(currentLoaded)} / ${formatBytes(totalSize)}${speedStr}${fileEtaStr}`;

    const summaryCount = document.getElementById('summaryCount');
    if (summaryCount) {
      summaryCount.innerText = `Uploading ${completedFilesCount}/${totalFilesCount} files (${formatBytes(totalBytesUploaded + currentLoaded)} / ${formatBytes(totalBytesToUpload)})`;
    }
    const sumPct = totalBytesToUpload > 0 ? Math.min(100, Math.round(((totalBytesUploaded + currentLoaded) / totalBytesToUpload) * 100)) : 0;
    const sumFill = document.getElementById('summaryProgressFill');
    if (sumFill) sumFill.style.width = sumPct + '%';
  };

  xhr.onload = () => {
    activeUploads--;
    if (task.cancelled) {
      processQueue();
      return;
    }

    if (xhr.status === 401) {
      showPinAuthModal();
      return;
    }
    
    let resp = null;
    try { resp = JSON.parse(xhr.responseText); } catch(e) {}

    if (xhr.status >= 200 && xhr.status < 300 && resp && resp.status === 'ok') {
      totalBytesUploaded += task.file.size;
      completedFilesCount++;
      
      const card = document.getElementById(task.cardId);
      if (card) card.classList.remove('active-transfer');
      const fill = document.getElementById(`${task.cardId}-fill`);
      if (fill) fill.style.width = '100%';
      const pctEl = document.getElementById(`${task.cardId}-pct`);
      if (pctEl) pctEl.innerText = '100%';
      const info = document.getElementById(`${task.cardId}-info`);
      if (info) info.innerText = `${formatBytes(task.file.size)} • Done`;
      
      const cancelBtn = document.getElementById(`${task.cardId}-cancel`);
      if (cancelBtn) cancelBtn.style.display = 'none';

      const badge = document.getElementById(`${task.cardId}-badge`);
      if (badge) {
        badge.className = 'queue-badge done';
        badge.innerText = 'Done';
      }
      updateSummaryBanner();
      processQueue();
    } else if (resp && resp.status === 'cancelled') {
      task.cancelled = true;
      markTaskCancelledUI(task, 'Cancelled by PC');
      updateSummaryBanner();
      processQueue();
    } else {
      handleUploadAutoResume(task);
    }
  };

  xhr.onerror = () => {
    activeUploads--;
    if (!task.cancelled) handleUploadAutoResume(task);
  };

  xhr.onabort = () => {
    activeUploads--;
    task.cancelled = true;
    markTaskCancelledUI(task, 'Cancelled');
    updateSummaryBanner();
    processQueue();
  };

  xhr.ontimeout = () => {
    activeUploads--;
    if (!task.cancelled) handleUploadAutoResume(task);
  };

  const sliceBlob = offset > 0 ? task.file.slice(offset) : task.file;
  let uploadUrl = `/api/upload?id=${encodeURIComponent(task.cardId)}&name=${encodeURIComponent(task.file.name)}&relPath=${encodeURIComponent(task.relPath)}&targetDir=${encodeURIComponent(currentPath)}&offset=${offset}&totalSize=${task.file.size}`;
  if (authToken) {
    uploadUrl += `&token=${encodeURIComponent(authToken)}`;
  }
  xhr.open('POST', uploadUrl, true);
  if (authToken) {
    xhr.setRequestHeader('Authorization', 'Bearer ' + authToken);
  }
  xhr.send(sliceBlob);
}

function handleUploadAutoResume(task) {
  if (task.cancelled) return;
  task.retries = (task.retries || 0) + 1;
  
  if (task.retries <= 20) {
    const badge = document.getElementById(`${task.cardId}-badge`);
    if (badge) {
      badge.className = 'queue-badge uploading';
      badge.innerText = `Reconnecting (${task.retries})...`;
    }
    const info = document.getElementById(`${task.cardId}-info`);
    if (info) {
      info.innerText = `Network paused. Reconnecting & resuming...`;
    }

    setTimeout(async () => {
      if (task.cancelled) return;
      let offset = 0;
      try {
        const res = await fetch(`/api/upload_status?id=${encodeURIComponent(task.cardId)}&name=${encodeURIComponent(task.file.name)}&relPath=${encodeURIComponent(task.relPath)}&targetDir=${encodeURIComponent(currentPath)}&_t=${Date.now()}`, {
          headers: authHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          offset = data.offset || 0;
        }
      } catch(e) {}

      activeUploads++;
      uploadTaskChunk(task, offset);
    }, 700);
  } else {
    handleUploadError(task, 'Connection lost after multiple retries');
  }
}

function handleUploadError(task, errorMsg) {
  if (task.cancelled) return;
  if (errorMsg && errorMsg.toLowerCase().includes('cancel')) {
    task.cancelled = true;
    markTaskCancelledUI(task, 'Cancelled');
    updateSummaryBanner();
    processQueue();
    return;
  }
  const card = document.getElementById(task.cardId);
  if (card) card.classList.remove('active-transfer');
  const badge = document.getElementById(`${task.cardId}-badge`);
  if (badge) {
    badge.className = 'queue-badge error';
    badge.innerText = 'Failed';
  }
  const cancelBtn = document.getElementById(`${task.cardId}-cancel`);
  if (cancelBtn) cancelBtn.style.display = 'none';
  document.getElementById(`${task.cardId}-info`).innerText = `Error: ${errorMsg}`;
  updateSummaryBanner();
  processQueue();
}

// ==============================================================================
// Files Explorer (Direct Uncached Fetching & Management)
// ==============================================================================

async function loadFiles(path = currentPath) {
  currentPath = path;
  renderBreadcrumbs();
  const container = document.getElementById('fileList');
  container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:24px;">Loading files...</p>';
  try {
    const res = await fetch(`/api/files?dir=${encodeURIComponent(currentPath)}&_t=${Date.now()}`, {
      cache: 'no-store',
      headers: authHeaders()
    });
    if (res.status === 401) {
      showPinAuthModal();
      return;
    }
    allItems = await res.json();
    renderFiles(allItems);
  } catch (err) {
    container.innerHTML = '<p style="color:var(--danger);text-align:center;padding:24px;">Failed to load files</p>';
  }
}

function renderBreadcrumbs() {
  const container = document.getElementById('breadcrumbs');
  const parts = currentPath ? currentPath.split('/') : [];
  let html = `<span class="crumb" onclick="loadFiles('')">from-phone</span>`;
  
  let accumulated = '';
  parts.forEach((p, idx) => {
    accumulated = accumulated ? `${accumulated}/${p}` : p;
    html += ` <span class="crumb-separator">/</span> `;
    if (idx === parts.length - 1) {
      html += `<span class="crumb-current">${escapeHtml(p)}</span>`;
    } else {
      const target = accumulated;
      html += `<span class="crumb" onclick="loadFiles('${escapeHtml(target)}')">${escapeHtml(p)}</span>`;
    }
  });
  container.innerHTML = html;
}

function filterFiles() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const filtered = allItems.filter(f => f.name.toLowerCase().includes(q));
  renderFiles(filtered);
}

function renderFiles(items) {
  const container = document.getElementById('fileList');
  if (!items || items.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:34px;">No files here yet</p>';
    return;
  }
  
  items.sort((a, b) => {
    if (a.is_dir === b.is_dir) return a.name.localeCompare(b.name);
    return a.is_dir ? -1 : 1;
  });

  container.innerHTML = items.map(item => {
    const tokenQuery = authToken ? `&token=${encodeURIComponent(authToken)}` : '';
    if (item.is_dir) {
      return `
        <div class="file-item is-folder">
          <div class="file-info" onclick="loadFiles('${escapeHtml(item.path)}')">
            <svg class="file-icon" viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
            <div class="file-details">
              <div class="file-title">${escapeHtml(item.name)}/</div>
              <div class="file-sub">${item.item_count} items &bull; ${item.mtime}</div>
            </div>
          </div>
          <div class="file-actions">
            <button class="action-btn" onclick="loadFiles('${escapeHtml(item.path)}')">Open</button>
            <a class="action-btn" href="/api/download?path=${encodeURIComponent(item.path)}${tokenQuery}" download="${escapeHtml(item.name)}.zip">ZIP</a>
            <button class="action-btn btn-del" onclick="deleteItem('${encodeURIComponent(item.path)}', true)">Delete</button>
          </div>
        </div>
      `;
    } else {
      return `
        <div class="file-item">
          <div class="file-info">
            <svg class="file-icon" viewBox="0 0 24 24">${getFileIcon(item.name)}</svg>
            <div class="file-details">
              <div class="file-title">${escapeHtml(item.name)}</div>
              <div class="file-sub">${formatBytes(item.size)} &bull; ${item.mtime}</div>
            </div>
          </div>
          <div class="file-actions">
            ${canPreview(item.name) ? `<button class="action-btn" onclick="previewFile('${encodeURIComponent(item.path)}')">Preview</button>` : ''}
            <a class="action-btn" href="/api/download?path=${encodeURIComponent(item.path)}${tokenQuery}" download="${escapeHtml(item.name)}">Download</a>
            <button class="action-btn btn-del" onclick="deleteItem('${encodeURIComponent(item.path)}', false)">Delete</button>
          </div>
        </div>
      `;
    }
  }).join('');
}

function getFileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  if (['flac','mp3','wav','ogg','m4a','aac'].includes(ext)) {
    return '<path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>';
  } else if (['jpg','jpeg','png','gif','webp','svg','heic'].includes(ext)) {
    return '<path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>';
  } else if (['mp4','webm','mov','mkv','avi'].includes(ext)) {
    return '<path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z"/>';
  } else if (['zip','tar','gz','rar','7z'].includes(ext)) {
    return '<path d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-6 10h-2v-2h2v2zm0-4h-2v-2h2v2zm-4-4h2v2h-2V8z"/>';
  }
  return '<path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>';
}

function canPreview(name) {
  const ext = name.split('.').pop().toLowerCase();
  return ['flac','mp3','wav','ogg','m4a','jpg','jpeg','png','gif','webp','svg','mp4','webm','mov','txt','log','json','py','sh','md','pdf'].includes(ext);
}

function previewFile(encodedPath) {
  const name = decodeURIComponent(encodedPath).split('/').pop();
  const ext = name.split('.').pop().toLowerCase();
  const tokenQuery = authToken ? `&token=${encodeURIComponent(authToken)}` : '';
  const url = `/api/download?path=${encodedPath}${tokenQuery}`;
  const body = document.getElementById('modalBody');

  if (['jpg','jpeg','png','gif','webp','svg'].includes(ext)) {
    body.innerHTML = `<img src="${url}" class="modal-media">`;
  } else if (['mp4','webm','mov'].includes(ext)) {
    body.innerHTML = `<video controls autoplay class="modal-media" src="${url}"></video>`;
  } else if (['flac','mp3','wav','ogg','m4a'].includes(ext)) {
    body.innerHTML = `<h4 style="margin-bottom:10px;">${escapeHtml(name)}</h4><audio controls autoplay style="width:100%;margin:10px 0;" src="${url}"></audio>`;
  } else if (['pdf'].includes(ext)) {
    body.innerHTML = `<iframe src="${url}" style="width:80vw;height:70vh;border:none;"></iframe>`;
  } else {
    body.innerHTML = `<p style="padding:10px;color:var(--text-secondary);">Loading preview...</p>`;
    fetch(url, { headers: authHeaders() }).then(r => r.text()).then(txt => {
      body.innerHTML = `<div class="modal-text">${escapeHtml(txt.slice(0, 50000))}</div>`;
    });
  }
  document.getElementById('modal').classList.add('active');
}

function closeModal(e) {
  if (pinModalShown) return;
  if (e && e.target !== e.currentTarget && e.target !== document.querySelector('.modal-close')) return;
  document.getElementById('modal').classList.remove('active');
  const video = document.querySelector('#modalBody video');
  if (video) video.pause();
  const audio = document.querySelector('#modalBody audio');
  if (audio) audio.pause();
}

async function promptNewFolder() {
  const name = prompt('Folder name:');
  if (name && name.trim()) {
    await fetch(`/api/mkdir?dir=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(name.trim())}`, { 
      method: 'POST',
      headers: authHeaders()
    });
    showToast('Folder created');
    loadFiles();
  }
}

async function deleteItem(encodedPath, isDir) {
  const name = decodeURIComponent(encodedPath).split('/').pop();
  if (confirm(`Delete ${isDir ? 'folder' : 'file'} "${name}"?`)) {
    await fetch(`/api/delete?path=${encodedPath}`, { 
      method: 'POST',
      headers: authHeaders()
    });
    showToast('Deleted');
    loadFiles();
  }
}

async function confirmClearSharedFolder() {
  if (confirm('Delete all files and folders in this directory?')) {
    for (const item of allItems) {
      try {
        await fetch(`/api/delete?path=${encodeURIComponent(item.path)}`, { 
          method: 'POST',
          headers: authHeaders()
        });
      } catch (e) {}
    }
    showToast('Cleared directory');
    loadFiles();
  }
}

// ==============================================================================
// Multimodal Clipboard System (Full Dismiss & Clean-Slate Support)
// ==============================================================================

async function loadClip(showFeedback = false) {
  try {
    const res = await fetch('/api/clipboard?_t=' + Date.now(), { 
      cache: 'no-store',
      headers: authHeaders()
    });
    if (res.status === 401) {
      showPinAuthModal();
      return;
    }
    const data = await res.json();
    
    const pcImgCard = document.getElementById('pcImageCard');
    const pcTextCard = document.getElementById('pcTextCard');

    if (data.type === 'image') {
      currentPcImageData = data.data;
      document.getElementById('pcImgElement').src = data.data;
      document.getElementById('pcImgDownloadBtn').href = data.data;
      document.getElementById('pcImgInfo').innerText = `Image from PC (${data.mime} &bull; ${formatBytes(data.size)})`;
      pcImgCard.style.display = 'flex';
      pcTextCard.style.display = 'none';
      if (showFeedback) showToast('Loaded copied image from PC');
    } else {
      currentPcImageData = null;
      pcImgCard.style.display = 'none';
      pcTextCard.style.display = 'block';
      document.getElementById('clipText').value = data.text || '';
      if (showFeedback) showToast('Loaded PC clipboard text');
    }
  } catch (err) {
    if (showFeedback) showToast('Failed to fetch PC clipboard');
  }
}

function dismissPcImage() {
  currentPcImageData = null;
  document.getElementById('pcImageCard').style.display = 'none';
  document.getElementById('pcTextCard').style.display = 'block';
  showToast('Image preview dismissed');
}

function clearClipText() {
  document.getElementById('clipText').value = '';
  showToast('Text cleared');
}

function clearClipboardView() {
  dismissPcImage();
  clearClipText();
  cancelSelectedClipImage();
  showToast('Clipboard reset — ready for new text or image');
}

function cancelSelectedClipImage() {
  pendingClipImageFile = null;
  pendingClipImageBase64 = null;
  document.getElementById('clipImageInput').value = '';
  document.getElementById('selectedImagePreview').style.display = 'none';
  document.getElementById('selectImageActions').style.display = 'flex';
  const cancelBtn = document.getElementById('clipImgCancelBtn');
  if (cancelBtn) cancelBtn.style.display = 'none';
}

function handleClipImageSelect(files) {
  if (!files || !files.length) return;
  const file = files[0];
  pendingClipImageFile = file;
  const reader = new FileReader();
  reader.onload = () => {
    pendingClipImageBase64 = reader.result;
    document.getElementById('selectedImgElement').src = pendingClipImageBase64;
    document.getElementById('selectedImgInfo').innerText = `${file.name} (${formatBytes(file.size)})`;
    document.getElementById('selectedImagePreview').style.display = 'flex';
    document.getElementById('selectImageActions').style.display = 'none';
    const cancelBtn = document.getElementById('clipImgCancelBtn');
    if (cancelBtn) cancelBtn.style.display = 'inline-flex';
  };
  reader.readAsDataURL(file);
}

async function sendSelectedImageToPc() {
  if (!pendingClipImageBase64 || !pendingClipImageFile) return;
  try {
    const res = await fetch('/api/clipboard', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        type: 'image',
        mime: pendingClipImageFile.type || 'image/png',
        data: pendingClipImageBase64
      })
    });
    if (res.ok) {
      showToast('Image copied to PC (Press Ctrl+V on PC)');
      cancelSelectedClipImage();
    } else {
      showToast('Failed to copy image to PC');
    }
  } catch (err) {
    alert('Error sending image');
  }
}

async function saveClipText() {
  const text = document.getElementById('clipText').value;
  try {
    const res = await fetch('/api/clipboard', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ type: 'text', text: text })
    });
    if (res.ok) {
      showToast('Text copied to PC (Press Ctrl+V on PC)');
    } else {
      showToast('Failed to send text to PC');
    }
  } catch (err) {
    alert('Failed to send');
  }
}

document.addEventListener('paste', async (e) => {
  if (activeTabId !== 'clip') return;
  const items = (e.clipboardData || e.originalEvent.clipboardData).items;
  for (let index in items) {
    const item = items[index];
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const blob = item.getAsFile();
      handleClipImageSelect([blob]);
      break;
    }
  }
});

async function copyImageToPhone() {
  if (!currentPcImageData) return;
  try {
    const res = await fetch(currentPcImageData);
    const blob = await res.blob();
    if (navigator.clipboard && navigator.clipboard.write) {
      await navigator.clipboard.write([
        new ClipboardItem({ [blob.type]: blob })
      ]);
      showToast('Image copied to phone clipboard');
    } else {
      showToast('Clipboard copy not supported, use Save Image');
    }
  } catch (err) {
    document.getElementById('pcImgDownloadBtn').click();
  }
}

async function saveClipImageToSharedFolder() {
  if (!currentPcImageData) return;
  try {
    const res = await fetch(currentPcImageData);
    const blob = await res.blob();
    const filename = `clip_image_${Date.now()}.png`;
    
    const uploadUrl = `/api/upload?name=${encodeURIComponent(filename)}&relPath=${encodeURIComponent(filename)}`;
    const uploadRes = await fetch(uploadUrl, { method: 'POST', body: blob });
    if (uploadRes.ok) {
      showToast(`Saved to Desktop/from-phone/${filename}`);
    } else {
      showToast('Could not save image to folder');
    }
  } catch (err) {
    alert('Failed to save to folder');
  }
}

function copyClip() {
  const t = document.getElementById('clipText');
  t.select();
  navigator.clipboard.writeText(t.value).then(() => showToast('Copied to phone clipboard'));
}

function escapeHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function toggleTheme() {
  const html = document.documentElement;
  const cur = html.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}

const savedTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

window.addEventListener('DOMContentLoaded', () => {
  updateSliderPosition('upload');
  sendHeartbeatAndPollStatus();
  setInterval(sendHeartbeatAndPollStatus, 2000);
});