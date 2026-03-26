# rpi-monitoring

## Deployment on Raspberry Pi

This repository is prepared for deployment through a GitHub Actions `self-hosted` runner running on the Raspberry Pi itself.

### What the workflow does

On every push to `main` or `master`:

1. Checks out the repository on the self-hosted runner.
2. Copies the project into a dedicated deployment directory.
3. Creates or updates a Python virtual environment in that directory.
4. Installs packages from `requirements.txt`.
5. Installs or updates a `systemd` service.
6. Enables the service at boot and restarts it.

### Files

- `.github/workflows/deploy.yml` runs the deployment job.
- `scripts/deploy.sh` performs deployment on the Raspberry Pi.
- `deploy/rpi-monitoring.service` is the `systemd` unit template.

### Required prerequisites on the Raspberry Pi

The deploy script automatically installs missing OS packages required for the virtual environment and native Python builds:

- `python3`
- `python3-venv`
- `python3-pip`
- `python3-dev`
- `build-essential`
- `swig`
- `liblgpio-dev` or `lgpio` depending on the Raspberry Pi OS package name

If you prefer to prepare the device manually, the equivalent command is:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev build-essential swig liblgpio-dev
```

The runner user must be able to run `sudo` without interactive password prompts because deployment may install OS packages, write into `/etc/systemd/system`, and restart services.

If the application needs access to SPI/GPIO, make sure the service user is in the required groups, for example:

```bash
sudo usermod -aG spi,gpio pi
```

Re-login after changing group membership.

For newer Raspberry Pi models and newer Raspberry Pi OS releases, the project uses `rpi-lgpio` instead of `RPi.GPIO` because `RPi.GPIO` may fail with errors like `Cannot determine SOC peripheral base address`.

### Workflow configuration

Default deployment settings:

- `SERVICE_NAME=rpi-monitoring.service`
- `PYTHON_BIN=python3`
- `DEPLOY_DIR=$HOME/apps/rpi-monitoring` if not explicitly set
- `SERVICE_USER=$USER` if not explicitly set

If your deployment should use another directory or another Unix user, define `DEPLOY_DIR` and `SERVICE_USER` in `.github/workflows/deploy.yml`.

### First-time setup

1. Create and register the GitHub self-hosted runner on the Raspberry Pi.
2. Make sure the runner user has the required `sudo` permissions.
3. Update `.github/workflows/deploy.yml` if you want a different deploy path or service user.
4. Push to `main` or `master`, or run the workflow manually via `workflow_dispatch`.

### Useful commands on the Raspberry Pi

```bash
sudo systemctl status rpi-monitoring.service
sudo journalctl -u rpi-monitoring.service -f
```
