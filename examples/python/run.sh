#!bin/bash
export PATH="$PWD/workspace/.venv/bin:$PATH"
echo "Running cowsay"
pwd
uv pip list
which python
uv run python -c "import cowsay; cowsay.cow('Welcome to python')"
test $? -eq 0 || { echo "Simulation failed"; exit -1; }
echo "done"