#!/bin/bash

# 1. (Re)install your package in editable or normal mode:
# pip install -e .

# 2. List all entry‐points in a particular group, e.g. "idmtools_task":
python3 - << 'EOF'
import importlib.metadata as m

# grab all EPs under "idmtools_task"
eps = m.entry_points().select(group="idmtools_experiment")
for ep in eps:
    print(f"{ep.name} -> {ep.value}")