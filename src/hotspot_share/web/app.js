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
let onboardingTriggered = false;

let pendingClipImageFile = null;
let pendingClipImageBase64 = null;

let authToken = localStorage.getItem('hotspot_share_token') || '';
const _urlParams = new URLSearchParams(window.location.search);
if (_urlParams.get('token')) {
  authToken = _urlParams.get('token');
  localStorage.setItem('hotspot_share_token', authToken);
}
if (_urlParams.get('onboard') || _urlParams.get('tour') || _urlParams.get('reset')) {
  localStorage.removeItem('hotspot_onboarded');
}

function authHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (authToken) {
    headers['Authorization'] = 'Bearer ' + authToken;
    headers['X-Auth-Token'] = authToken;
  }
  return headers;
}

function showPinAuthScreen(errorMsg = '') {
  document.documentElement.setAttribute('data-auth-locked', 'true');
  document.body.classList.add('pin-auth-locked');
  const overlay = document.getElementById('pinAuthOverlay');
  const errEl = document.getElementById('pinAuthError');
  const inp = document.getElementById('pinAuthInput');
  if (errEl) {
    if (errorMsg) {
      errEl.innerText = errorMsg;
      errEl.style.display = 'block';
    } else {
      errEl.innerText = '';
      errEl.style.display = 'none';
    }
  }
  if (overlay) {
    overlay.style.display = 'flex';
  }
  if (inp) {
    setTimeout(() => {
      try { inp.focus(); } catch (e) {}
    }, 120);
  }
}

function hidePinAuthScreen() {
  document.documentElement.removeAttribute('data-auth-locked');
  document.body.classList.remove('pin-auth-locked');
  const overlay = document.getElementById('pinAuthOverlay');
  if (overlay) {
    overlay.style.display = 'none';
  }
  const errEl = document.getElementById('pinAuthError');
  if (errEl) {
    errEl.style.display = 'none';
    errEl.innerText = '';
  }
}

function showPinAuthModal(msg = '') {
  showPinAuthScreen(msg);
}

function formatPinAuthInput(input) {
  let val = input.value.replace(/\D/g, '');
  if (val.length > 8) val = val.slice(0, 8);
  if (val.length > 4) {
    input.value = val.slice(0, 4) + ' ' + val.slice(4);
  } else {
    input.value = val;
  }
}

async function submitPinAuth() {
  const inp = document.getElementById('pinAuthInput');
  const rawPin = inp ? inp.value.replace(/\D/g, '').trim() : '';
  if (!rawPin || rawPin.length !== 8) {
    showPinAuthScreen('Please enter the full 8-digit PIN code.');
    return;
  }

  const submitBtn = document.getElementById('btnSubmitPinAuth');
  const btnText = document.getElementById('btnSubmitPinAuthText');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.style.opacity = '0.7';
    if (btnText) btnText.innerText = 'Verifying...';
  }

  try {
    const res = await fetch('/api/auth/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: rawPin })
    });

    let data = null;
    try {
      const text = await res.text();
      data = JSON.parse(text);
    } catch (parseErr) {
      data = {
        status: 'error',
        message: (res.status === 403)
          ? 'Incorrect PIN code. Please check the code on your PC.'
          : (res.status === 429 ? 'Too many failed attempts. Please wait 30 seconds.' : 'Unable to connect to PC.')
      };
    }

    if (res.ok && data && data.status === 'ok' && data.token) {
      authToken = data.token;
      localStorage.setItem('hotspot_share_token', authToken);
      hidePinAuthScreen();
      showToast('Connected & paired!');
      await sendHeartbeatAndPollStatus();
      if (activeTabId === 'clip') {
        loadClip();
      }
      if (activeTabId === 'files') {
        loadFiles();
      }
    } else {
      const msg = (data && data.message)
        ? data.message
        : (res.status === 429
            ? 'Too many failed attempts. Please wait 30 seconds.'
            : 'Incorrect PIN code. Please check the code on your PC.');
      showPinAuthScreen(msg);
      if (inp) {
        inp.select();
      }
    }
  } catch (e) {
    showPinAuthScreen('Unable to reach PC. Check your Wi-Fi connection.');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.style.opacity = '1';
      if (btnText) btnText.innerText = 'Authorize & Connect';
    }
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

let currentServerAuthEnabled = false;
let currentServerPin = "";

async function renderSecuritySection() {
  try {
    const res = await fetch('/api/status?_t=' + Date.now(), { headers: authHeaders() });
    const data = await res.json();
    currentServerAuthEnabled = !!data.auth_enabled;
    currentServerPin = data.pin_code || "";
    isLocalClient = !!data.is_local_client;
    pcHostName = data.pc_name || 'PC';
  } catch (e) {}

  const isEnabled = currentServerAuthEnabled;
  const isPhone = !isLocalClient;
  const formatted = (currentServerPin.length === 8)
    ? `${currentServerPin.slice(0, 4)} ${currentServerPin.slice(4)}`
    : (currentServerPin || '--------');

  // Update Status Badge on Tab
  const statusBadge = document.getElementById('secStatusBadge');
  if (statusBadge) {
    if (isEnabled) {
      statusBadge.className = 'sec-status-badge is-active';
      statusBadge.innerText = 'Protected';
    } else {
      statusBadge.className = 'sec-status-badge is-disabled';
      statusBadge.innerText = 'Disabled';
    }
  }

  const toggleTitle = document.getElementById('secToggleStateTitle');
  const toggleDesc = document.getElementById('secToggleStateDesc');
  const btnContainer = document.getElementById('secToggleBtnContainer');
  const activePinBox = document.getElementById('secActivePinBox');
  const oneSentence = document.getElementById('secOneSentenceDesc');

  if (isPhone) {
    if (toggleTitle) {
      toggleTitle.innerText = isEnabled
        ? `Protected by ${pcHostName}`
        : `Connected to ${pcHostName}`;
    }
    if (toggleDesc) {
      toggleDesc.innerText = isEnabled
        ? `Your phone is paired and verified with ${pcHostName}. Direct Wi-Fi transfers and clipboard are secured.`
        : `PIN protection is disabled on ${pcHostName}. Anyone on this Wi-Fi can transfer files.`;
    }
    if (oneSentence) {
      oneSentence.innerText = isEnabled
        ? 'This phone session is authenticated with 8-digit PIN protection.'
        : 'Connected over local Wi-Fi without PIN protection.';
    }
    if (btnContainer) {
      if (isEnabled) {
        btnContainer.innerHTML = `
          <button class="btn-secondary" id="btnUnpairPhone" onclick="unpairPhoneSession()">
            Unpair Device
          </button>
        `;
      } else {
        btnContainer.innerHTML = '';
      }
    }
    if (activePinBox) {
      activePinBox.style.display = 'none';
    }
  } else {
    // Desktop View: Host Controls
    if (toggleTitle) {
      toggleTitle.innerText = isEnabled
        ? 'PIN Protection is On'
        : 'PIN Protection is Off';
    }
    if (toggleDesc) {
      toggleDesc.innerText = isEnabled
        ? 'Connecting devices must enter this 8-digit code to pair.'
        : 'Anyone on your Wi-Fi can transfer files without a code.';
    }
    if (oneSentence) {
      oneSentence.innerText = 'Require an 8-digit code before connecting devices can transfer files or access clipboard.';
    }
    if (btnContainer) {
      if (isEnabled) {
        btnContainer.innerHTML = `
          <button class="btn-secondary" id="btnDisablePinAction" onclick="toggleAuthSecurity(false)">
            Disable PIN Protection
          </button>
        `;
      } else {
        btnContainer.innerHTML = `
          <button class="btn-primary" id="btnEnablePinAction" onclick="toggleAuthSecurity(true)">
            Enable PIN Protection
          </button>
        `;
      }
    }
    if (activePinBox) {
      activePinBox.style.display = isEnabled ? 'block' : 'none';
    }
    const pinDigits = document.getElementById('secPinDigits');
    if (pinDigits) {
      pinDigits.innerText = formatted;
    }
  }
}

