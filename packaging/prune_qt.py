"""Strip an unpacked PySide6 down to what drawapp loads.

Usage: python prune_qt.py <dir containing PySide6/ and shiboken6/>

Keeps QtCore, QtGui and QtWidgets, the X11 platform plugin, and every Qt
library those need. Library needs are read from the ELF headers with
readelf, so this works on files built for another CPU.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

KEEP_MODULES = {"QtCore", "QtGui", "QtWidgets"}
KEEP_PLUGINS = {
    "platforms": {"libqxcb.so"},
    "xcbglintegrations": None,
    "platforminputcontexts": {"libcomposeplatforminputcontextplugin.so", "libibusplatforminputcontextplugin.so"},
}
KEEP_TOP_DIRS = {"Qt", "support", "__pycache__"}
_NEEDED = re.compile(r"\(NEEDED\).*\[(.+?)\]")


def needed(path: Path):
    out = subprocess.run(["readelf", "-d", str(path)], capture_output=True, text=True).stdout
    return _NEEDED.findall(out)


def main(root: Path):
    pyside = root / "PySide6"
    qt = pyside / "Qt"
    libdir = qt / "lib"

    # 1. Plugins: keep only the X11 platform and what it needs to draw and type.
    for folder in (qt / "plugins").iterdir():
        wanted = KEEP_PLUGINS.get(folder.name, set())
        if folder.name not in KEEP_PLUGINS:
            shutil.rmtree(folder)
        elif wanted is not None:
            for f in folder.iterdir():
                if f.name not in wanted:
                    f.unlink()

    # 2. Python modules and tools at the top of the package.
    for entry in pyside.iterdir():
        if entry.is_dir():
            if entry.name not in KEEP_TOP_DIRS:
                shutil.rmtree(entry)
            continue
        stem = entry.name.split(".")[0]
        is_module = stem.startswith("Qt") and entry.suffix in (".so", ".pyi")
        is_tool = entry.suffix == "" and not entry.name.startswith("_")
        if (is_module and stem not in KEEP_MODULES) or is_tool:
            entry.unlink()
    for folder in qt.iterdir():
        if folder.name not in ("lib", "plugins"):
            shutil.rmtree(folder)

    # 3. Qt libraries: keep the ones reachable from what is left.
    seeds = [p for p in pyside.glob("*.so*")] + list((qt / "plugins").rglob("*.so"))
    keep, queue = set(), list(seeds)
    while queue:
        for name in needed(queue.pop()):
            lib = libdir / name
            if name not in keep and lib.exists():
                keep.add(name)
                queue.append(lib)
    for lib in libdir.iterdir():
        if lib.is_dir():
            shutil.rmtree(lib)
        elif lib.name not in keep:
            lib.unlink()

    # 4. Things only a development install needs.
    for name in ("bin",):
        shutil.rmtree(root / name, ignore_errors=True)
    for extra in ("include", "typesystems", "glue", "doc", "scripts"):
        shutil.rmtree(root / "shiboken6" / extra, ignore_errors=True)
    for pyi in root.rglob("*.pyi"):
        pyi.unlink()
    for cache in list(root.rglob("__pycache__")):
        shutil.rmtree(cache)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
