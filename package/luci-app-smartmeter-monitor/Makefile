include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-smartmeter-monitor
PKG_VERSION:=0.2.0
PKG_RELEASE:=1
PKG_LICENSE:=Unspecified
PKG_MAINTAINER:=garik816
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-smartmeter-monitor
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=SmartMeterMonitor availability monitoring
  URL:=https://github.com/garik816/BlackoutMonitor
  DEPENDS:=+luci-base +rpcd-mod-file +python3-light +python3-sqlite3 +python3-xml +python3-urllib +curl +nmap
endef

define Package/luci-app-smartmeter-monitor/description
  Standalone OpenWrt availability monitoring (ARP, ICMP, HTTP) with LuCI views.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/luci-app-smartmeter-monitor/install
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_DIR) $(1)/usr/share/luci/menu.d
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DIR) $(1)/usr/share/ucode/luci/template/my-scripts
	$(INSTALL_DIR) $(1)/www/luci-static/resources/view/my-scripts
	$(INSTALL_CONF) $(CURDIR)/files/etc/config/smartmeter-availability.example $(1)/etc/config/smartmeter-availability.example
	$(INSTALL_BIN) $(CURDIR)/files/etc/init.d/smartmeter-availability $(1)/etc/init.d/smartmeter-availability
	$(INSTALL_BIN) $(CURDIR)/files/usr/bin/smartmeter-availability $(1)/usr/bin/smartmeter-availability
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/smartmeter-availability-config $(1)/usr/libexec/smartmeter-availability-config
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/smartmeter-availability-dashboard $(1)/usr/libexec/smartmeter-availability-dashboard
	$(INSTALL_DATA) $(CURDIR)/files/usr/libexec/smartmeter_config.py $(1)/usr/libexec/smartmeter_config.py
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/luci/menu.d/luci-app-my-scripts.json $(1)/usr/share/luci/menu.d/luci-app-my-scripts.json
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/rpcd/acl.d/luci-app-my-scripts.json $(1)/usr/share/rpcd/acl.d/luci-app-my-scripts.json
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/ucode/luci/template/my-scripts/smartmeter.ut $(1)/usr/share/ucode/luci/template/my-scripts/smartmeter.ut
	$(INSTALL_DATA) $(CURDIR)/files/www/luci-static/resources/view/my-scripts/smartmeter.js $(1)/www/luci-static/resources/view/my-scripts/smartmeter.js
endef

# Keep user UCI settings and SQLite history outside package ownership.
define Package/luci-app-smartmeter-monitor/postinst
#!/bin/sh
[ -z "$$IPKG_INSTROOT" ] || exit 0
if [ ! -e /etc/config/smartmeter-availability ]; then
  cp /etc/config/smartmeter-availability.example /etc/config/smartmeter-availability
  uci -q set smartmeter-availability.main.enabled='0'
  uci -q commit smartmeter-availability
  /etc/init.d/smartmeter-availability enable 2>/dev/null || true
fi
/etc/init.d/rpcd reload 2>/dev/null || true
/etc/init.d/smartmeter-availability enabled >/dev/null 2>&1 && \
  /etc/init.d/smartmeter-availability restart 2>/dev/null || true
rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*.json
exit 0
endef

define Package/luci-app-smartmeter-monitor/prerm
#!/bin/sh
[ -z "$$IPKG_INSTROOT" ] || exit 0
/etc/init.d/smartmeter-availability stop 2>/dev/null || true
exit 0
endef

$(eval $(call BuildPackage,luci-app-smartmeter-monitor))
