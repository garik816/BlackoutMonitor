"""Guard against duplicated, omitted or conflicting OpenWrt package payloads."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"


def owned_files(package):
    makefile = ROOT / "package" / package / "Makefile"
    source = makefile.read_text(encoding="utf-8")
    paths = re.findall(r"\$\(CURDIR\)/files/([^\s\\]+)", source)
    assert paths, f"No owned files found in {makefile}"
    assert len(paths) == len(set(paths)), f"Duplicate install path in {makefile}"
    return set(paths)


def main():
    smart = owned_files("luci-app-smartmeter-monitor")
    blackout = owned_files("luci-app-blackout-monitor")
    actual = {str(path.relative_to(FILES)).replace("\\", "/")
              for path in FILES.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}
    assert not (smart & blackout), f"Overlapping package payloads: {smart & blackout}"
    assert actual == (smart | blackout), (
        f"Unowned files: {actual - (smart | blackout)}; missing sources: {(smart | blackout) - actual}"
    )
    blackout_mk = (ROOT / "package/luci-app-blackout-monitor/Makefile").read_text(encoding="utf-8")
    assert "DEPENDS:=+luci-app-smartmeter-monitor" in blackout_mk
    assert "etc/config/smartmeter-availability.example" in smart
    assert not any(path.startswith("etc/config/") for path in blackout)
    print(f"PASS: {len(smart)} smartmeter and {len(blackout)} blackout files; "
          "non-overlapping ownership, shared source and dependency confirmed")


if __name__ == "__main__":
    main()
