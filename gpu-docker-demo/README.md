# gpu-docker-demo

Minimal, copy-pasteable example of a container that actually uses the GPU
on `selfservevgpu-1` — not just proving GPU passthrough works (that's
already confirmed via `nvidia-smi` and `docker run --gpus all nvidia/cuda:...
nvidia-smi`), but showing the pattern to adapt for your own workloads: a
PyTorch CNN trained on CIFAR10, with `train` and `infer` as two separate
modes of the same image.

`nvidia-container-toolkit` is a **host-level runtime hook**, not a
container itself — it's what lets `docker run --gpus all` hand a container
access to the host's GPU. It's already installed and configured on
`selfservevgpu-1`; nothing here needs to install it.

## Prerequisites

- A host with `nvidia-container-toolkit` installed and Docker's runtime
  configured for it (`nvidia-ctk runtime configure --runtime=docker`) —
  already true on `selfservevgpu-1`.
- Being in the `docker` group on that VM — no `sudo` needed for any
  command below. Already true for students on `selfservevgpu-1`.

## Two modes: train and infer

- `train`: trains a small CNN on CIFAR10 for 2 epochs, then saves the
  weights to `checkpoints/model.pth`.
- `infer`: loads `checkpoints/model.pth`, runs the model on 8 fixed images
  from the CIFAR10 **test** split (not train — inference should run on
  unseen data), and prints predicted vs. actual class labels plus accuracy
  over those 8 samples.

Each `docker run` gets a fresh, throwaway container filesystem — so
`infer` run without `train` having run first (and without the checkpoint
mount) will fail with a clear message telling you to run `train` first,
not a raw stack trace. This is deliberate: it demonstrates that a
container is stateless by default, and persisting anything across runs
(a checkpoint, a dataset) requires an explicit bind mount.

Two bind mounts are used for that reason:

- `./checkpoints:/app/checkpoints` — the trained weights.
- `./data:/app/data` — the CIFAR10 dataset. Without this, every `train`
  and `infer` run re-downloads ~170MB from the network, which gets old
  fast during a workshop.

## Build and run

Clone the repo if you don't already have it on the VM, then `cd` into this
folder:

```bash
[ -d lefolab-utils ] || git clone https://github.com/traitlab/lefolab-utils.git
cd lefolab-utils/gpu-docker-demo
```

Plain Docker:

```bash
docker build -t gpu-demo .
mkdir -p checkpoints data
docker run --rm --gpus all -v "$(pwd)/checkpoints:/app/checkpoints" -v "$(pwd)/data:/app/data" gpu-demo train
docker run --rm --gpus all -v "$(pwd)/checkpoints:/app/checkpoints" -v "$(pwd)/data:/app/data" gpu-demo infer
```

`docker run --gpus all gpu-demo` (no argument) defaults to `train` mode.

Compose equivalent:

```bash
docker compose run --rm gpu-demo train
docker compose run --rm gpu-demo infer
```

`docker compose up` alone would only ever run the default `train` command
— use `docker compose run --rm gpu-demo <mode>` to pick a mode explicitly.

`docker-compose.yml` uses `deploy.resources.reservations` for the GPU
reservation, which is normally a Swarm-only key but is honored by Compose
v2 (the `docker compose` CLI) for plain `docker compose up`/`run` too —
check `docker compose version` if this doesn't seem to work. If GPU
reservation via Compose doesn't work on your Compose version, fall back
to plain `docker run --gpus all`, which always works.

## Expected output

`train` prints whether CUDA is available, the GPU name, and per-epoch
batch loss, ending with:

```
Finished training
Saved checkpoint to checkpoints/model.pth
```

2 epochs on CIFAR10 on this vGPU slice takes roughly a few minutes —
if it's still running well past that, something's wrong rather than just
slow. *(Time this once for real on `selfservevgpu-1` and replace this
line with an actual figure.)*

`infer` prints one line per sample:

```
sample 0: predicted=cat actual=cat
...
accuracy on 8 samples: 7/8
```

Running `infer` before `train` (or without the checkpoint mount) prints:

```
No checkpoint found at checkpoints/model.pth. Run the container in 'train' mode first: docker run --gpus all gpu-demo train
```

## Adapting this for your own project

Copy this folder, then swap in your own code:

- Replace `train.py` / `infer.py` / `model.py` / `requirements.txt` with
  your own model and dependencies.
- Keep the `FROM nvidia/cuda:...` base (or switch to a framework-specific
  image like `pytorch/pytorch:...-cuda...-runtime` if that's simpler for
  your case).
- Keep the checkpoint-mount pattern — anything that needs to survive
  between container runs must be bind-mounted, not left in the container
  filesystem.

**Do not reuse this demo's `./checkpoints` / `./data` bind-mount pattern
for real, larger-scale work.** This demo's dataset is small and throwaway;
real projects with larger datasets/checkpoints should use
`/mnt/ceph/rpp-elalib-lab/selfserve/<username>/` or `/mnt/app`, per the
broader access model below — not a bind mount next to your Dockerfile.

## Base image / version pinning

**Don't hardcode a CUDA image tag without checking it matches the host
driver's supported version.** Before picking a tag:

1. Check the driver's max supported CUDA API version: `nvidia-smi` →
   header line `CUDA Version: X.Y`.
2. Verify a matching tag is actually published, e.g.:
   `curl -s "https://hub.docker.com/v2/repositories/nvidia/cuda/tags?page_size=100&name=<ubuntu-tag>" | jq -r '.results[].name'`
   (or browse https://hub.docker.com/r/nvidia/cuda/tags).
3. Pick a tag at or below the driver's supported version — a newer CUDA
   runtime than the driver supports fails at runtime, not at build/pull
   time.

This demo pins `nvidia/cuda:13.0.3-runtime-ubuntu24.04`, matching the
driver on `selfservevgpu-1` (CUDA 13.0) as of this writing. Re-verify if
the driver is ever upgraded. The `-runtime` variant (not `-devel`) is used
because `torch`'s pip wheel ships prebuilt CUDA binaries and doesn't
compile anything locally — `nvcc`/build headers aren't needed here.

If `pip3 install torch` ever resolves a CPU-only or mismatched-CUDA wheel,
pin an explicit `+cuXXX` build matching this image's CUDA version instead
of relying on the default resolution.

## Where this runs

`selfservevgpu-1`, via `tf-rpp-elalib/selfserve-vgpu-connect.sh <username>`.
See `docs/selfserve_vgpu_plan.md` in that repo for the broader access model
(Ceph mounts, sudo-as-superuser, exposing a running app on your assigned
port range, etc.) — this README only covers the GPU-in-Docker pattern, not
the surrounding VM access model.

## Out of scope

- Multi-GPU / distributed training — `selfservevgpu-1` has exactly one
  vGPU slice.
- Any persistence beyond the two bind mounts (`checkpoints/`, `data/`)
  this demo needs. Real projects have a much larger persistence need and
  should use the Ceph/`/mnt/app` mounts mentioned above, not this pattern.
