include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-blackout-monitor
PKG_VERSION:=0.2.0
PKG_RELEASE:=1
PKG_LICENSE:=Unspecified
PKG_MAINTAINER:=garik816
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-blackout-monitor
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=Blackout schedule and analytics
  URL:=https://github.com/garik816/BlackoutMonitor
  DEPENDS:=+luci-app-smartmeter-monitor
endef

define Package/luci-app-blackout-monitor/description
  Electricity outage schedules and analytics based on SmartMeter availability data.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/luci-app-blackout-monitor/install
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_DIR) $(1)/usr/libexec
	$(INSTALL_DIR) $(1)/usr/share/luci/menu.d
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DIR) $(1)/usr/share/ucode/luci/template/my-scripts
	$(INSTALL_DIR) $(1)/www/luci-static/resources/view/my-scripts
	$(INSTALL_BIN) $(CURDIR)/files/etc/init.d/svitlo-schedule $(1)/etc/init.d/svitlo-schedule
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/svitlo-schedule $(1)/usr/libexec/svitlo-schedule
	$(INSTALL_BIN) $(CURDIR)/files/usr/libexec/svitlo-schedule-watch $(1)/usr/libexec/svitlo-schedule-watch
	$(INSTALL_DATA) $(CURDIR)/files/usr/libexec/svitlo_analysis.py $(1)/usr/libexec/svitlo_analysis.py
	$(INSTALL_DATA) $(CURDIR)/files/usr/libexec/svitlo_schedule.py $(1)/usr/libexec/svitlo_schedule.py
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/luci/menu.d/luci-app-svitlo.json $(1)/usr/share/luci/menu.d/luci-app-svitlo.json
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/rpcd/acl.d/luci-app-svitlo.json $(1)/usr/share/rpcd/acl.d/luci-app-svitlo.json
	$(INSTALL_DATA) $(CURDIR)/files/usr/share/ucode/luci/template/my-scripts/svitlo.ut $(1)/usr/share/ucode/luci/template/my-scripts/svitlo.ut
	$(INSTALL_DATA) $(CURDIR)/files/www/luci-static/resources/view/my-scripts/svitlo.js $(1)/www/luci-static/resources/view/my-scripts/svitlo.js
endef

# Do not re-enable a service intentionally disabled by an operator on upgrades.
# /etc/blackout-monitor is deliberately not package-owned and survives upgrades.
define Package/luci-app-blackout-monitor/postinst
#!/bin/sh
[ -z "$$IPKG_INSTROOT" ] || exit 0
if [ ! -e /etc/blackout-monitor/schedule-initialized ]; then
  mkdir -p /etc/blackout-monitor
  /etc/init.d/svitlo-schedule enable 2>/dev/null || true
  touch /etc/blackout-monitor/schedule-initialized
fi
/etc/init.d/rpcd reload 2>/dev/null || true
/etc/init.d/svitlo-schedule enabled >/dev/null 2>&1 && \
  /etc/init.d/svitlo-schedule restart 2>/dev/null || true
rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*.json
exit 0
endef

define Package/luci-app-blackout-monitor/prerm
#!/bin/sh
[ -z "$$IPKG_INSTROOT" ] || exit 0
/etc/init.d/svitlo-schedule stop 2>/dev/null || true
exit 0
endef

$(eval $(call BuildPackage,luci-app-blackout-monitor))
