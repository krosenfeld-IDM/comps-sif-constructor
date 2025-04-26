#!/usr/bin/env python3
"""
Vendoring script: download and extract wheels for idmtools, idmtools_platform_comps,
idmtools_models, and pycomps into src/ so they can be packaged via discovery.
Usage:
    python vendor_packages.py
"""
import io
import zipfile
import urllib.request
from pathlib import Path

# package name to wheel URL map
packages = {
    "idmtools": "https://packages.idmod.org/api/pypi/pypi-production/idmtools/1.7.10/idmtools-1.7.10-py3-none-any.whl",
    "idmtools_platform_comps": "https://packages.idmod.org:443/artifactory/idm-pypi-production/idmtools-platform-comps/1.7.10/idmtools_platform_comps-1.7.10-py3-none-any.whl",
    "idmtools_models": "https://packages.idmod.org:443/artifactory/idm-pypi-production/idmtools-models/1.7.10/idmtools_models-1.7.10-py3-none-any.whl",
    "COMPS": "https://packages.idmod.org:443/artifactory/idm-pypi-production/pyCOMPS/2.11.0/pyCOMPS-2.11.0-py2.py3-none-any.whl",
}

dest_root = Path(__file__).parent / "src"
# ensure destination exists
(dest_root).mkdir(parents=True, exist_ok=True)

for name, url in packages.items():
    print(f"Vendoring {name}...")
    data = urllib.request.urlopen(url).read()
    with io.BytesIO(data) as buf:
        with zipfile.ZipFile(buf) as z:
            for member in z.namelist():
                print(f"Extracting {member}...")
                if not member.startswith(name + "/"):
                    continue
                target = dest_root / member
                if member.endswith('/'):
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with open(target, 'wb') as f:
                        f.write(z.read(member))
print("Vendoring complete.")
