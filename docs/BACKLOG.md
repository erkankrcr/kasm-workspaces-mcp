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
