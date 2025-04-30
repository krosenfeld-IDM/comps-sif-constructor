# README

`create` the image:
```bash
uvx comps_sif_constructor create -d python.def -i python.sif
```
`launch` the experiment (e.g., trials / simulations):
```bash
uvx comps_sif_constructor launch --name python --file trials_.jsonl
```

Checkout the base docker image locally:
```bash
docker pull ghcr.io/astral-sh/uv:python3.12-bookworm-slim
```