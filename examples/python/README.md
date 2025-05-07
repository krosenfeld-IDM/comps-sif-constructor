# README

`create` the image:
```bash
comps_sif_constructor create -d python.def
```
`launch` the experiment (e.g., trials / simulations):
```bash
comps_sif_constructor launch --name python --file trials_.jsonl
```
`gather` the results
```bash
comps_sif_constructor gather -
```

## Related

Checkout the base docker image locally:
```bash
docker pull ghcr.io/astral-sh/uv:python3.12-bookworm-slim
```