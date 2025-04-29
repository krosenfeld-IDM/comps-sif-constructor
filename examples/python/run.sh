#!bin/bash
export PATH="$PWD/workspace/.venv/bin:$PATH"
echo "Running cowsay"
uv run python remote.py
test $? -eq 0 || { echo "Simulation failed"; exit -1; }
echo "done"