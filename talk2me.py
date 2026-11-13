#!/usr/bin/env python3
"""talk2me - a magnifying glass for your computer.

Type `talk2me` in a terminal for a one-screen overview of your machine:
CPU, RAM, disk, battery, top apps, network, and your last command.
Run `talk2me lst` to see every command.

Requires: pip install psutil rich
"""
import os, platform, sys, time
from pathlib import Path
import psutil
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

__version__ = "1.0.0"

console = Console()
LOG = Path.home() / ".talk2me_log"          # written by the shell hook (see install.ps1)
COMMANDS = {}                                # name -> (function, description)
ALIASES = {"lst": "list", "ls": "list", "help": "list", "-h": "list", "--help": "list",
           "all": "overview", "me": "overview", "wtf": "why", "live": "watch"}

EXIT_CODES = {
    1: "PowerShell or the program reported an error (the exact message isn't recorded).",
    2: "File not found, or the program was used wrongly.",
    3: "Path not found.",
    5: "Access denied. Try running PowerShell as Administrator.",
    126: "Found, but it couldn't be run.",
    127: "Command not found.",
    130: "Stopped with Ctrl+C.",
    137: "Killed (often because it ran out of memory).",
    9009: "Windows couldn't find that program.",
    -1073741510: "Stopped with Ctrl+C.",
    -1073741819: "The program crashed (access violation).",
    -1073741515: "A required DLL file is missing.",
}
PATH_CMDS = {"ls", "dir", "gci", "get-childitem", "cd", "sl", "set-location", "cat", "type",
             "gc", "get-content", "copy", "cp", "move", "mv", "del", "rm", "remove-item",
             "notepad", "code", "start"}


def command(name, desc):
    """Register a function as a talk2me command."""
    def wrap(fn):
        COMMANDS[name] = (fn, desc)
        return fn
    return wrap


def _bar(pct, width=20):
    filled = int(pct / 100 * width)
    color = "green" if pct < 60 else "yellow" if pct < 85 else "red"
    return f"[{color}]{'█' * filled}[/][dim]{'░' * (width - filled)}[/] {pct:.0f}%"


def _last_entry():
    """Return (timestamp, exit code, command) of the last non-talk2me command, or None."""
    if not LOG.exists():
        return None
    lines = LOG.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    for line in reversed(lines):
        try: ts, code, cmd = line.split("|", 2)
        except ValueError: continue
        if cmd.strip().startswith("talk2me"):
            continue
        try: return int(ts), code, cmd.strip()
        except ValueError: continue
    return None


def _grouped_usage():
    """Return {app name: (cpu %, ram %)} grouped by process name."""
    me, cores = os.getpid(), psutil.cpu_count() or 1
    procs = list(psutil.process_iter(["name", "memory_percent"]))
    for p in procs:
        try: p.cpu_percent(None)             # prime the counter
        except psutil.Error: pass
    time.sleep(0.5)
    totals = {}
    for p in procs:
        try:
            name = p.info["name"]
            if p.pid in (0, me) or name == "System Idle Process":
                continue
            c, m = totals.get(name, (0, 0))
            totals[name] = (c + p.cpu_percent(None) / cores,
                            m + (p.info["memory_percent"] or 0))
        except psutil.Error: pass
    return totals


def _guess(cmd):
    """Best-guess causes for a failed command, judged from the command text alone."""
    import re, shlex, shutil, subprocess
    tips = []
    try:
        parts = shlex.split(cmd, posix=False)
    except ValueError:
        return ["There's an unbalanced quote in the command. Check your quotes."]
    if not parts:
        return tips
    first = parts[0].strip("\"'")

    # 1. Is the command itself something PowerShell knows?
    if not shutil.which(first):
        try:
            safe = first.replace("'", "''")
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"if (Get-Command '{safe}' -ErrorAction SilentlyContinue) {{ 'yes' }}"],
                capture_output=True, text=True, timeout=8)
            known = "yes" in r.stdout
        except Exception:
            known = True                       # can't tell, so don't guess
        if not known:
            tips.append(f"'{first}' isn't a command PowerShell recognises. It may be a typo, "
                        "or the program isn't installed or isn't on your PATH.")

    # 2. Do the file or folder arguments exist (from the current folder)?
    treat_all_as_paths = first.lower() in PATH_CMDS
    for arg in parts[1:]:
        shown = arg.strip("\"'")
        if not shown or shown.startswith("-"):
            continue
        looks_like_path = ("\\" in shown or "/" in shown
                           or re.search(r"\.[A-Za-z]\w{0,4}$", shown))
        if "@" in shown or "=" in shown:
            looks_like_path = False
        if not (treat_all_as_paths or looks_like_path):
            continue
        a = shown.replace("$HOME", str(Path.home())).replace("$env:USERPROFILE", str(Path.home()))
        a = os.path.expandvars(os.path.expanduser(a))
        if any(ch in a for ch in "$*?") or "://" in a:
            continue
        if not Path(a).exists():
            tips.append(f"'{shown}' doesn't exist from the current folder. Check the spelling, "
                        "or whether you were in a different folder when you ran it.")
    return tips[:3]