async function unpairPhoneSession() {
  if (!confirm('Disconnect and revoke pairing? You will need to enter the 8-digit PIN again to reconnect.')) return;
  try {
    await fetch('/api/auth/disconnect', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({})
    });
  } catch (e) {}
  authToken = '';
  localStorage.removeItem('hotspot_share_token');
  showToast('Disconnected & sharing code revoked');
  showPinAuthScreen();
  await sendHeartbeatAndPollStatus();
}

async function disconnectAllDevices() {
  if (!confirm('Disconnect paired mobile devices and generate a new 8-digit sharing code?')) return;
  try {
    const res = await fetch('/api/auth/disconnect', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.status === 'ok') {
      currentServerPin = data.pin_code || '';
      showToast('Disconnected. New PIN: ' + (data.formatted_pin || currentServerPin));
      await sendHeartbeatAndPollStatus();
      renderSecuritySection();
    } else {
      showToast('Failed to disconnect: ' + (data.message || 'Error'));
    }
  } catch (e) {
    showToast('Failed to disconnect: ' + e.message);
  }
}

function copyActivePin() {
  if (!currentServerPin) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(currentServerPin).then(() => {
      showToast('8-Digit PIN copied to clipboard');
    }).catch(() => {
      showToast('PIN: ' + currentServerPin);
    });
  } else {
    showToast('PIN: ' + currentServerPin);
  }
}

async function setCustomPinFromTab() {
  const inp = document.getElementById('secCustomPinInput');
  const pin = inp ? inp.value.trim() : '';
  if (pin.length !== 8 || !/^\d{8}$/.test(pin)) {
    showToast('PIN must be exactly 8 digits');
    return;
  }
  try {
    const res = await fetch('/api/auth/configure', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ action: 'set_pin', pin })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      currentServerAuthEnabled = true;
      currentServerPin = data.pin_code;
      if (inp) inp.value = '';
      renderSecuritySection();
      sendHeartbeatAndPollStatus();
      showToast('Custom 8-digit PIN set!');
    } else {
      showToast(data.message || 'Failed to set PIN');
    }
  } catch (e) {
    showToast('Failed to set PIN: ' + e.message);
  }
}

async function openSecurityModal() {
  try {
    const res = await fetch('/api/status?_t=' + Date.now(), { headers: authHeaders() });
    const data = await res.json();
    currentServerAuthEnabled = !!data.auth_enabled;
    currentServerPin = data.pin_code || "";
  } catch (e) {}

  const isEnabled = currentServerAuthEnabled;
  const formatted = (currentServerPin.length === 8)
    ? `${currentServerPin.slice(0, 4)} ${currentServerPin.slice(4)}`
    : (currentServerPin || '--------');

  const toggleBtnHtml = isEnabled
    ? `<button class="btn-secondary" style="padding:7px 14px;font-size:12.5px;font-weight:600;" onclick="toggleAuthSecurity(false)">
        Disable PIN Protection
      </button>`
    : `<button class="btn-primary" style="padding:7px 14px;font-size:12.5px;font-weight:600;" onclick="toggleAuthSecurity(true)">
        Enable PIN Protection
      </button>`;

  const html = `
    <div style="text-align:left;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
        <div class="sec-icon-emblem">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="3" ry="3"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            <circle cx="12" cy="16" r="1"/>
            <path d="M12 17v2"/>
          </svg>
        </div>
        <div>
          <h3 style="font-size:17px;font-weight:600;margin:0;color:var(--text-primary);">PIN Protection</h3>
          <span style="font-size:12px;color:var(--text-secondary);">Require an 8-digit code before connecting devices can transfer files.</span>
        </div>
      </div>

      <!-- PIN Settings Card -->
      <div style="background:var(--btn-secondary-bg);border:1px solid var(--border);border-radius:14px;padding:16px;margin:14px 0;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
          <div>
            <div style="display:flex;align-items:center;gap:8px;">
              <b style="font-size:13px;color:var(--text-primary);">Require 8-Digit PIN</b>
              <span class="sec-status-badge ${isEnabled ? 'is-active' : 'is-disabled'}">
                ${isEnabled ? 'Protected' : 'Disabled'}
              </span>
            </div>
            <span style="font-size:12px;color:var(--text-secondary);margin-top:3px;display:block;">
              ${isEnabled ? 'Connecting devices must enter this code to pair.' : 'Anyone on your Wi-Fi can transfer files without a code.'}
            </span>
          </div>
          ${toggleBtnHtml}
        </div>

        <!-- Live PIN Display and Actions -->
        <div id="pinConfigDetails" style="display:${isEnabled ? 'block' : 'none'};margin-top:14px;padding-top:14px;border-top:1px solid var(--border);">
          <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px;">Active Pairing PIN</div>
          <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;background:var(--card-bg);border:1px solid var(--border-focus);padding:10px 14px;border-radius:10px;">
            <span id="activePinDisplay" style="font-family:monospace;font-size:22px;font-weight:700;letter-spacing:3px;color:var(--text-primary);">${escapeHtml(formatted)}</span>
            <button class="btn-secondary" onclick="regeneratePinCode()" style="font-size:11.5px;padding:6px 12px;">Regenerate</button>
          </div>

          <!-- Custom PIN Input -->
          <div style="margin-top:12px;display:flex;gap:8px;align-items:center;">
            <input type="text" id="customPinInput" maxlength="8" placeholder="Custom 8-digit PIN" style="flex:1;background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:8px 12px;font-family:monospace;font-size:13.5px;color:var(--text-primary);letter-spacing:1px;" oninput="this.value=this.value.replace(/[^0-9]/g,'')">
            <button class="btn-secondary" onclick="setCustomPinCode()" style="font-size:11.5px;padding:8px 12px;">Set PIN</button>
          </div>
        </div>
      </div>

      <div style="display:flex;justify-content:space-between;align-items:center;">
        <button class="btn-secondary" onclick="closeModal(); switchTab('security');">Open Security Tab</button>
        <button class="btn-primary" onclick="closeModal()">Done</button>
      </div>
    </div>
  `;
  document.getElementById('modalBody').innerHTML = html;
  document.getElementById('modal').classList.add('active');
}

