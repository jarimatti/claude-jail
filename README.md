# Claude Jail

A safer Claude Code setup: a devcontainer for **rootless Podman** whose only way out is an allowlist proxy.

## Use as a Copier template

Generate the jail into a project (needs [Copier](https://copier.readthedocs.io/), e.g. via `uvx`; `mise install` in this repo provides `uv` and Node.js):

    uvx copier copy gh:jarimatti/claude-jail path/to/project     # or a local path to this repo
    uvx copier update                                         # later, inside the project, to pull template changes

The template also adds a `mise.toml` (Node.js, for `npx`) if the project has none; an existing one is never overwritten.

Questions: `project_name` and `extra_domains` (additional HTTPS hosts for the allowlist, e.g. `.pypi.org`). Answers are stored in `.copier-answers.yml`; commit it, because `copier update` reads it to re-render with your answers and merge template changes. The template lives in `template/`.

## Quick start

Requires rootless Podman, `podman-compose` (`podman compose` is a wrapper around it, so the commands below are interchangeable) and Node.js (on the host, for `npx`; `mise install` provides it from the `mise.toml` the template adds). From the generated project:

    npx @devcontainers/cli up   --docker-path podman --docker-compose-path podman-compose --workspace-folder .
    npx @devcontainers/cli exec --docker-path podman --docker-compose-path podman-compose --workspace-folder . bash
    claude                      # inside the jail; log in on first run

The first `up` pulls a large image and installs Claude Code, so expect a few minutes. Your project is mounted at `/workspace`. To stop: `podman compose -f .devcontainer/docker-compose.yml down` (add `-v` to also delete the login volume and so log out). Re-running `up` starts it again.

## How it works

    host ── egress (normal network) ── [proxy: squid] ── jail (--internal network) ── [jail: Claude Code]

Both containers are services of one compose project (`.devcontainer/docker-compose.yml`), so every project gets its own proxy, networks and login volume, and they start and stop together.

- The jail sits on an `--internal` Podman network. It has no route to anything, including the host, the LAN and raw IPs.
- The only reachable thing is the squid proxy, which tunnels HTTPS (port 443) to the hosts in `.devcontainer/proxy/allowed-domains.txt`. It filters by hostname on every request, so CDN IP changes don't matter. Plain HTTP is denied.
- The jail is a stock `mcr.microsoft.com/devcontainers/base:trixie` image (Debian 13, no Dockerfile, no features) with Claude Code installed by `postCreateCommand` using the native installer (`curl -fsSL https://claude.ai/install.sh | bash`). Node.js is not installed in the jail. It runs with `cap_drop: ALL` and `no-new-privileges` (so the image's sudo is inert) and needs no network capabilities, because nothing inside the container configures a firewall.
- Claude is logged in with your claude.ai subscription **inside** the jail (accepted trade-off): the OAuth token lives in the `~/.claude` volume. The proxy limits where a compromised jail could send it, but it can't keep the token out of the jail.

## Use

CLI: see Quick start. `up` starts the proxy and the jail via compose.

VS Code: set `"dev.containers.dockerPath": "podman"` in user settings (from a WSL window it may need to go in the Remote [WSL] scope), then "Reopen in Container".

## Changing the allowlist

Edit `.devcontainer/proxy/allowed-domains.txt` (or change `extra_domains` with `copier update`), then restart the proxy: `podman compose -f .devcontainer/docker-compose.yml restart proxy`. `podman compose -f .devcontainer/docker-compose.yml logs proxy` shows denied requests.

## Notes

- Tools must honor `HTTPS_PROXY` (Claude Code, git over https, curl do). `ssh` does not, so use https remotes.
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` is set, which stops telemetry/update checks (and so auto-updates). To update Claude Code, rebuild the container (`postCreateCommand` installs the latest release; the version is not pinned).
- The jail can still write to the workspace and read the Claude token; the network is the boundary, not the filesystem. The one exception is `.devcontainer/`, which is mounted read-only inside the jail so it can't rewrite its own allowlist. Likewise `.git/hooks` is read-only, since hooks would run on the host at the next git command; this means the project must be a git repo (with a plain `.git` directory) or the jail won't start. `.git/config` is still writable (aliases, `core.hooksPath`, `core.fsmonitor` can run commands on the host), so treat the repo as untrusted after a session.

## Verified

Rebuilt from scratch from a rendered template with `podman-compose` 1.3.0 and Podman 5.4: the devcontainer builds and starts, the native installer works through the proxy, `claude` runs inside the jail, and the `~/.claude` volume is writable by `vscode`. Isolation checks: allowlisted HTTPS works; other hosts, plain HTTP and direct IP access (bypassing the proxy) fail; the jail has no capabilities and is attached only to the internal network.

The jail maps your host user to `vscode` (`userns_mode: keep-id`, which is why the compose file sets `x-podman: in_pod: false`), so `/workspace` is writable and owned by you. Checked on the full stack: files created in the jail are owned by your host uid, `.devcontainer` and `.git/hooks` are read-only, and the `~/.claude` volume is writable.

## Not verified

- The login persists across rebuilds.
- Claude **login** (OAuth) inside the jail. Token exchange should be covered by `.anthropic.com`/`.claude.com`/`.claude.ai`; if it fails, check the proxy logs for denied hosts.
- The VS Code GUI flow, including extension install through the proxy.
- Behavior of `git push`/`gh` beyond reaching GitHub.