def _overview_panel():
    cores = psutil.cpu_count() or 1
    psutil.cpu_percent(None)
    totals = _grouped_usage()                # includes the 0.5s sampling pause
    cpu = psutil.cpu_percent(None)

    top = sorted(totals.items(), key=lambda r: r[1][0] + r[1][1], reverse=True)[:3]
    top_txt = "\n".join(f"{n}  [dim]{c:.1f}% CPU · {m:.1f}% RAM[/]" for n, (c, m) in top) \
        or "[dim]No applications detected[/]"

    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(Path.home().anchor or "/")
    up = time.time() - psutil.boot_time()

    b = psutil.sensors_battery()
    if b:
        state = "plugged in" if b.power_plugged else "on battery"
        left = ""
        if not b.power_plugged and b.secsleft not in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED):
            left = f" · {b.secsleft // 3600}h {b.secsleft % 3600 // 60}m left"
        battery_txt = f"{_bar(b.percent)}  [dim]{state}{left}[/]"
    else:
        battery_txt = "[dim]No battery[/]"

    try:
        n = sum(1 for c in psutil.net_connections(kind="inet") if c.status == "ESTABLISHED")
        net_txt = f"{n} active connections  [dim](talk2me net for details)[/]"
    except psutil.AccessDenied:
        net_txt = "[dim]Needs Administrator to read[/]"

    entry = _last_entry()
    if entry:
        ts, code, cmd = entry
        status = "[green]✓[/]" if code == "0" else f"[red]✗ exit {code}[/]"
        last_txt = f"{status} {escape(cmd)}  [dim]{int(time.time() - ts)}s ago[/]"
    else:
        last_txt = "[dim]No history yet[/]"

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("[cyan]Machine[/]", f"{platform.system()} {platform.release()} · "
              f"{psutil.cpu_count(logical=False)} cores / {cores} threads · up {up//3600:.0f}h {up%3600//60:.0f}m")
    t.add_row("[cyan]CPU[/]", _bar(cpu))
    t.add_row("[cyan]RAM[/]", f"{_bar(ram.percent)}  [dim]{ram.used/2**30:.1f} / {ram.total/2**30:.1f} GB[/]")
    t.add_row("[cyan]Disk[/]", f"{_bar(disk.percent)}  [dim]{disk.used/2**30:.0f} / {disk.total/2**30:.0f} GB[/]")
    t.add_row("[cyan]Battery[/]", battery_txt)
    t.add_row("[cyan]Top apps[/]", top_txt)
    t.add_row("[cyan]Network[/]", net_txt)
    t.add_row("[cyan]Last cmd[/]", last_txt)
    return Panel(t, title="talk2me", border_style="cyan")


@command("list", "Show all talk2me commands (aliases: lst, ls, help)")
def list_cmds():
    t = Table(title="talk2me commands")
    t.add_column("Command", style="cyan")
    t.add_column("What it does")
    for name, (_, desc) in sorted(COMMANDS.items()):
        t.add_row(f"talk2me {name}", desc)
    console.print(t)


@command("overview", "One-screen summary of everything (default)")
def overview():
    console.print(_overview_panel())


@command("watch", "Live overview that refreshes every second (Ctrl+C to quit)")
def watch():
    from rich.live import Live
    try:
        with Live(_overview_panel(), console=console, screen=True, auto_refresh=False) as live:
            while True:
                time.sleep(0.5)
                live.update(_overview_panel(), refresh=True)
    except KeyboardInterrupt:
        pass