function openAboutModal() {
  const iconB64 = (typeof window.__ICON_BASE64__ !== 'undefined' && window.__ICON_BASE64__) || '';
  const iconSrc = iconB64 ? `data:image/png;base64,${iconB64}` : '/icon.svg';
  const html = `
    <div class="about-modal-wrapper">
      <div class="about-modal-header">
        <div class="about-logo-box">
          <img src="${iconSrc}" class="about-app-logo" alt="Hotspot Share" onerror="this.src='/icon.svg'">
        </div>
        <div class="about-meta">
          <div class="about-title-row">
            <h2 class="about-app-title">Hotspot Share</h2>
            <span class="about-version-badge">v2.0.10</span>
          </div>
          <div class="about-app-tagline">High-Speed Local Wi-Fi File Sharing &amp; Multimodal Sync</div>
        </div>
      </div>

      <p class="about-description">
        Hotspot Share is a zero-cloud, privacy-first peer-to-peer sharing system designed for Linux desktops and mobile phones.
        Transfer large files and directories at full Wi-Fi link speeds via a direct 8MB chunked transfer engine, and seamlessly sync clipboard text and images between your devices—with zero phone apps, zero cloud telemetry, and zero account logins.
      </p>

      <div class="about-specs-grid">
        <div class="about-spec-item">
          <span class="about-spec-label">Maintainer</span>
          <span class="about-spec-val">penguinatnight</span>
        </div>
        <div class="about-spec-item">
          <span class="about-spec-label">Contact</span>
          <a href="mailto:penguinatnight1@gmail.com" onclick="openExternalUrl('mailto:penguinatnight1@gmail.com'); return false;" class="about-spec-link">penguinatnight1@gmail.com</a>
        </div>
        <div class="about-spec-item">
          <span class="about-spec-label">License</span>
          <span class="about-spec-val">GPL-3.0 (Open Source)</span>
        </div>
        <div class="about-spec-item">
          <span class="about-spec-label">Architecture</span>
          <span class="about-spec-val">Python 3 + WebKitGTK</span>
        </div>
      </div>

      <div class="about-actions-row">
        <button type="button" class="btn-primary about-action-btn" onclick="openExternalUrl('https://github.com/penguinatnight/hotspot-share')">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
          <span>GitHub Source</span>
        </button>
        <button type="button" class="btn-secondary about-action-btn" onclick="closeAboutAndTour()">
          <span>Re-open Tour</span>
        </button>
        <button type="button" class="btn-secondary about-action-btn" onclick="closeModal()">
          <span>Close</span>
        </button>
      </div>
    </div>
  `;
  document.getElementById('modalBody').innerHTML = html;
  document.getElementById('modal').classList.add('active');
}

function openExternalUrl(url) {
  if (!url) return;
  fetch('/api/open-url?url=' + encodeURIComponent(url), { headers: authHeaders() }).catch(() => {});
  try {
    window.open(url, '_blank');
  } catch (e) {}
}

function closeAboutAndTour() {
  closeModal();
  setTimeout(() => openOnboarding(true), 150);
}

async function toggleAuthSecurity(enable) {
  try {
    const res = await fetch('/api/auth/configure', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ action: enable ? 'enable' : 'disable' })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      currentServerAuthEnabled = !!data.auth_enabled;
      currentServerPin = data.pin_code || "";
      renderSecuritySection();
      if (document.getElementById('modal').classList.contains('active')) {
        openSecurityModal();
      }
      sendHeartbeatAndPollStatus();
      showToast(enable ? '8-Digit PIN Protection Enabled' : 'PIN Protection Disabled');
    }
  } catch (e) {
    showToast('Failed to update PIN: ' + e.message);
  }
}

async function regeneratePinCode() {
  try {
    const res = await fetch('/api/auth/configure', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ action: 'regenerate' })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      currentServerAuthEnabled = true;
      currentServerPin = data.pin_code;
      renderSecuritySection();
      if (document.getElementById('modal').classList.contains('active')) {
        openSecurityModal();
      }
      sendHeartbeatAndPollStatus();
      showToast('New 8-digit PIN generated!');
    }
  } catch (e) {
    showToast('Failed to regenerate PIN: ' + e.message);
  }
}

async function setCustomPinCode() {
  const inp = document.getElementById('customPinInput');
  const pin = inp ? inp.value.trim() : '';
  if (pin.length !== 8 || !/^\d{8}$/.test(pin)) {
    showToast('PIN must be exactly 8 digits');
    return;
  }
  try {
    const res = await fetch('/api/auth/configure', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ action: 'set_pin', pin })
    });
    const data = await res.json();
    if (data.status === 'ok') {
      currentServerAuthEnabled = true;
      currentServerPin = data.pin_code;
      renderSecuritySection();
      if (document.getElementById('modal').classList.contains('active')) {
        openSecurityModal();
      }
      sendHeartbeatAndPollStatus();
      showToast('Custom 8-digit PIN set!');
    } else {
      showToast(data.message || 'Failed to set PIN');
    }
  } catch (e) {
    showToast('Failed to set PIN: ' + e.message);
  }
}

