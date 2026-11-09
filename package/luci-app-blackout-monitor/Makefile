include $(TOPDIR)/rules.mk
PKG_NAME:=luci-app-blackout-monitor
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=Unspecified
PKG_MAINTAINER:=garik816
PKGARCH:=all

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-blackout-monitor
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=BlackoutMonitor and SmartMeterMonitor
  URL:=https://github.com/garik816/BlackoutMonitor
  DEPENDS:=+luci-base +rpcd-mod-file +python3-light +python3-sqlite3 +python3-xml +python3-urllib +curl +nmap
endef

define Package/luci-app-blackout-monitor/description
  LuCI pages for availability monitoring, outage schedules and SQLite analytics.
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/luci-app-blackout-monitor/install
	$(INSTALL_DIR) $(1)
	$(CP) $(CURDIR)/files/. $(1)/
	chmod 0755 $(1)/etc/init.d/smartmeter-availability \
		$(1)/etc/init.d/svitlo-schedule \
		$(1)/usr/bin/smartmeter-availability \
		$(1)/usr/libexec/smartmeter-availability-config \
		$(1)/usr/libexec/smartmeter-availability-dashboard \
		$(1)/usr/libexec/svitlo-schedule \
		$(1)/usr/libexec/svitlo-schedule-watch
endef

# Existing UCI configuration and /root/*.sqlite3 are never package-owned.
define Package/luci-app-blackout-monitor/postinst
#!/bin/sh
[ -z "$$IPKG_INSTROOT" ] || exit 0
if [ ! -e /etc/config/smartmeter-availability ]; then
	cp /etc/config/smartmeter-availability.example /etc/config/smartmeter-availability
	uci -q set smartmeter-availability.main.enabled='0'
	uci -q commit smartmeter-availability
	/etc/init.d/smartmeter-availability enable 2>/dev/null || true
	/etc/init.d/svitlo-schedule enable 2>/dev/null || true
fi
/etc/init.d/rpcd reload 2>/dev/null || true
/etc/init.d/smartmeter-availability enabled >/dev/null 2>&1 && \
	/etc/init.d/smartmeter-availability restart 2>/dev/null || true
/etc/init.d/svitlo-schedule enabled >/dev/null 2>&1 && \
	/etc/init.d/svitlo-schedule restart 2>/dev/null || true
rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*.json
exit 0
endef

define Package/luci-app-blackout-monitor/prerm
#!/bin/sh
[ -z "$$IPKG_INSTROOT" ] || exit 0
/etc/init.d/smartmeter-availability stop 2>/dev/null || true
/etc/init.d/svitlo-schedule stop 2>/dev/null || true
exit 0
endef

$(eval $(call BuildPackage,luci-app-blackout-monitor))
