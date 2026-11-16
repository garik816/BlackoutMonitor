# Modular OpenWrt packages (experimental branch)

Target: **OpenWrt 25.12.6, x86_64, apk**.

| APK | Responsibility | Dependency |
| --- | --- | --- |
| `luci-app-smartmeter-monitor` | ARP/ICMP/HTTP availability service and LuCI calendar | base LuCI, Python, curl, nmap |
| `luci-app-blackout-monitor` | outage schedule collector, analysis and LuCI schedule view | `luci-app-smartmeter-monitor` |

Both APKs are built from the **same repository `files/` source tree**, with non-overlapping package-owned paths. Python guard `tests/test_package_ownership.py` enforces this in CI.

## Data preservation

- The real `/etc/config/smartmeter-availability` is user-owned, not package-owned. Only the example is packaged.
- SQLite databases in `/root/*.sqlite3` are not package-owned and must be backed up separately.
- The blackout service records its initial autostart only once in `/etc/blackout-monitor/schedule-initialized`, preserving manually disabled startup settings across upgrades.
- The availability service retains its enabled/disabled state.

## Before migrating an existing combined v0.1.x installation

**Do not install this draft over the production router until the migration is tested on a backup or spare OpenWrt 25.12.6 environment.** The previous combined `luci-app-blackout-monitor` APK owned both sets of files; v0.2.x delegates availability files to a new dependency. Verify that apk handles the ownership transfer in one upgrade transaction, with no overwrite conflicts or deleted local data.

Validate: fresh SmartMeter-only install, fresh combined install, upgrade from v0.1.x, uninstall of just blackout package, upgrade with schedule disabled, UCI persistence, SQLite history, LuCI menu placement, and signed-feed installation.

When approved, the signed feed serves both APKs. Users can install the standalone monitor through LuCI Software; installing blackout will pull in the monitor automatically.
