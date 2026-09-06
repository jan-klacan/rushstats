# Running rushstats in Docker

Docker is optional. A Python wheel is smaller and starts faster; choose Docker when
you already use containers or want an isolated command without a host Python/Rust
installation. No server, Compose stack, exposed port or persistent service is needed.

## Build

Start Docker Desktop (macOS/Windows) or the Docker daemon (Linux), then run:

```sh
docker build -t rushstats:0.2.0 .
docker run --rm rushstats:0.2.0 --version
docker run --rm rushstats:0.2.0 --help
```

The multi-stage build compiles the extension with Rust, then installs only the wheel
into a Python 3.13 slim runtime. Rust, Cargo, compilers, source datasets and Git
history are not included in the final image. Base images use versioned tags; tags
can receive updates, so byte-identical rebuilds are not promised. BuildKit records
the resolved image digests. The image builds natively for Linux AMD64 and ARM64
when the corresponding builder is used; each architecture must be tested separately.

No prebuilt container image is currently published by this project. These commands
use the image you build locally. The Docker wheel targets its own runtime's glibc;
portable PyPI Linux wheels are built separately using manylinux2014.

## Analyze a mounted dataset

On macOS/Linux, run from the directory containing your CSV:

```sh
docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$(pwd),target=/data" \
  rushstats:0.2.0 customers.csv --all --group-by city -o report.md
```

`/data` is the container's working directory. The report appears in the mounted host
directory. Matching your host UID/GID avoids unexpected report ownership on Linux.
By default, the image runs as UID/GID 10001, not root. When overriding the user, avoid
UID 0 if you want to keep that property.

PowerShell with Docker Desktop can use:

```powershell
docker run --rm --network none `
  --mount "type=bind,source=$($PWD.Path),target=/data" `
  rushstats:0.2.0 customers.csv --all -o report.md
```

If the mounted output directory denies writes to the container's user, adjust the
host directory permissions or select an appropriate `--user`; rushstats does not
change host permissions. Existing reports still require `--force` to replace.

## Separate input and output

The runtime needs no network. A read-only root filesystem and a read-only input
mount work; only the destination directory must be writable. Temporary report files
are created beside the output, so no writable system temporary directory is needed.
Create the output directory on the host first:

```sh
mkdir -p reports
docker run --rm --network none --read-only \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$(pwd)/examples,target=/input,readonly" \
  --mount "type=bind,source=$(pwd)/reports,target=/output" \
  rushstats:0.2.0 /input/customers.csv --all -o /output/report.md
```

Only mount data you intend the command to read/write. `--max-bytes` and
`--max-groups` are application limits; Docker's `--memory` option can impose a
separate process-memory limit, though reaching it may terminate the container.

## Verification

```sh
python scripts/smoke_container.py --image rushstats:0.2.0
```

This checks the non-root default separately, then checks offline/read-only-root
operation, report generation, overwrite refusal and missing-file errors using a
temporary synthetic dataset. On POSIX hosts the mounted-file checks use the host
UID/GID: atomic report files have owner-only permissions (0600), so native Linux
requires matching ownership for the host process to read them. The
same script runs in CI. It does not upload the image or data anywhere.
