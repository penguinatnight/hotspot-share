CC ?= gcc
HARDENING_FLAGS ?= -fstack-protector-strong -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -fPIE -pie -Wl,-z,relro,-z,now -Wl,-z,noexecstack
CFLAGS ?= -O2 -Wall -Wno-deprecated-declarations $(HARDENING_FLAGS)
PREFIX ?= /usr/local
DESTDIR ?=
BINDIR ?= $(PREFIX)/bin
DATADIR ?= $(PREFIX)/share
PYTHON ?= python3

PKG_CONFIG_GTK ?= $(shell pkg-config --cflags --libs gtk+-3.0 webkit2gtk-4.1 2>/dev/null || pkg-config --cflags --libs gtk+-3.0 webkit2gtk-4.0 2>/dev/null)

.PHONY: all build clean install install-user uninstall test deb snap

all: build

build: gui/hotspot-share-gui

gui/hotspot-share-gui: gui/gui.c
	@mkdir -p gui
	$(CC) $(CFLAGS) gui/gui.c -o gui/hotspot-share-gui $(PKG_CONFIG_GTK)

clean:
	rm -f gui/hotspot-share-gui
	rm -rf build dist *.egg-info __pycache__ src/*/__pycache__ debian/hotspot-share debian/.debhelper *.deb *.snap

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover tests
	PYTHONPATH=src $(PYTHON) -m hotspot_share.cli --version

deb:
	dpkg-buildpackage -us -uc -b

snap:
	snapcraft

install: build
	@echo "Installing Hotspot Share to $(DESTDIR)$(PREFIX)..."
	# Binaries
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 gui/hotspot-share-gui $(DESTDIR)$(BINDIR)/hotspot-share-gui
	# Python entry wrapper
	@echo '#!/bin/sh' > $(DESTDIR)$(BINDIR)/hotspot-share
	@echo 'exec $(PYTHON) -m hotspot_share.cli "$$@"' >> $(DESTDIR)$(BINDIR)/hotspot-share
	chmod 755 $(DESTDIR)$(BINDIR)/hotspot-share
	# Python Package
	$(PYTHON) setup.py install --root=$(DESTDIR)/ --prefix=$(PREFIX) --install-layout=deb --no-compile 2>/dev/null || $(PYTHON) setup.py install --root=$(DESTDIR)/ --prefix=$(PREFIX) 2>/dev/null || true
	# Desktop and AppStream
	install -d $(DESTDIR)$(DATADIR)/applications
	install -m 644 packaging/desktop/hotspot-share.desktop $(DESTDIR)$(DATADIR)/applications/hotspot-share.desktop
	install -d $(DESTDIR)$(DATADIR)/metainfo
	install -m 644 packaging/appstream/org.yab.hotspotshare.metainfo.xml $(DESTDIR)$(DATADIR)/metainfo/org.yab.hotspotshare.metainfo.xml
	install -m 644 packaging/appstream/org.yab.hotspotshare.metainfo.xml $(DESTDIR)$(DATADIR)/metainfo/hotspot-share.metainfo.xml
	# Web Assets
	install -d $(DESTDIR)$(DATADIR)/hotspot-share/web
	cp -r web/* $(DESTDIR)$(DATADIR)/hotspot-share/web/
	# Icons
	install -d $(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps
	install -m 644 assets/icons/hotspot-share.svg $(DESTDIR)$(DATADIR)/icons/hicolor/scalable/apps/hotspot-share.svg
	@for size in 16 24 32 48 64 128 256 512; do \
		install -d $(DESTDIR)$(DATADIR)/icons/hicolor/$${size}x$${size}/apps; \
		if [ -f assets/icons/hicolor/$${size}x$${size}/apps/hotspot-share.png ]; then \
			install -m 644 assets/icons/hicolor/$${size}x$${size}/apps/hotspot-share.png $(DESTDIR)$(DATADIR)/icons/hicolor/$${size}x$${size}/apps/hotspot-share.png; \
		fi \
	done
	# Nautilus Extension
	install -d $(DESTDIR)$(DATADIR)/nautilus-python/extensions
	install -m 644 extensions/nautilus/hotspot_share_nautilus.py $(DESTDIR)$(DATADIR)/nautilus-python/extensions/hotspot_share_nautilus.py 2>/dev/null || true
	@echo "Installation complete!"

install-user: build
	@echo "Installing Hotspot Share for current user to ~/.local..."
	install -d $(HOME)/.local/bin
	install -d $(HOME)/.local/share/applications
	install -d $(HOME)/.local/share/metainfo
	install -d $(HOME)/.local/share/hotspot-share/web
	install -d $(HOME)/.local/share/nautilus-python/extensions
	install -m 755 gui/hotspot-share-gui $(HOME)/.local/bin/hotspot-share-gui
	@echo '#!/bin/sh' > $(HOME)/.local/bin/hotspot-share
	@echo 'PYTHONPATH="$(CURDIR)/src:$$PYTHONPATH" exec $(PYTHON) -m hotspot_share.cli "$$@"' >> $(HOME)/.local/bin/hotspot-share
	chmod 755 $(HOME)/.local/bin/hotspot-share
	install -m 644 packaging/desktop/hotspot-share.desktop $(HOME)/.local/share/applications/hotspot-share.desktop
	# Clean any override desktop entries that break snapd / Ubuntu App Center launching
	@rm -f $(HOME)/.local/share/applications/hotspot-share_hotspot-share*.desktop
	# If snap package is installed, mask the local desktop entry so GNOME app search shows exactly one icon
	@if [ -f /var/lib/snapd/desktop/applications/hotspot-share_hotspot-share.desktop ]; then \
		sed -i '/^\[Desktop Entry\]/a NoDisplay=true' $(HOME)/.local/share/applications/hotspot-share.desktop; \
	fi
	install -m 644 packaging/appstream/org.yab.hotspotshare.metainfo.xml $(HOME)/.local/share/metainfo/org.yab.hotspotshare.metainfo.xml
	install -m 644 packaging/appstream/org.yab.hotspotshare.metainfo.xml $(HOME)/.local/share/metainfo/hotspot-share.metainfo.xml
	cp -r web/* $(HOME)/.local/share/hotspot-share/web/
	install -d $(HOME)/.local/share/icons/hicolor/scalable/apps
	install -m 644 assets/icons/hotspot-share.svg $(HOME)/.local/share/icons/hicolor/scalable/apps/hotspot-share.svg
	@for size in 16 24 32 48 64 128 256 512; do \
		install -d $(HOME)/.local/share/icons/hicolor/$${size}x$${size}/apps; \
		if [ -f assets/icons/hicolor/$${size}x$${size}/apps/hotspot-share.png ]; then \
			install -m 644 assets/icons/hicolor/$${size}x$${size}/apps/hotspot-share.png $(HOME)/.local/share/icons/hicolor/$${size}x$${size}/apps/hotspot-share.png; \
		fi \
	done
	cp extensions/nautilus/hotspot_share_nautilus.py $(HOME)/.local/share/nautilus-python/extensions/ 2>/dev/null || true
	update-desktop-database $(HOME)/.local/share/applications 2>/dev/null || true
	gtk-update-icon-cache -f -t $(HOME)/.local/share/icons/hicolor 2>/dev/null || true
	appstreamcli refresh-cache 2>/dev/null || true
	@echo "User installation complete! You can now run 'hotspot-share-gui' or launch from your app menu."

uninstall: uninstall-user
	-rm -f $(DESTDIR)$(BINDIR)/hotspot-share $(DESTDIR)$(BINDIR)/hotspot-share-gui 2>/dev/null || true
	-rm -f $(DESTDIR)$(DATADIR)/applications/hotspot-share.desktop 2>/dev/null || true
	-rm -f $(DESTDIR)$(DATADIR)/metainfo/org.yab.hotspotshare.metainfo.xml 2>/dev/null || true
	-rm -rf $(DESTDIR)$(DATADIR)/hotspot-share 2>/dev/null || true
	-rm -f $(DESTDIR)$(DATADIR)/icons/hicolor/*/apps/hotspot-share.* 2>/dev/null || true
	-rm -f $(DESTDIR)$(DATADIR)/nautilus-python/extensions/hotspot_share_nautilus.py 2>/dev/null || true
	@echo "Hotspot Share system uninstallation complete."