// PWA INSTALLATION SYSTEM (Mobile-Only)
let deferredPwaPrompt = null;

function isMobileClient() {
  if (isLocalClient) return false;
  const ua = navigator.userAgent || '';
  const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua) ||
                     (navigator.maxTouchPoints > 1 && /Macintosh/i.test(ua));
  const isSmallScreen = window.innerWidth <= 768;
  return isMobileUA || isSmallScreen;
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  if (isMobileClient()) {
    deferredPwaPrompt = e;
    updatePwaInstallVisibility();
  }
});

window.addEventListener('appinstalled', () => {
  deferredPwaPrompt = null;
  updatePwaInstallVisibility();
  showToast('Hotspot Share installed on phone!');
});

function isAppStandalone() {
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}

function updatePwaInstallVisibility() {
  const isMobile = isMobileClient();
  const standalone = isAppStandalone();
  const bannerDismissed = sessionStorage.getItem('pwa_banner_dismissed') === 'true';

  const headerBtn = document.getElementById('pwaHeaderBtn');
  const banner = document.getElementById('pwaMobileBanner');

  if (isMobile && !standalone) {
    if (headerBtn) headerBtn.style.display = 'inline-flex';
    if (banner && !bannerDismissed) banner.style.display = 'flex';
  } else {
    if (headerBtn) headerBtn.style.display = 'none';
    if (banner) banner.style.display = 'none';
  }
}

function dismissPwaBanner() {
  sessionStorage.setItem('pwa_banner_dismissed', 'true');
  const banner = document.getElementById('pwaMobileBanner');
  if (banner) banner.style.display = 'none';
}

async function triggerPwaInstall() {
  if (deferredPwaPrompt) {
    deferredPwaPrompt.prompt();
    const { outcome } = await deferredPwaPrompt.userChoice;
    if (outcome === 'accepted') {
      deferredPwaPrompt = null;
      updatePwaInstallVisibility();
    }
  } else {
    showPwaInstallGuideModal();
  }
}

