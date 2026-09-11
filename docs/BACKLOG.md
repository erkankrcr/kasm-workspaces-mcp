# Backlog

Features that exist in the code but aren't ready to be presented as
supported/working. Tracked here instead of silently shipping something
that only works by accident in one environment.

## `execute_kasm_command_ssh` (`KASM_SSH_ENABLED`) — Work In Progress

**Status: backlog, not a supported feature yet.** Don't rely on this
without re-reading this section for your own deployment.

Reaching a Kasm session container over SSH has **two independent
requirements**, both of which have to hold at once:

1. **Network reachability from wherever this MCP server runs to the
   container's IP.** Kasm's session containers sit on the agent host's
   own Docker bridge network (typically `172.x.x.x`), which is **not**
   routable from other machines — confirmed live 2026-09-11: being on
   the same LAN as the Kasm agent host was *not* enough (TCP connects to
   the container IP timed out from a peer LAN machine); only *from
   inside the agent host itself* was the container reachable, and only
   on the port KasmVNC actually listens on (**6901** in the instance
   tested — not 22, not 443, both of which are refused).

   `KASM_SSH_HOST_OVERRIDE` doesn't solve this by itself — it only
   changes *which host* `ssh_exec` targets, not whether that host's
   Docker network is reachable from where this MCP server process runs.
   The one setup where reachability holds: this MCP server runs *on the
   Kasm agent host itself*, or on a machine with an SSH-based tunnel /
   port-forward into that host set up *outside* this project (e.g. an
   `ssh -L`/jump-host config the operator maintains themselves — this
   project has no built-in support for establishing that tunnel).

2. **The workspace image itself must run an SSH daemon.** Confirmed
   live: stock `kasmweb/*` images (Chromium, Postman, Ubuntu Noble, the
   `kasmweb/kali-rolling-desktop` image registered during this same
   testing session) do **not** run sshd — only port 6901 (KasmVNC) is
   open inside the container. `execute_kasm_command_ssh` will simply
   fail to connect against any of these, network reachability aside.
   It only has a chance of working against a **custom image you build
   yourself with sshd installed and started**.

**Why this is backlog, not "done":** requirement 1 happened to be
satisfiable in the environment this was tested against (operator has
SSH access to their own Kasm agent host — a multi-server install where
that host also happens to be reachable). That is environment-specific
good fortune, not something this project sets up or verifies. A
single-server Kasm install, a different network topology, or simply not
having SSH credentials to the agent host would all break requirement 1
even before requirement 2 (a stock image with no sshd) comes into play.
Shipping this as a normal opt-in flag without that caveat would mislead
most users into thinking it "just works" once `KASM_SSH_ENABLED=true`
and a key are set.

**Even "SSH into the agent host" isn't one fix — it's per-agent, and
some agents are deliberately unreachable from each other.** This
project's multi-server test deployment has separate agent hosts for
different zones (e.g. a `kasm-server` host on `10.0.20.x` and a
`kasm-dmz` host on `10.0.50.x`). Confirmed live 2026-09-11: from inside
the `kasm-server` host (reached over SSH), `ping` and `ssh` to the
`kasm-dmz` host's IP both hit a hard timeout (100% packet loss, no
route) — a deliberate DMZ network boundary, not a missing daemon. So
even an operator with SSH access to *one* agent host cannot assume that
gets them reachability to sessions running on a *different* agent —
each agent needs its own verified network path, and some (by design)
have none from the others. Any future fix here has to be scoped
per-agent-host, not treated as a single yes/no capability.

**Root privilege is not the blocker, and neither is reverse SSH — both
confirmed live 2026-09-11 with dedicated experiments:**

- *"Could we install/run an SSH-like listener without root?"* Yes in
  principle (run `sshd`/`dropbear` as a non-root user on a port >1024
  with self-owned host keys and `authorized_keys`, or bring a static
  no-dependency binary if `openssh-server` isn't installed at all — no
  package manager or root needed for either). But this doesn't help:
  dispatched a plain `python3 -m http.server 8899` as the default
  (non-root) user via `exec_command_kasm` — zero install, zero
  privilege — and a *direct* connection attempt from this MCP server's
  host straight to `container_ip:8899` (bypassing the agent entirely)
  still timed out identically to every other port tried. The blocker is
  the network path, full stop; the service running inside is irrelevant.

- *"Could the container connect back to us instead (reverse SSH)?"*
  Tested directly: started a plain TCP listener on this MCP server's
  own host, then dispatched an outbound probe from inside the container
  (`... > /dev/tcp/<this-host-LAN-IP>/19999`, no root, no install) via
  `exec_command_kasm`. Result: **no connection ever arrived** — the
  container's outbound path doesn't reach this host either. Most likely
  a deliberate firewall rule (containers get outbound *internet* access
  for the desktop apps, but not access back into the operator's LAN) —
  consistent with wanting pentest/Kali sandboxes isolated from the home
  network, not a bug. Net effect: reverse SSH is blocked in the same
  direction as forward SSH, for a different (also intentional-looking)
  reason.

So there are two fully independent barriers, not one: (a) service
availability inside the container (solvable without root) and (b)
network reachability to/from the container (not solvable from outside
the agent host at all, in either direction, in this deployment). Only
the "run inside/tunnel through the agent host" approach above touches
barrier (b); nothing this project can dispatch *into* the container
changes it.

**Before promoting this out of backlog**, it needs at least one of:
- A documented, tested reference setup (e.g. "run this MCP server on
  the agent host" or "here's the exact SSH tunnel command to run
  first") that a new user can actually follow, not just "same-network"
  hand-waving.
- Or a built-in tunnel/jump-host mechanism (this project would open the
  SSH connection *through* an operator-supplied jump host itself,
  rather than assuming direct reachability) — not implemented.
- A clearly documented "you must build your own sshd-enabled image"
  requirement surfaced *before* someone enables the flag, not
  discovered by trial and error.