uninstall-user:
	@echo "Purging Hotspot Share user files, persistent caches, and shared directories..."
	rm -f $(HOME)/.local/bin/hotspot-share $(HOME)/.local/bin/hotspot-share-gui
	rm -f $(HOME)/.local/share/applications/hotspot-share.desktop
	rm -f $(HOME)/.local/share/applications/hotspot-share_hotspot-share.desktop
	rm -f $(HOME)/.local/share/applications/hotspot-share_hotspot-share-gui.desktop
	rm -f $(HOME)/.local/share/metainfo/org.yab.hotspotshare.metainfo.xml
	rm -f $(HOME)/.local/share/metainfo/hotspot-share.metainfo.xml
	rm -rf $(HOME)/.local/share/hotspot-share
	rm -rf $(HOME)/.cache/hotspot-share
	rm -rf $(HOME)/.config/hotspot-share
	rm -rf $(HOME)/Downloads/HotspotShare
	rm -rf $(HOME)/HotspotShare
	rm -f $(HOME)/.local/share/icons/hicolor/*/apps/hotspot-share.*
	rm -f $(HOME)/.local/share/icons/hicolor/scalable/apps/hotspot-share.svg
	rm -f $(HOME)/.local/share/nautilus-python/extensions/hotspot_share_nautilus.py
	update-desktop-database $(HOME)/.local/share/applications 2>/dev/null || true
	gtk-update-icon-cache -f -t $(HOME)/.local/share/icons/hicolor 2>/dev/null || true
	@echo "Hotspot Share user uninstallation and data purge complete."

purge: uninstall-user