function showPwaInstallGuideModal() {
  const isIos = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

  const html = `
    <div style="text-align:left;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <div style="width:36px;height:36px;border-radius:10px;background:var(--btn-bg);color:var(--btn-text);display:flex;align-items:center;justify-content:center;">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
        </div>
        <div>
          <h3 style="font-size:16px;font-weight:700;margin:0;color:var(--text-primary);">Install Hotspot Share</h3>
          <span style="font-size:12px;color:var(--text-secondary);">Add to your home screen for full-screen sharing</span>
        </div>
      </div>

      ${isIos ? `
        <div style="background:var(--btn-secondary-bg);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:16px;">
          <b style="font-size:13px;color:var(--text-primary);display:block;margin-bottom:10px;">Safari on iPhone / iPad:</b>
          <ol style="font-size:12px;color:var(--text-secondary);padding-left:18px;margin:0;line-height:1.7;">
            <li>Tap the <b>Share</b> button in Safari's bottom toolbar.</li>
            <li>Scroll down and tap <b>Add to Home Screen</b>.</li>
            <li>Tap <b>Add</b> in the top-right corner.</li>
          </ol>
        </div>
      ` : `
        <div style="background:var(--btn-secondary-bg);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:16px;">
          <b style="font-size:13px;color:var(--text-primary);display:block;margin-bottom:10px;">Chrome on Android:</b>
          <ol style="font-size:12px;color:var(--text-secondary);padding-left:18px;margin:0;line-height:1.7;">
            <li>Tap the <b>Menu (⋮)</b> in the top right corner of Chrome.</li>
            <li>Tap <b>Install app</b> or <b>Add to Home screen</b>.</li>
            <li>Tap <b>Install</b> to confirm.</li>
          </ol>
        </div>
      `}

      <div style="display:flex;justify-content:flex-end;">
        <button class="btn-primary" onclick="closeModal()">Got It</button>
      </div>
    </div>
  `;
  document.getElementById('modalBody').innerHTML = html;
  document.getElementById('modal').classList.add('active');
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
      if (authToken) {
        authToken = '';
        localStorage.removeItem('hotspot_share_token');
      }
      showPinAuthScreen();
    }

    const res = await fetch('/api/status?_t=' + Date.now(), { 
      cache: 'no-store',
      headers: authHeaders()
    });
    const data = await res.json();
    if (data.auth_required) {
      showPinAuthScreen();
    } else if (data.is_authenticated || !data.auth_enabled || data.is_local_client) {
      hidePinAuthScreen();
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
      const btnFiles = document.getElementById('btnSelectFiles');
      const btnFolder = document.getElementById('btnSelectFolder');
      const dzTitle = document.getElementById('dropzoneTitle');
      const dzSub = document.getElementById('dropzoneSubtitle');
      const dropzoneEl = document.getElementById('dropzone');
      const discBtn = document.getElementById('disconnectMiniBtn');

      if (data.connected && data.phones && data.phones.length > 0) {
        const p = data.phones[0];
        currentConnectedPhoneIp = p.ip;
        currentConnectedPhoneName = p.device_name || 'Phone';
        beacon.className = 'beacon-dot connected';
        deviceLabel.innerText = 'Connected: ' + currentConnectedPhoneName;
        if (discBtn) discBtn.style.display = 'inline-flex';
        qrCard.style.display = 'none';

        if (dropzoneEl) dropzoneEl.classList.remove('waiting-for-phone');

        if (btnFiles) {
          btnFiles.disabled = false;
          btnFiles.style.opacity = '1';
          btnFiles.style.cursor = 'pointer';
          btnFiles.innerText = 'Send Files to ' + currentConnectedPhoneName;
        }
        if (btnFolder) {
          btnFolder.disabled = false;
          btnFolder.style.opacity = '1';
          btnFolder.style.cursor = 'pointer';
          btnFolder.innerText = 'Send Folder to ' + currentConnectedPhoneName;
        }
        if (dzTitle) dzTitle.innerText = 'Send files to ' + currentConnectedPhoneName;
        if (dzSub) dzSub.innerText = 'Direct Wi-Fi 6 Beam • Instant transfer to ' + currentConnectedPhoneName;

        if (p.storage && p.storage.total_bytes > 0) {
          diskText.innerText = currentConnectedPhoneName + ': ' + p.storage.free_str + ' free | PC: ' + (data.pc_disk ? data.pc_disk.free_str + ' free' : '');
          diskBar.style.width = p.storage.pct_used + '%';
        } else if (data.pc_disk) {
          diskText.innerText = currentConnectedPhoneName + ' | PC: ' + data.pc_disk.free_str + ' free / ' + data.pc_disk.total_str;
          diskBar.style.width = data.pc_disk.pct_used + '%';
        }
      } else {
        currentConnectedPhoneIp = '';
        currentConnectedPhoneName = '';
        beacon.className = 'beacon-dot';
        deviceLabel.innerText = 'Waiting for phone to connect...';
        if (discBtn) discBtn.style.display = 'none';

        if (dropzoneEl) dropzoneEl.classList.add('waiting-for-phone');

        if (btnFiles) {
          btnFiles.disabled = true;
          btnFiles.style.opacity = '0.55';
          btnFiles.style.cursor = 'not-allowed';
          btnFiles.innerText = 'Connect Phone to Send Files';
        }
        if (btnFolder) {
          btnFolder.disabled = true;
          btnFolder.style.opacity = '0.55';
          btnFolder.style.cursor = 'not-allowed';
          btnFolder.innerText = 'Connect Phone to Send Folder';
        }
        if (dzTitle) dzTitle.innerText = 'No phone connected';
        if (dzSub) dzSub.innerText = 'Scan the QR code above with your phone camera to connect and start sharing';

        if (data.pc_disk) {
          diskText.innerText = 'PC: ' + data.pc_disk.free_str + ' free / ' + data.pc_disk.total_str + ' (' + data.pc_disk.pct_free + '% free)';
          diskBar.style.width = data.pc_disk.pct_used + '%';
        }
        if (data.qr_matrix || data.qr_svg) {
          renderQrDisplay(data.qr_matrix, data.qr_svg);
          document.getElementById('qrUrlBadge').innerText = data.server_url;
          qrCard.style.display = 'flex';
        }
      }

      // Update Desktop Host PIN Badge
      const hostPinBadge = document.getElementById('hostPinBadge');
      const hostPinText = document.getElementById('hostPinCodeText');
      if (hostPinBadge && hostPinText) {
        if (data.auth_enabled && data.pin_code) {
          hostPinBadge.style.display = 'inline-flex';
          hostPinText.innerText = data.formatted_pin || data.pin_code;
        } else {
          hostPinBadge.style.display = 'none';
        }
      }

      const secBtn = document.getElementById('securityBtn');
      if (secBtn) secBtn.style.display = 'inline-flex';
      updatePwaInstallVisibility();

      // Auto-trigger onboarding ONLY on PC desktop
      if (!localStorage.getItem('hotspot_onboarded') && !onboardingTriggered) {
        onboardingTriggered = true;
        openOnboarding(false);
      }
    } else {
      // Phone View - immediately dismiss onboarding
      document.documentElement.classList.remove('init-onboarding');
      beacon.className = 'beacon-dot connected';
      const myDisplayName = (hw.model !== 'Linux Desktop' && hw.model !== 'Windows PC' && hw.model !== 'Apple Mac' ? hw.model : '') || 'Phone';
      deviceLabel.innerText = `${myDisplayName} ⇄ ${pcHostName}`;
      qrCard.style.display = 'none';

      // Always hide tour button and onboarding modal on phones
      const tourBtn = document.getElementById('tourBtn');
      if (tourBtn) tourBtn.style.display = 'none';
      const secBtn = document.getElementById('securityBtn');
      if (secBtn) secBtn.style.display = 'none';
      const hostPinBadge = document.getElementById('hostPinBadge');
      if (hostPinBadge) hostPinBadge.style.display = 'none';
      const overlay = document.getElementById('onboardingOverlay');
      if (overlay) overlay.style.display = 'none';

      updatePwaInstallVisibility();

      const btnFiles = document.getElementById('btnSelectFiles');
      const btnFolder = document.getElementById('btnSelectFolder');
      const dzTitle = document.getElementById('dropzoneTitle');
      const dzSub = document.getElementById('dropzoneSubtitle');
      const dropzoneEl = document.getElementById('dropzone');

      if (dropzoneEl) dropzoneEl.classList.remove('waiting-for-phone');

      if (btnFiles) {
        btnFiles.disabled = false;
        btnFiles.style.opacity = '1';
        btnFiles.style.cursor = 'pointer';
        btnFiles.innerText = 'Send Files to ' + pcHostName;
      }
      if (btnFolder) {
        btnFolder.disabled = false;
        btnFolder.style.opacity = '1';
        btnFolder.style.cursor = 'pointer';
        btnFolder.innerText = 'Send Photos / Folder to ' + pcHostName;
      }
      if (dzTitle) dzTitle.innerText = 'Send files or photos to ' + pcHostName;
      if (dzSub) dzSub.innerText = 'Direct Wi-Fi 6 Transfer • Saves to Desktop/from-phone on ' + pcHostName;

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
    syncIncomingBeams(data.beams);
    updateClipboardTabUI();

    if (filesNeedRefresh && activeTabId === 'files') {
      filesNeedRefresh = false;
      loadFiles();
    }

  } catch (err) {}
}

