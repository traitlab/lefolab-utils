# Plan: minimal GPU-in-Docker demo for selfservevgpu-1

## Purpose

`selfservevgpu-1` (lab, `tf-rpp-elalib`) now has a working vGPU driver,
CUDA toolkit, and `nvidia-container-toolkit` (confirmed via `nvidia-smi` and
`docker run --gpus all nvidia/cuda:... nvidia-smi`). Students landing on
that VM need a **minimal, copy-pasteable example** showing how to write a
container that actually uses the GPU - not just prove passthrough works,
but show the pattern they'd adapt for their own workloads. This plan
describes that example; the actual code/Dockerfile should be implemented
directly in this repo folder (`lefolab-utils/gpu-docker-demo/`).

## Where this lives

New folder in `lefolab-utils`, following this repo's existing convention
(one folder per tool/topic, README inside explaining it):

```
lefolab-utils/gpu-docker-demo/
├── README.md            - what it is, how to build/run both modes, expected output
├── Dockerfile
├── .dockerignore         - excludes checkpoints/, data/, __pycache__ from the build context
├── .gitignore            - excludes checkpoints/, data/ from being committed
├── entrypoint.sh         - dispatches to train.py or infer.py based on the CLI arg
├── requirements.txt      (or inline pip install in Dockerfile - see below)
├── train.py              - training mode (adapted from tf-rpp-elalib's test-cudnn.py)
├── infer.py              - inference mode: loads train.py's checkpoint, runs predictions
└── docker-compose.yml    - compose alternative, showing the GPU reservation stanza
```

`.dockerignore` matters less here since the shown Dockerfile only `COPY`s
specific files (no `COPY .`), but add it anyway as a one-liner
(`checkpoints/`, `data/`, `__pycache__/`) - cheap insurance if someone later
changes the Dockerfile to `COPY . .`. `.gitignore` matters more: without it,
someone testing locally can easily `git add -A` a `model.pth` or the
downloaded CIFAR10 data into the repo by accident.

## Prerequisites the README should state up front

- Must run on a host with `nvidia-container-toolkit` installed and Docker's
  runtime configured for it (`nvidia-ctk runtime configure --runtime=docker`)
  - already true on `selfservevgpu-1`, not something students need to set up
    themselves.