@command("why", "Explain in plain English why your last command failed")
def why():
    entry = _last_entry()
    if not entry:
        console.print("[yellow]No history yet. Install the shell hook first.[/]")
        return
    ts, code, cmd = entry
    if code == "0":
        console.print(f"[green]✓ Your last command worked[/] (exit 0): [bold]{escape(cmd)}[/]\n"
                      "Nothing to explain.")
        return
    try:
        num = int(code)
        if num > 2**31:
            num -= 2**32
    except ValueError:
        num = None
    meaning = EXIT_CODES.get(num, "The program didn't give a specific reason.")
    tips = _guess(cmd)

    body = (f"[red]✗ failed[/] (exit {code})  [dim]{int(time.time() - ts)}s ago[/]\n"
            f"[bold]{escape(cmd)}[/]\n\n"
            f"[cyan]What the exit code says:[/] {meaning}")
    if tips:
        body += "\n\n[cyan]Likely causes:[/]\n" + "\n".join(f"  • {escape(t)}" for t in tips)
    else:
        body += ("\n\n[dim]Nothing obvious stands out from the command alone. "
                 "Run it again to see the full error message.[/]")
    console.print(Panel(body, title="talk2me why", border_style="red"))


@command("last", "Your last command, whether it worked, and when")
def last():
    entry = _last_entry()
    if not entry:
        console.print("[yellow]No history yet. Install the shell hook first.[/]")
        return
    ts, code, cmd = entry
    status = "[green]✓ worked[/]" if code == "0" else f"[red]✗ failed (exit {code})[/]"
    console.print(f"{status}  [bold]{escape(cmd)}[/]  [dim]{int(time.time() - ts)}s ago[/]")


@command("specs", "CPU, RAM, disk, OS, uptime")
def specs():
    t = Table(title="This machine", show_header=False)
    t.add_row("OS", f"{platform.system()} {platform.release()}")
    t.add_row("CPU", f"{platform.processor()} ({psutil.cpu_count(logical=False)} cores / {psutil.cpu_count()} threads)")
    ram = psutil.virtual_memory()
    t.add_row("RAM", f"{ram.used/2**30:.1f} / {ram.total/2**30:.1f} GB ({ram.percent}%)")
    disk = psutil.disk_usage(Path.home().anchor or "/")
    t.add_row("Disk", f"{disk.used/2**30:.0f} / {disk.total/2**30:.0f} GB ({disk.percent}%)")
    up = time.time() - psutil.boot_time()
    t.add_row("Uptime", f"{up//3600:.0f}h {up%3600//60:.0f}m")
    console.print(t)


@command("hogs", "Top apps by CPU and RAM (grouped by name)")
def hogs(n=8):
    totals = _grouped_usage()
    t = Table(title="Biggest resource users")
    t.add_column("App"); t.add_column("CPU %"); t.add_column("RAM %")
    for name, (cpu, mem) in sorted(totals.items(), key=lambda r: r[1][0] + r[1][1], reverse=True)[:n]:
        t.add_row(name, f"{cpu:.1f}", f"{mem:.1f}")
    console.print(t)


@command("net", "Which programs are talking to the internet")
def net():
    t = Table(title="Active internet connections")
    t.add_column("Program"); t.add_column("Remote address")
    try:
        conns = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        console.print("[yellow]Windows blocked this. Run PowerShell as Administrator.[/]")
        return
    seen = set()
    for c in conns:
        if c.status != "ESTABLISHED" or not c.raddr:
            continue
        try: name = psutil.Process(c.pid).name() if c.pid else "?"
        except psutil.Error: name = "?"
        key = (name, c.raddr.ip)
        if key in seen:
            continue
        seen.add(key)
        t.add_row(name, f"{c.raddr.ip}:{c.raddr.port}")
    console.print(t)


@command("battery", "Charge level, plugged in or not, time left")
def battery():
    b = psutil.sensors_battery()
    if b is None:
        console.print("[yellow]No battery found.[/]")
        return
    state = "plugged in" if b.power_plugged else "on battery"
    left = ""
    if not b.power_plugged and b.secsleft not in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED):
        left = f", {b.secsleft // 3600}h {b.secsleft % 3600 // 60}m left"
    console.print(f"[bold]{b.percent:.0f}%[/] {state}{left}")


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "overview"
    if name in ("-v", "--version", "version"):
        console.print(f"talk2me {__version__}")
        return
    name = ALIASES.get(name, name)
    if name not in COMMANDS:
        console.print(f"[red]Unknown command:[/] {name}\n")
        list_cmds()
        sys.exit(1)
    COMMANDS[name][0]()


if __name__ == "__main__":
    main()
