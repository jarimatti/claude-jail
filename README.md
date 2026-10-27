# Claude Jail

A safer Claude Code setup: a devcontainer for **rootless Podman** whose only way out is an allowlist proxy.

## Quick start

Requires rootless Podman and Node.js (on the host, for `npx`). From this directory:

    npx @devcontainers/cli up   --docker-path podman --workspace-folder .
    npx @devcontainers/cli exec --docker-path podman --workspace-folder . bash
    claude                      # inside the jail; log in on first run

The first `up` pulls a large image and installs Claude Code, so expect a few minutes. Your project is mounted at `/workspace`. To stop: `podman stop $(podman ps -q --filter label=devcontainer.local_folder)`. Re-running `up` starts it again.

## How it works

    host ── claude-jail-egress (normal network) ── [claude-jail-proxy: squid] ── claude-jail-net (--internal) ── [jail: Claude Code]

- The jail sits on an `--internal` Podman network. It has no route to anything, including the host, the LAN and raw IPs.
- The only reachable thing is the squid proxy, which tunnels HTTPS (port 443) to the hosts in `.devcontainer/proxy/allowed-domains.txt`. It filters by hostname on every request, so CDN IP changes don't matter. Plain HTTP is denied.
- The jail is a stock `mcr.microsoft.com/devcontainers/base:trixie` image (Debian 13, no Dockerfile, no features) with Claude Code installed by `postCreateCommand` using the native installer (`curl -fsSL https://claude.ai/install.sh | bash`). Node.js is not installed in the jail. It runs with `--cap-drop=ALL` and `no-new-privileges` (so the image's sudo is inert) and needs no network capabilities, because nothing inside the container configures a firewall.
- Claude is logged in with your claude.ai subscription **inside** the jail (accepted trade-off): the OAuth token lives in the `~/.claude` volume. The proxy limits where a compromised jail could send it, but it can't keep the token out of the jail.

## Use

CLI: see Quick start. `up` runs `.devcontainer/proxy/up.sh` on the host (the `initializeCommand`), which creates the two networks and (re)starts the proxy.

VS Code: set `"dev.containers.dockerPath": "podman"` in user settings (from a WSL window it may need to go in the Remote [WSL] scope), then "Reopen in Container".

## Changing the allowlist

Edit `.devcontainer/proxy/allowed-domains.txt` and run `bash .devcontainer/proxy/up.sh` (or rebuild the devcontainer). The proxy is recreated and picks it up. `podman logs claude-jail-proxy` shows denied requests.

## Notes

- Tools must honor `HTTPS_PROXY` (Claude Code, git over https, curl do). `ssh` does not, so use https remotes.
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` is set, which stops telemetry/update checks (and so auto-updates). To update Claude Code, rebuild the container (`postCreateCommand` installs the latest release; the version is not pinned).
- The first build pulls a large base image; give it a few minutes.
- The jail can still write to the workspace and read the Claude token; the network is the boundary, not the filesystem.
- Cleanup: `podman rm -f claude-jail-proxy; podman network rm claude-jail-net claude-jail-egress`.

## Verified

Rebuilt from scratch on the `base:trixie` image: the devcontainer builds and starts, the native installer works through the proxy, and `claude` runs inside the jail.

## Not verified

- The `vscode` user (UID 1000) can write to the `~/.claude` volume, and the login persists across rebuilds.
- Claude **login** (OAuth) inside the jail. Token exchange should be covered by `.anthropic.com`/`.claude.com`/`.claude.ai`; if it fails, check `podman logs claude-jail-proxy` for denied hosts.
- The VS Code GUI flow, including extension install through the proxy.
- Behavior of `git push`/`gh` beyond reaching GitHub. `npm` is no longer in the jail, so `registry.npmjs.org` in the allowlist is only needed if you install Node yourself.
