import unittest
import time
import re
from pathlib import Path
from hotspot_share.server import BeamTracker

class TestBeamsAndOnboarding(unittest.TestCase):
    def setUp(self):
        BeamTracker.beams.clear()
        BeamTracker.dismissed.clear()

    def test_beam_tracker_pc_to_phone(self):
        # PC (127.0.0.1) uploads a file
        BeamTracker.add_beam(
            beam_id="b1",
            name="photo.jpg",
            rel_path="photo.jpg",
            size=1024,
            is_dir=False,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )
        
        # PC viewing /api/status does NOT see its own beam as incoming
        pc_beams = BeamTracker.get_active_beams("127.0.0.1")
        self.assertEqual(len(pc_beams), 0)

        # Phone (192.168.1.50) sees incoming beam from PC
        phone_beams = BeamTracker.get_active_beams("192.168.1.50")
        self.assertEqual(len(phone_beams), 1)
        self.assertEqual(phone_beams[0]["name"], "photo.jpg")
        self.assertEqual(phone_beams[0]["size"], 1024)
        self.assertFalse(phone_beams[0]["is_dir"])

    def test_beam_tracker_folder(self):
        # PC sends a folder
        BeamTracker.add_beam(
            beam_id="b2",
            name="Documents",
            rel_path="Documents",
            size=4096,
            is_dir=True,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )

        phone_beams = BeamTracker.get_active_beams("192.168.1.88")
        self.assertEqual(len(phone_beams), 1)
        self.assertTrue(phone_beams[0]["is_dir"])
        self.assertEqual(phone_beams[0]["name"], "Documents")

    def test_beam_dismissal(self):
        BeamTracker.add_beam(
            beam_id="b3",
            name="report.pdf",
            rel_path="report.pdf",
            size=2048,
            is_dir=False,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )

        self.assertEqual(len(BeamTracker.get_active_beams("192.168.1.77")), 1)
        BeamTracker.dismiss_beam("b3", "192.168.1.77")
        self.assertEqual(len(BeamTracker.get_active_beams("192.168.1.77")), 0)

    def test_beam_expiration(self):
        BeamTracker.add_beam(
            beam_id="b4",
            name="old.txt",
            rel_path="old.txt",
            size=10,
            is_dir=False,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )
        BeamTracker.beams[0]["time"] = time.time() - 700  # Older than 600s
        self.assertEqual(len(BeamTracker.get_active_beams("192.168.1.66")), 0)

    def test_onboarding_html_structure(self):
        html_path = Path("web/index.html")
        self.assertTrue(html_path.exists())
        content = html_path.read_text(encoding="utf-8")

        # Verify Onboarding modal elements
        self.assertIn('id="onboardingOverlay"', content)
        self.assertIn('id="onboard-slide-0"', content)
        self.assertIn('id="onboard-slide-1"', content)
        self.assertIn('id="onboard-slide-2"', content)
        self.assertIn('id="onboard-slide-3"', content)

        # Verify key product messaging
        self.assertIn("AirDrop for Linux", content)
        self.assertIn("100% Private & Open Source", content)
        self.assertIn("No Login or Accounts", content)
        self.assertIn("Zero Data Retention", content)
        self.assertIn("Camera QR Pairing", content)
        self.assertIn("Clipboard & Folder Transfers", content)

        # Verify incoming beam and toolbar elements
        self.assertIn('id="incomingBeamsContainer"', content)
        self.assertIn('id="tourBtn"', content)
        self.assertIn('id="filesTabBadge"', content)
        self.assertIn('id="btnSelectFiles"', content)
        self.assertIn('id="btnSelectFolder"', content)

    def test_onboarding_app_js_methods(self):
        js_path = Path("web/app.js")
        self.assertTrue(js_path.exists())
        js = js_path.read_text(encoding="utf-8")

        # Verify essential functions
        self.assertIn("function triggerDownload(", js)
        self.assertIn("function syncIncomingBeams(", js)
        self.assertIn("function openOnboarding(", js)
        self.assertIn("function finishOnboarding(", js)
        self.assertIn("function handleFileSelectClick(", js)
        self.assertIn("localStorage.getItem('hotspot_onboarded')", js)

    def test_no_emojis_in_onboarding_and_beams(self):
        html_path = Path("web/index.html")
        content = html_path.read_text(encoding="utf-8")
        
        # Onboarding section must be free of emoji glyphs
        onboard_start = content.find('id="onboardingOverlay"')
        self.assertNotEqual(onboard_start, -1)
        onboard_chunk = content[onboard_start:onboard_start + 4500]
        
        for forbidden in ["🔓", "🛡️", "📜", "🚀", "⬇"]:
            self.assertNotIn(forbidden, onboard_chunk, f"Forbidden emoji {forbidden} found in onboarding HTML")

        js_path = Path("web/app.js")
        js_chunk = js_path.read_text(encoding="utf-8")
        self.assertNotIn("Get Started 🚀", js_chunk)
        self.assertNotIn("Save to Phone ⬇", js_chunk)

    def test_connection_guards_in_app(self):
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")

        # Must guard against sending to no one when no phone is connected
        self.assertIn("No phone connected", js)
        self.assertIn("waiting-for-phone", js)
        self.assertIn("waiting-for-phone", css)
        self.assertIn("pulse-highlight", js)
        self.assertIn("pulse-highlight", css)

        # Mobile must suppress onboarding
        self.assertIn("if (!isLocalClient && !force) return;", js)

    def test_fullscreen_onboarding_and_original_logo(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")

        # Full-screen sliding track and original logo
        self.assertIn('id="onboardingTrack"', html)
        self.assertIn('class="onboarding-original-logo"', html)
        self.assertIn('onboarding-top-bar', html)
        self.assertIn('init-onboarding', html)
        self.assertIn('init-onboarding', css)

        # No temporary welcome stage (must enter app directly)
        self.assertNotIn('id="onboardingWelcomeStage"', html)
        self.assertNotIn('function showWelcomeStage(', js)

        # No top clutter: skip button, step 1 of 5 pill, and subtitle removed from header
        self.assertNotIn('class="onboarding-skip"', html)
        self.assertNotIn('id="onboardStepPill"', html)
        self.assertNotIn('AirDrop for Linux</span>', html)

        # Full screen styles
        self.assertIn("width: 100vw;", css)
        self.assertIn("height: 100vh;", css)
        self.assertIn(".onboarding-track", css)
        self.assertIn(".onboarding-original-logo", css)

        # JS methods and variables
        self.assertIn("let onboardingTriggered = false;", js)
        self.assertIn("translate3d(-", js)

    def test_desktop_pwa_suppression(self):
        css = Path("web/style.css").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")

        # CSS must strictly suppress PWA buttons on desktop
        self.assertIn("@media (min-width: 769px)", css)
        self.assertIn("#pwaHeaderBtn", css)
        self.assertIn("#pwaMobileBanner", css)

        # JS must guard PWA install for mobile devices only
        self.assertIn("function isMobileClient(", js)
        self.assertIn("if (isLocalClient) return false;", js)

    def test_single_desktop_entry_deduplication(self):
        # Verify packaging desktop file
        desktop_file = Path("packaging/desktop/hotspot-share.desktop")
        self.assertTrue(desktop_file.exists())
        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("Name=Hotspot Share", content)
        self.assertIn("Exec=hotspot-share-gui", content)

        # Verify Makefile contains deduplication logic
        makefile = Path("Makefile").read_text(encoding="utf-8")
        self.assertIn("hotspot-share_hotspot-share.desktop", makefile)
        self.assertIn("NoDisplay=true", makefile)

    def test_makefile_uninstall_purges_persistent_storage(self):
        makefile = Path("Makefile").read_text(encoding="utf-8")
        self.assertIn("uninstall-user:", makefile)
        self.assertIn("Downloads/HotspotShare", makefile)
        self.assertIn(".local/share/hotspot-share", makefile)
        self.assertIn(".cache/hotspot-share", makefile)
        self.assertIn(".config/hotspot-share", makefile)

    def test_clear_all_files_endpoint_and_ui(self):
        server_py = Path("src/hotspot_share/server.py").read_text(encoding="utf-8")
        app_js = Path("web/app.js").read_text(encoding="utf-8")
        self.assertIn("'/api/clear_all_files'", server_py)
        self.assertIn("All shared files cleared", server_py)
        self.assertIn("fetch('/api/clear_all_files'", app_js)

    def test_light_theme_default_and_icon_labels(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")

        # Must default to light theme in html attribute and js
        self.assertIn('data-theme="light"', html)
        self.assertIn("localStorage.getItem('theme') || 'light'", html)
        self.assertIn("localStorage.getItem('theme') || 'light'", js)
        self.assertIn(':root,\n:root[data-theme="light"]', css)

        # Icons must have visible descriptive names/labels
        self.assertIn('id="btn-security"', html)
        self.assertIn('id="btn-about"', html)
        self.assertIn('id="tourBtn"', html)
        self.assertIn('<span class="btn-label">Tour</span>', html)
        self.assertIn('id="refreshBtn"', html)
        self.assertIn('<span class="btn-label">Refresh</span>', html)
        self.assertIn('id="themeLabel">Dark</span>', html)
        self.assertIn('id="disconnectMiniBtn"', html)

        # Dropzone and toolbar action buttons must have self-describing text
        self.assertIn('<span>Select Files</span>', html)
        self.assertIn('<span>Select Folder</span>', html)
        self.assertIn('<span>+ Folder</span>', html)

    def test_clipboard_privacy_protection(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")

        # Clipboard section has privacy notice banner
        self.assertIn('clip-privacy-banner', html)
        self.assertIn('Zero Auto-Sync Privacy', html)

        # Startup and PIN auth must NOT auto-fetch clipboard unless on clipboard tab
        self.assertIn("if (activeTabId === 'clip') {\n        loadClip();\n      }", js)

    def test_security_tab_and_explicit_enable_button(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")

        # Security must have its own dedicated tab button and section
        self.assertIn('id="btn-security"', html)
        self.assertIn('id="tab-security"', html)
        self.assertIn("switchTab('security')", html)

        # Must explicitly have Enable and Disable actions rather than ambiguous static labels
        self.assertIn('Enable PIN Protection', html)
        self.assertIn('Enable PIN Protection', js)
        self.assertIn('Disable PIN Protection', js)
        self.assertIn('secToggleBtnContainer', html)
        self.assertIn('renderSecuritySection', js)

        # Graceful lock emblem used; basic shield icon and AI-slop green dot bubbles removed
        self.assertIn('sec-icon-emblem', html)
        self.assertNotIn('sec-icon-shield', html)
        self.assertIn('sec-status-badge', html)
        self.assertNotIn('sec-status-dot', html)
        self.assertNotIn('sec-status-dot', css)

        # Verbose behind-the-scenes cards removed; clean single sentence description retained
        self.assertNotIn('How Security Works Behind The Scenes', html)
        self.assertNotIn('100 Million Keyspace', html)
        self.assertIn('Require an 8-digit code before connecting devices can transfer files or access clipboard.', html)

        # Clean CSS styling
        self.assertIn('.security-wrapper', css)
        self.assertIn('.sec-status-badge', css)
        self.assertIn('.sec-icon-emblem', css)

    def test_mobile_pin_screen_and_responsiveness(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")
        gui_c = Path("gui/gui.c").read_text(encoding="utf-8")

        # 1. Dedicated full-screen PIN overlay with NO exit button
        self.assertIn('id="pinAuthOverlay"', html)
        self.assertIn('pin-auth-fullscreen', html)
        self.assertIn('id="pinAuthError"', html)
        self.assertIn('id="pinAuthInput"', html)
        self.assertIn('id="btnSubmitPinAuth"', html)
        self.assertIn('function showPinAuthScreen', js)
        self.assertIn('function hidePinAuthScreen', js)
        self.assertIn('.pin-auth-fullscreen', css)

        # Ensure PIN overlay does NOT contain a modal-close exit button
        pin_chunk_start = html.find('id="pinAuthOverlay"')
        pin_chunk_end = html.find('id="modal"')
        self.assertNotEqual(pin_chunk_start, -1)
        self.assertNotEqual(pin_chunk_end, -1)
        pin_chunk = html[pin_chunk_start:pin_chunk_end]
        self.assertNotIn('modal-close', pin_chunk)
        self.assertNotIn('&times;', pin_chunk)

        # 2. Safe response handling in submitPinAuth (no JSON syntax error crash)
        self.assertIn('JSON.parse', js)
        self.assertIn('await res.text()', js)

        # 3. Mobile responsiveness in style.css to prevent horizontal swiping
        self.assertIn('overflow-x: hidden !important', css)
        self.assertIn('max-width: 100vw !important', css)

        # 4. Security tab phone-awareness
        self.assertIn('unpairPhoneSession', js)
        self.assertIn('Protected by', js)

        # 5. GTK desktop window minimum size constraints
        self.assertIn('GDK_HINT_MIN_SIZE', gui_c)
        self.assertIn('gtk_widget_set_size_request(main_window, 720, 540)', gui_c)

    def test_pin_auth_full_screen_shield_and_no_cache(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")
        server_py = Path("src/hotspot_share/server.py").read_text(encoding="utf-8")
        sw_js = Path("web/sw.js").read_text(encoding="utf-8")

        # 1. Server-side auth locking injection
        self.assertIn('data-auth-locked="true"', server_py)
        self.assertIn('__AUTH_LOCKED__', html)
        self.assertIn('html[data-auth-locked="true"] header', css)
        self.assertIn('html[data-auth-locked="true"] main', css)
        self.assertIn('display: none !important', css)

        # 2. Complete absence of exit buttons on PIN overlay
        self.assertIn('id="pinAuthForm"', html)
        self.assertIn('type="submit"', html)
        self.assertIn('id="btnSubmitPinAuth"', html)
        self.assertIn('id="btnSubmitPinAuthText"', html)

        # 3. Static assets Cache-Control must prevent stale caching
        self.assertIn("self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')", server_py)
        self.assertIn("v=2.1.4", html)
        self.assertIn("hotspot-share-v2.1.4", sw_js)

        # 4. PIN input sanitization in backend (strip spaces & dashes)
        self.assertIn("re.sub(r'[\\s\\-]+', '', raw_val)", server_py)

        # 5. No onboarding on mobile phones
        self.assertIn("const isDesktop = !(/Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent));", js)

        # 6. No HTML5 pattern attribute (prevents "Please match the format requested" popups)
        self.assertNotIn('pattern="[0-9]*"', html)
        self.assertIn('novalidate', html)

        # 7. Official branding (logo, title, description) on mobile pairing screen and header
        self.assertIn('pin-auth-branding', html)
        self.assertIn('pin-auth-app-logo', html)
        self.assertIn('Hotspot Share', html)
        self.assertIn('mobile-brand-bar', html)
        self.assertIn('mobile-brand-logo', html)

    def test_security_pin_enabled_by_default(self):
        cli_code = Path("src/hotspot_share/cli.py").read_text(encoding="utf-8")
        auth_code = Path("src/hotspot_share/auth.py").read_text(encoding="utf-8")
        self.assertIn("AuthManager.enable_pin_auth", cli_code)
        self.assertIn("--no-auth", cli_code)
        self.assertIn("auth_enabled = True", auth_code)
        self.assertIn("DEFAULT_PIN_LENGTH = 8", auth_code)

    def test_disconnect_and_about_section_and_contact_email(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")
        server_py = Path("src/hotspot_share/server.py").read_text(encoding="utf-8")
        setup_py = Path("setup.py").read_text(encoding="utf-8")
        snap_yaml = Path("snap/snapcraft.yaml").read_text(encoding="utf-8")

        # 1. Disconnect endpoint and UI
        self.assertIn("'/api/auth/disconnect'", server_py)
        self.assertIn("disconnectAllDevices", js)
        self.assertIn("btn-disconnect-mini", css)
        self.assertIn("btn-disconnect-mini", html)

        # 2. About section and modal
        self.assertIn("openAboutModal", js)
        self.assertIn("about-modal-wrapper", css)
        self.assertIn("penguinatnight1@gmail.com", js)
        self.assertIn('id="btn-about"', html)

        # 3. Contact email updated everywhere
        self.assertIn("penguinatnight1@gmail.com", setup_py)
        self.assertIn("penguinatnight1@gmail.com", snap_yaml)

    def test_clipboard_privacy_no_lock_icon_and_send_image_to_phone(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")

        # 1. No SVG lock icon in privacy banner (clean, not AI slop)
        self.assertIn('clip-privacy-banner', html)
        self.assertIn('Zero Auto-Sync Privacy', html)
        # Verify no SVG tag inside clip-privacy-banner
        banner_match = re.search(r'<div class="clip-privacy-banner">(.*?)</div>', html, re.DOTALL)
        self.assertIsNotNone(banner_match)
        self.assertNotIn('<svg', banner_match.group(1))

        # 2. Support for Send Image to Phone on desktop
        self.assertIn('SEND IMAGE TO PHONE', html)
        self.assertIn('Send Image to Phone', html)
        self.assertIn('updateClipboardTabUI', js)
        self.assertIn('Send Image to ${targetDevice}', js)

    def test_about_tab_skip_button_zoom_prevention_and_shortcuts(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")
        gui_c = Path("gui/gui.c").read_text(encoding="utf-8")

        # 1. About section tab (independent tab, not a modal)
        self.assertIn('id="tab-about"', html)
        self.assertIn('id="btn-about"', html)
        self.assertIn('about-section-container', html)
        self.assertIn('about-section-container', css)

        # 2. Professional, understated version typography (no colorful badge)
        self.assertIn('about-version-text', html)
        self.assertIn('about-version-text', css)

        # 3. Onboarding tour skip button on top
        self.assertIn('btn-onboard-skip-top', html)
        self.assertIn('btn-onboard-skip-top', css)

        # 4. Zoom and pinch prevention across GUI C and Web frontend
        self.assertIn('on_webview_scroll', gui_c)
        self.assertIn('notify::zoom-level', gui_c)
        self.assertIn('webkit_web_view_set_zoom_level', gui_c)
        self.assertIn("overscroll-behavior: none", css)
        self.assertIn("touch-action: pan-x pan-y", css)
        self.assertIn("window.addEventListener('wheel'", js)
        self.assertIn("window.addEventListener('gesturestart'", js)

        # 5. Desktop keyboard shortcuts
        self.assertIn("shortcuts-grid", html)
        self.assertIn("switchTab('upload')", js)
        self.assertIn("switchTab('files')", js)
        self.assertIn("switchTab('clip')", js)
        self.assertIn("switchTab('security')", js)
        self.assertIn("switchTab('about')", js)
        self.assertIn("fileSearchInput", js)
        self.assertIn("toggleTheme()", js)

    def test_mobile_grid_navigation_and_scrolling(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        js = Path("web/app.js").read_text(encoding="utf-8")
        css = Path("web/style.css").read_text(encoding="utf-8")

        # 1. Strict 5-column CSS grid navigation on mobile
        self.assertIn("grid-template-columns: repeat(5, 1fr) !important;", css)
        self.assertIn("flex-direction: column !important;", css)

        # 2. Absolute notification badge positioning on Files tab (zero overlap with Clipboard)
        self.assertIn("position: absolute !important;", css)
        self.assertIn("right: calc(50% - 18px) !important;", css)

        # 3. Smooth touch scrolling on mobile
        self.assertIn("touch-action: manipulation", css)
        self.assertIn("-webkit-overflow-scrolling: touch", css)
        self.assertIn("overflow-y: auto !important;", css)
        self.assertIn("isDesktopClient", js)

        # 4. Tab-aware incoming beams visibility and batch controls
        self.assertIn("tabId === 'upload' || tabId === 'files'", js)
        self.assertIn("beam-batch-header", css)
        self.assertIn("downloadAllBeams", js)
        self.assertIn("dismissAllBeams", js)

        # 5. Viewport scroll reset on tab change
        self.assertIn("window.scrollTo({ top: 0, behavior: 'instant' })", js)

        # 6. Valid HTML nesting for security-wrapper
        self.assertIn('</div>\n    </div>\n  </section>', html)

        # 7. Desktop keyboard shortcuts hidden on mobile web
        self.assertIn("about-shortcuts-card", html)
        self.assertIn(".about-shortcuts-card", css)
        self.assertIn("updateMobileShortcutsVisibility", js)

if __name__ == "__main__":
    unittest.main()