function renderQrDisplay(matrix, svg) {
  const container = document.getElementById('qrSvgContainer');
  if (!container) return;
  let canvas = document.getElementById('qrCanvas');
  
  if (matrix && Array.isArray(matrix) && matrix.length > 0) {
    if (!canvas) {
      container.innerHTML = '<canvas id="qrCanvas" width="108" height="108"></canvas>';
      canvas = document.getElementById('qrCanvas');
    }
    const ctx = canvas.getContext('2d');
    if (ctx) {
      const size = matrix.length;
      const pad = 2;
      const total = size + pad * 2;
      const canvasSize = 108;
      const moduleSize = canvasSize / total;

      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvasSize, canvasSize);

      ctx.fillStyle = '#000000';
      for (let r = 0; r < size; r++) {
        for (let c = 0; c < size; c++) {
          if (matrix[r][c] === 1) {
            ctx.fillRect(
              Math.floor((c + pad) * moduleSize),
              Math.floor((r + pad) * moduleSize),
              Math.ceil(moduleSize),
              Math.ceil(moduleSize)
            );
          }
        }
      }
      return;
    }
  }
  
  if (svg) {
    container.innerHTML = svg;
  }
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
    const sender = r.sender || r.device_name || 'PC';
    const isCompleted = r.status === 'completed' || r.status === 'done';
    const isLocal = isLocalClient;
    summaryBanner.style.display = 'flex';

    if (isCompleted) {
      if (!isLocal) {
        document.getElementById('summaryCount').innerText = `${sender} sent: ${filename}`;
        document.getElementById('summarySpeed').innerHTML = `<button type="button" class="btn-beam-save" style="padding:4px 10px;font-size:11px;" onclick="triggerDownload('/api/download?path=${encodeURIComponent(r.rel_path || r.name)}', '${escapeHtml(filename)}')">Save to Phone</button>`;
      } else {
        document.getElementById('summaryCount').innerText = `Received from ${sender}: ${filename}`;
        document.getElementById('summarySpeed').innerText = 'Completed';
      }
    } else {
      document.getElementById('summaryCount').innerText = `Transfer ${r.status}`;
      document.getElementById('summarySpeed').innerText = r.status === 'cancelled' ? 'Cancelled' : 'Failed';
    }

    document.getElementById('summaryProgressFill').style.width = isCompleted ? '100%' : '0%';
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
          if (isCompleted && !isLocal) {
            infoEl.innerHTML = `${formatBytes(r.total_bytes || 0)} • Ready on PC • <button type="button" class="btn-beam-save" style="margin-left:8px;padding:3px 8px;font-size:11px;" onclick="triggerDownload('/api/download?path=${encodeURIComponent(r.rel_path || r.name)}', '${escapeHtml(filename)}')">Save to Phone</button>`;
          } else {
            infoEl.innerText = `${formatBytes(r.total_bytes || 0)} • ${isCompleted ? 'Saved to Desktop/from-phone' : r.status}`;
          }
        }
      }
    }

    if (activeServerTransferId) {
      activeServerTransferId = null;
      filesNeedRefresh = true;
      if (activeTabId === 'files') {
        loadFiles();
      } else {
        updateFilesBadge(1);
      }
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

// AIRDROP BEAMS & DIRECT MOBILE DOWNLOAD ENGINE
let dismissedBeams = new Set();
let filesNeedRefresh = false;

function triggerDownload(url, filename, beamId) {
  const tokenQuery = authToken ? `&token=${encodeURIComponent(authToken)}` : '';
  const fullUrl = url + (url.includes('?') ? tokenQuery : `?${tokenQuery.slice(1)}`);
  const a = document.createElement('a');
  a.href = fullUrl;
  a.download = filename || 'download';
  a.target = '_blank';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    try { document.body.removeChild(a); } catch (e) {}
  }, 300);

  showToast(`Downloading ${filename} to Phone...`);

  if (beamId) {
    dismissBeam(beamId);
  }
}

function syncIncomingBeams(beams) {
  const container = document.getElementById('incomingBeamsContainer');
  if (!container) return;

  if (!beams || beams.length === 0) {
    container.style.display = 'none';
    container.innerHTML = '';
    return;
  }

  const activeBeams = beams.filter(b => !dismissedBeams.has(b.id));
  if (activeBeams.length === 0) {
    container.style.display = 'none';
    container.innerHTML = '';
    return;
  }

  container.style.display = 'flex';
  container.innerHTML = activeBeams.map(b => {
    const tokenQuery = authToken ? `&token=${encodeURIComponent(authToken)}` : '';
    const downloadUrl = `/api/download?path=${encodeURIComponent(b.path)}${tokenQuery}`;
    const isDir = b.is_dir;
    const actionLabel = isDir ? 'Save ZIP' : 'Save to Phone';
    const fileDesc = isDir ? `Folder (${formatBytes(b.size)})` : formatBytes(b.size);

    return `
      <div class="beam-card" id="beam-${b.id}">
        <div class="beam-card-left">
          <div class="beam-card-icon">
            <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
          </div>
          <div class="beam-card-meta">
            <div class="beam-card-title">AirDrop from ${escapeHtml(b.sender)}</div>
            <div class="beam-card-name" title="${escapeHtml(b.name)}">${escapeHtml(b.name)} (${fileDesc})</div>
          </div>
        </div>
        <div class="beam-card-actions">
          <button type="button" class="btn-beam-save" onclick="triggerDownload('${downloadUrl}', '${escapeHtml(b.name)}${isDir ? '.zip' : ''}', '${b.id}')">
            ${actionLabel}
          </button>
          <button type="button" class="btn-beam-dismiss" onclick="dismissBeam('${b.id}')" title="Dismiss">✕</button>
        </div>
      </div>
    `;
  }).join('');

  updateFilesBadge(activeBeams.length);
}

function dismissBeam(beamId) {
  dismissedBeams.add(beamId);
  const card = document.getElementById(`beam-${beamId}`);
  if (card) card.remove();
  const container = document.getElementById('incomingBeamsContainer');
  if (container && container.children.length === 0) {
    container.style.display = 'none';
  }
  fetch(`/api/dismiss_beam?id=${encodeURIComponent(beamId)}`).catch(() => {});
}

function updateFilesBadge(count) {
  const badge = document.getElementById('filesTabBadge');
  if (!badge) return;
  if (count > 0) {
    badge.innerText = count;
    badge.style.display = 'inline-block';
  } else {
    badge.style.display = 'none';
  }
}

// ONBOARDING TOUR SYSTEM
let currentOnboardSlide = 0;
const totalOnboardSlides = 5;

function openOnboarding(force = false) {
  // Never show onboarding on mobile phone
  if (!isLocalClient && !force) return;
  currentOnboardSlide = 0;
  updateOnboardSlideUI();
  const overlay = document.getElementById('onboardingOverlay');
  if (overlay) {
    overlay.classList.remove('fade-out');
    overlay.style.display = 'flex';
    document.documentElement.classList.add('init-onboarding');
  }
}