- Students are already in the `docker` group on that VM (see
  `tf-rpp-elalib`'s `cloud-config-setup-docker.tft`) - no `sudo` needed for
  any of the commands below.

## Base image and version pinning - the one thing to get right

**Do not hardcode a CUDA image tag without checking it actually exists and
matches the host driver's supported version first.** This bit us already
once on the infra side (a guessed `nvidia/cuda:12.4.1-base-ubuntu24.04` tag
turned out to never have been published). Before picking a tag:

1. Check the driver's max supported CUDA API version on the actual host:
   `nvidia-smi` → header line `CUDA Version: X.Y`.
2. Verify a matching tag is actually published:
   `curl -s "https://hub.docker.com/v2/repositories/nvidia/cuda/tags?page_size=100&name=<ubuntu-tag>" | jq -r '.results[].name'`
   (or just browse https://hub.docker.com/r/nvidia/cuda/tags).
3. Pick a tag at or below that driver version - a newer CUDA runtime than
   the host driver supports fails at runtime, not at build/pull time, which
   is a confusing failure mode for students to debug.

As of this VM's current state: driver reports CUDA 13.0, and
`nvidia/cuda:13.0.3-*-ubuntu24.04` tags are confirmed to exist and already
verified working on this exact VM (see `tf-rpp-elalib`'s
`cloud-config-setup-nvidia-container-toolkit.tft`). Start from there; re-verify
if the driver ever gets upgraded.

Use the `-runtime-` variant, not `-devel-`: `torch`'s pip wheel ships
prebuilt CUDA binaries and does not compile anything against a local CUDA
install at build time, so `nvcc`/build headers (what `-devel` adds over
`-runtime`) buy nothing here and just make the image bigger for no reason.
`-devel` would only be justified if this demo actually compiled a custom
CUDA kernel itself - it doesn't. Example: `nvidia/cuda:13.0.3-runtime-ubuntu24.04`
(verify this specific tag is published the same way as above before using it).

## Two modes: train and infer

Rather than a throwaway boolean check, reuse the CIFAR10 CNN training
script that's already deployed and verified working on `selfservevgpu-1`
itself - `tf-rpp-elalib`'s `modules/selfserve-vgpu/cloud-config-setup-cuda-toolkit.tft`
writes this exact script to `/root/tests/cudnn/test-cudnn.py` on the VM.
Copy that code as the basis for `train.py` here (same `Net` class,
CIFAR10 dataset, training loop over 2 epochs) with one addition: save the
trained weights at the end so a *second*, separate container run can load
them back for inference. That gap between the two runs is the whole point
- it demonstrates that a container is disposable/stateless by default and
you have to deliberately persist a checkpoint across runs, which is a real
lesson for anyone about to run their own training jobs this way.

- **`train.py`**: existing CIFAR10/CNN training code, plus at the end:
  ```python
  import os
  os.makedirs("checkpoints", exist_ok=True)
  torch.save(net.state_dict(), "checkpoints/model.pth")
  print("Saved checkpoint to checkpoints/model.pth")
  ```
- **`infer.py`**: a new, small script -
  1. Re-declare the same `Net` class (or factor it into a shared
     `model.py` both scripts import, cleaner than duplicating the class).
  2. `net.load_state_dict(torch.load("checkpoints/model.pth"))`,
     `net.eval()`, move to `device`.
  3. Load a **fixed, small set of indices** (e.g. the first 8 images) from
     the CIFAR10 **test** split (not train - makes the point that inference
     should run on unseen data), not a random sample - deterministic output
     means every student sees the same predictions for the same checkpoint,
     which matters for a teaching demo (comparing results, debugging
     together, etc.). Run a forward pass, print predicted vs. actual class
     labels for each, plus accuracy over that small batch.
  4. Fail with a clear error message (not a stack trace) if
     `checkpoints/model.pth` doesn't exist yet - i.e. tell the user to run
     `train` mode first, rather than a raw `FileNotFoundError`.
- **`entrypoint.sh`**: dispatches on the first argument:
  ```bash
  #!/bin/bash
  set -e
  case "$1" in
    train) exec python3 train.py ;;
    infer) exec python3 infer.py ;;
    *) echo "Usage: docker run --gpus all gpu-demo [train|infer]"; exit 1 ;;
  esac
  ```

The checkpoint has to survive between the two separate `docker run`
invocations (each container's own filesystem is thrown away when it exits),
so `checkpoints/` needs a bind mount to a host directory - see the Dockerfile
and compose sections below. This is also worth calling out explicitly in the
README as the "why did my second run fail" answer if someone forgets the
mount.

**Separately, decide deliberately what happens to the CIFAR10 dataset
download.** `torchvision.datasets.CIFAR10(download=True)` fetches ~170MB on
first use; without its own persistent mount, that download re-happens on
every single `train` (and `infer`, since it also loads the test split)
run, hitting the network every time during a workshop. Mount a second
`./data:/app/data` bind volume alongside `./checkpoints:/app/checkpoints`
(and point both scripts' `root=` argument at `data/` instead of the
default `./data` relative path, which is the same thing but explicit) so
the dataset downloads once and is reused. This is a deliberate choice to
make, not leave implicit - the plan is calling it out so whoever implements
this adds the second mount rather than discovering the repeated-download
behavior by accident mid-workshop.

## Dockerfile shape

```dockerfile
FROM nvidia/cuda:13.0.3-runtime-ubuntu24.04

RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY train.py infer.py entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["train"]
```

`CMD ["train"]` as the default means a bare `docker run --gpus all gpu-demo`
(no arg) trains first, which is the natural order for a first-time run;
`docker run --gpus all gpu-demo infer` overrides it.

`requirements.txt`: `torch` **and `torchvision`** - both `train.py` and
`infer.py` depend on `torchvision` for the CIFAR10 dataset and transforms,
not just `torch`. pip pulls the CUDA-enabled wheels automatically when a
matching CUDA runtime is present in the base image - no need to pin a
`+cuXXX` build explicitly unless the default resolution picks the wrong
one; note this as a "if it fails, pin explicitly" caveat in the README
rather than pre-solving it, since the correct pin depends on whatever CUDA
version this image ends up using.

## docker-compose.yml shape

Show the GPU reservation stanza, since that's the pattern used elsewhere in
the fleet (e.g. `stac-fastapi-pgstac`'s compose file) and is what students
will need once they have more than one service:

```yaml
services:
  gpu-demo:
    build: .
    volumes:
      - ./checkpoints:/app/checkpoints
      - ./data:/app/data
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

Bind-mount `./checkpoints` and `./data` (plain host directories next to the
compose file), not named volumes, for this demo specifically - the point is
for the student to actually *see* `model.pth` and the downloaded CIFAR10
files appear on disk between runs, which named volumes hide away under
Docker's data-root. Run each mode by overriding the command:
```
docker compose run --rm gpu-demo train
docker compose run --rm gpu-demo infer
```
(`docker compose up` alone would only ever run the default `CMD`.)

Note in the README: `deploy.resources.reservations` is normally a Swarm-only
key, but Compose v2 (the `docker compose` CLI, not legacy `docker-compose`)
honors it for plain `docker compose up` too - confirm this still holds for
whatever Compose version ships on the VM (`docker compose version`), since
this is a common point of confusion/breakage across Compose versions. If it
doesn't work, fall back to `docker run --gpus all` (which always works
regardless of Compose version) and say so plainly rather than debugging
Compose GPU quirks in a beginner-facing demo.

## README.md should include

1. One-paragraph explanation of what `nvidia-container-toolkit` actually
   does (host-level runtime hook, not a container itself - this specific
   confusion already came up once when explaining this to a user, worth
   heading off).
2. Build + run commands for both modes, in order (infer depends on a
   checkpoint that only exists after train has run once):
   ```
   docker build -t gpu-demo .
   mkdir -p checkpoints data
   docker run --rm --gpus all -v "$(pwd)/checkpoints:/app/checkpoints" -v "$(pwd)/data:/app/data" gpu-demo train
   docker run --rm --gpus all -v "$(pwd)/checkpoints:/app/checkpoints" -v "$(pwd)/data:/app/data" gpu-demo infer
   ```
   and the compose equivalent:
   ```
   docker compose run --rm gpu-demo train
   docker compose run --rm gpu-demo infer
   ```
3. Expected output: `train` prints the GPU name, CUDA availability, and the
   per-epoch loss printouts from the existing CIFAR10 loop, ending with
   "Saved checkpoint to checkpoints/model.pth"; `infer` prints predicted vs.
   actual labels for a handful of test images plus the small-batch accuracy.
4. What happens if you run `infer` before `train` (clear "run train first"
   message, not a stack trace - see the `infer.py` spec above) - worth
   showing deliberately so students recognize the error if they hit it.
5. A short "adapt this for your own project" pointer: copy this folder,
   swap `train.py`/`infer.py`/`requirements.txt` for your own model/code,
   keep the `FROM nvidia/cuda:...` line (or switch to a framework-specific
   base image like `pytorch/pytorch:...-cuda...-runtime` if that's simpler
   for your case) and the checkpoint-mount pattern.
6. Link back to where this runs: `selfservevgpu-1` via
   `tf-rpp-elalib/selfserve-vgpu-connect.sh <username>`, and
   `docs/selfserve_vgpu_plan.md` in that repo for the broader access model
   (Ceph mounts, sudo-as-superuser, port range for exposing a running app,
   etc.) - this demo folder should not duplicate that context, just point
   to it.
7. Expected runtime for `train` (2 epochs on CIFAR10, on this vGPU slice) -
   whoever implements this should actually time it once and put a real
   number/range in the README, so students don't wonder if it's hung
   partway through. A rough guess isn't good enough here since it's the
   kind of detail that's cheap to verify and expensive to get wrong.

## Out of scope for this plan

- Multi-GPU / distributed training patterns - this VM has exactly one
  vGPU slice, not relevant here.
- Anything beyond the two bind mounts (`checkpoints/`, `data/`) this demo
  actually needs. Real student projects have a much larger persistence need
  (their actual datasets/checkpoints), which should go on
  `/mnt/ceph/rpp-elalib-lab/selfserve/<username>/` or `/mnt/app` per the
  infra repo's plan, not a bind mount next to their Dockerfile - mention
  this distinction in the README so students don't copy the demo's
  small-scale bind-mount pattern verbatim for real, larger-scale work.