function finishOnboarding() {
  localStorage.setItem('hotspot_onboarded', 'true');
  document.documentElement.classList.remove('init-onboarding');
  const overlay = document.getElementById('onboardingOverlay');
  if (overlay) {
    overlay.classList.add('fade-out');
    setTimeout(() => {
      overlay.style.display = 'none';
      overlay.classList.remove('fade-out');
      showToast('Welcome to Hotspot Share! Ready for transfers.');
      const qrCard = document.getElementById('qrConnectCard');
      if (qrCard && qrCard.style.display !== 'none') {
        qrCard.classList.add('pulse-highlight');
        setTimeout(() => qrCard.classList.remove('pulse-highlight'), 2200);
      }
    }, 300);
  }
}

function handleOnboardingBackdropClick(e) {
  finishOnboarding();
}

function updateOnboardSlideUI() {
  const track = document.getElementById('onboardingTrack');
  if (track) {
    track.style.transform = `translate3d(-${currentOnboardSlide * 20}%, 0, 0)`;
  }

  for (let i = 0; i < totalOnboardSlides; i++) {
    const slide = document.getElementById(`onboard-slide-${i}`);
    if (slide) slide.classList.toggle('active', i === currentOnboardSlide);
  }
  const dots = document.querySelectorAll('#slideDots .dot');
  dots.forEach((d, idx) => {
    d.classList.toggle('active', idx === currentOnboardSlide);
  });

  const backBtn = document.getElementById('onboardBackBtn');
  const nextBtn = document.getElementById('onboardNextBtn');
  if (backBtn) {
    backBtn.style.display = currentOnboardSlide === 0 ? 'none' : 'inline-block';
  }
  if (nextBtn) {
    if (currentOnboardSlide === totalOnboardSlides - 1) {
      nextBtn.innerHTML = 'Get Started &rarr;';
    } else {
      nextBtn.innerHTML = 'Next &rarr;';
    }
  }
}

function nextOnboardSlide() {
  if (currentOnboardSlide < totalOnboardSlides - 1) {
    currentOnboardSlide++;
    updateOnboardSlideUI();
  } else {
    finishOnboarding();
  }
}

function prevOnboardSlide() {
  if (currentOnboardSlide > 0) {
    currentOnboardSlide--;
    updateOnboardSlideUI();
  }
}

function goToOnboardSlide(idx) {
  if (idx >= 0 && idx < totalOnboardSlides) {
    currentOnboardSlide = idx;
    updateOnboardSlideUI();
  }
}

document.addEventListener('keydown', (e) => {
  const overlay = document.getElementById('onboardingOverlay');
  if (!overlay || overlay.style.display === 'none') return;
  const welcomeStage = document.getElementById('onboardingWelcomeStage');
  const isWelcomeVisible = welcomeStage && welcomeStage.style.display !== 'none';

  if (e.key === 'Escape') {
    finishOnboarding();
  } else if (!isWelcomeVisible) {
    if (e.key === 'ArrowRight' || e.key === 'Enter') {
      nextOnboardSlide();
    } else if (e.key === 'ArrowLeft') {
      prevOnboardSlide();
    }
  } else if (isWelcomeVisible && (e.key === 'Enter' || e.key === ' ')) {
    finishOnboarding();
  }
});

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
  const target = document.getElementById('tab-' + tabId);
  if (target) target.classList.add('active');
  if (tabId === 'files') {
    updateFilesBadge(0);
    filesNeedRefresh = false;
    loadFiles();
  }
  if (tabId === 'clip') {
    updateClipboardTabUI();
    loadClip();
  }
  if (tabId === 'security') renderSecuritySection();
}

async function manualRefresh() {
  showToast('Refreshing...');
  const rBtn = document.getElementById('refreshBtn');
  if (rBtn) rBtn.style.opacity = '0.5';
  try {
    await sendHeartbeatAndPollStatus();
    if (activeTabId === 'files') await loadFiles();
    if (activeTabId === 'clip') await loadClip(true);
    if (activeTabId === 'security') await renderSecuritySection();
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

function handleFileSelectClick(inputId) {
  if (isLocalClient && (!currentConnectedPhoneName || !currentConnectedPhoneIp)) {
    showToast('No phone connected. Scan the QR code above with your phone camera first.');
    const qrCard = document.getElementById('qrConnectCard');
    if (qrCard) {
      qrCard.scrollIntoView({ behavior: 'smooth' });
      qrCard.classList.add('pulse-highlight');
      setTimeout(() => qrCard.classList.remove('pulse-highlight'), 1200);
    }
    return;
  }
  const el = document.getElementById(inputId);
  if (el) el.click();
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

  if (isLocalClient && (!currentConnectedPhoneName || !currentConnectedPhoneIp)) {
    showToast('No phone connected. Scan the QR code above with your phone camera first.');
    const qrCard = document.getElementById('qrConnectCard');
    if (qrCard) {
      qrCard.scrollIntoView({ behavior: 'smooth' });
      qrCard.classList.add('pulse-highlight');
      setTimeout(() => qrCard.classList.remove('pulse-highlight'), 1200);
    }
    return;
  }

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
    if (isLocalClient && (!currentConnectedPhoneName || !currentConnectedPhoneIp)) {
      fileInput.value = '';
      showToast('No phone connected. Scan the QR code above with your phone camera first.');
      return;
    }
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
    if (isLocalClient && (!currentConnectedPhoneName || !currentConnectedPhoneIp)) {
      folderInput.value = '';
      showToast('No phone connected. Scan the QR code above with your phone camera first.');
      return;
    }
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

function handleSummaryCancel() {
  cancelAllUploads();
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
  let uploadUrl = `/api/upload?id=${encodeURIComponent(task.cardId)}&name=${encodeURIComponent(task.file.name)}&relPath=${encodeURIComponent(task.relPath)}&targetDir=${encodeURIComponent(currentPath)}&offset=${offset}&totalSize=${task.file.size}&conflict=rename`;
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
  if (typeof pinModalShown !== 'undefined' && pinModalShown) return;
  if (e && e.currentTarget && e.currentTarget.id === 'modal' && e.target !== e.currentTarget && !e.target.closest('.modal-close')) {
    return;
  }
  const modalEl = document.getElementById('modal');
  if (modalEl) modalEl.classList.remove('active');
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
    try {
      const res = await fetch('/api/clear_all_files', {
        method: 'POST',
        headers: authHeaders()
      });
      if (res.ok) {
        showToast('All files cleared');
        loadFiles();
        return;
      }
    } catch (e) {}

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

function updateClipboardTabUI() {
  const isPhone = !isLocalClient;
  const targetDevice = isPhone ? 'PC' : (currentConnectedPhoneName || 'Phone');

  const clipCardTitle = document.getElementById('clipCardTitle');
  if (clipCardTitle) {
    clipCardTitle.innerText = isPhone ? 'PC CLIPBOARD' : (targetDevice.toUpperCase() + ' CLIPBOARD');
  }

  const fetchClipLabel = document.getElementById('fetchClipLabel');
  if (fetchClipLabel) {
    fetchClipLabel.innerText = isPhone ? 'Fetch from PC' : `Fetch from ${targetDevice}`;
  }

  const clipText = document.getElementById('clipText');
  if (clipText) {
    clipText.placeholder = isPhone
      ? "Type or paste text here. Tap 'Send Text to PC' to paste with Ctrl+V on your laptop..."
      : `Type or paste text here. Tap 'Send Text to ${targetDevice}' to sync with your ${targetDevice}...`;
  }

  const sendClipTextLabel = document.getElementById('sendClipTextLabel');
  if (sendClipTextLabel) {
    sendClipTextLabel.innerText = isPhone
      ? 'Send Text to PC (Ctrl+V)'
      : `Send Text to ${targetDevice}`;
  }

  const clipImageCardTitle = document.getElementById('clipImageCardTitle');
  if (clipImageCardTitle) {
    clipImageCardTitle.innerText = isPhone
      ? 'SEND IMAGE TO PC CLIPBOARD'
      : `SEND IMAGE TO ${targetDevice.toUpperCase()}`;
  }

  const clipImageDesc = document.getElementById('clipImageDesc');
  if (clipImageDesc) {
    clipImageDesc.innerHTML = isPhone
      ? `Select or paste an image here to copy it directly into your PC's clipboard. You can immediately press <b>Ctrl+V</b> in Discord, Telegram, Slack, LibreOffice, GIMP, or any PC app.`
      : `Select or paste an image here to send it directly to your ${targetDevice}'s clipboard or photo gallery.`;
  }

  const btnSendImageAction = document.getElementById('btnSendImageAction');
  if (btnSendImageAction) {
    btnSendImageAction.innerText = isPhone
      ? 'Send Image to PC (Ctrl+V)'
      : `Send Image to ${targetDevice}`;
  }

  const selectImageBtnLabel = document.getElementById('selectImageBtnLabel');
  if (selectImageBtnLabel) {
    selectImageBtnLabel.innerText = isPhone
      ? 'Select Image to Copy'
      : `Select Image for ${targetDevice}`;
  }
}

async function loadClip(showFeedback = false) {
  try {
    const isPhone = !isLocalClient;
    const originDevice = isPhone ? 'PC' : (currentConnectedPhoneName || 'Phone');
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
      document.getElementById('pcImgInfo').innerText = `Image from ${originDevice} (${data.mime} &bull; ${formatBytes(data.size)})`;
      pcImgCard.style.display = 'flex';
      pcTextCard.style.display = 'none';
      if (showFeedback) showToast(`Loaded copied image from ${originDevice}`);
    } else {
      currentPcImageData = null;
      pcImgCard.style.display = 'none';
      pcTextCard.style.display = 'block';
      document.getElementById('clipText').value = data.text || '';
      if (showFeedback) showToast(`Loaded ${originDevice} clipboard text`);
    }
  } catch (err) {
    if (showFeedback) showToast('Failed to fetch clipboard');
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
  const isPhone = !isLocalClient;
  const targetDevice = isPhone ? 'PC' : (currentConnectedPhoneName || 'Phone');
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
      showToast(isPhone ? 'Image copied to PC (Press Ctrl+V on PC)' : `Image sent to ${targetDevice}`);
      cancelSelectedClipImage();
    } else {
      showToast(`Failed to send image to ${targetDevice}`);
    }
  } catch (err) {
    showToast('Error sending image');
  }
}

async function saveClipText() {
  const text = document.getElementById('clipText').value;
  const isPhone = !isLocalClient;
  const targetDevice = isPhone ? 'PC' : (currentConnectedPhoneName || 'Phone');
  try {
    const res = await fetch('/api/clipboard', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ type: 'text', text: text })
    });
    if (res.ok) {
      showToast(isPhone ? 'Text copied to PC (Press Ctrl+V on PC)' : `Text sent to ${targetDevice}`);
    } else {
      showToast(`Failed to send text to ${targetDevice}`);
    }
  } catch (err) {
    showToast('Failed to send text');
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
    
    let uploadUrl = `/api/upload?name=${encodeURIComponent(filename)}&relPath=${encodeURIComponent(filename)}&conflict=rename`;
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

function updateThemeUI(theme) {
  const isDark = theme === 'dark';
  const label = document.getElementById('themeLabel');
  // When dark -> clicking switches to Light mode, so label is 'Light'
  // When light -> clicking switches to Dark mode, so label is 'Dark'
  if (label) label.innerText = isDark ? 'Light' : 'Dark';
  const themeBtn = document.getElementById('themeBtn');
  if (themeBtn) {
    themeBtn.title = isDark ? 'Switch to Light mode' : 'Switch to Dark mode';
  }
  const icon = document.getElementById('themeIcon');
  if (icon) {
    if (isDark) {
      // Dark active: next action is Light (show sun icon)
      icon.innerHTML = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
      icon.setAttribute('style', 'fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;');
    } else {
      // Light active: next action is Dark (show moon icon)
      icon.innerHTML = '<path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-2.98 0-5.4-2.42-5.4-5.4 0-1.81.89-3.42 2.26-4.4-.44-.06-.9-.1-1.36-.1z"/>';
      icon.setAttribute('style', 'fill:currentColor;stroke:none;');
    }
  }
}

function toggleTheme() {
  const html = document.documentElement;
  const cur = html.getAttribute('data-theme') || 'light';
  const next = cur === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeUI(next);
}

const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
updateThemeUI(savedTheme);

window.addEventListener('DOMContentLoaded', () => {
  const isDesktop = !(/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent));
  if (isDesktop && !localStorage.getItem('hotspot_onboarded')) {
    openOnboarding(true);
  }
  updateSliderPosition('upload');
  sendHeartbeatAndPollStatus();
  setInterval(sendHeartbeatAndPollStatus, 2000);

  if ('serviceWorker' in navigator && (window.location.protocol === 'http:' || window.location.protocol === 'https:')) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
  }
});