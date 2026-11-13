# talk2me

A magnifying glass for your computer. Type `talk2me` in a terminal and get a one-screen summary of what your machine is doing: CPU, RAM, disk, battery, the apps using the most resources, network connections, and whether your last command worked.

```
╭────────────────────────── talk2me ───────────────────────────╮
│   Machine     Windows 11 · 8 cores / 8 threads · up 22h 40m  │
│   CPU         █░░░░░░░░░░░░░░░░░░░ 8%                        │
│   RAM         ███████████░░░░░░░░░ 57%  8.8 / 15.5 GB        │
│   Disk        ████░░░░░░░░░░░░░░░░ 20%  90 / 444 GB          │
│   Battery     ██████████░░░░░░░░░░ 54%  plugged in           │
│   Top apps    claude.exe  0.0% CPU · 8.7% RAM                │
│   Network     3 active connections                           │
│   Last cmd    ✓ notepad notes.txt  85s ago                   │
╰──────────────────────────────────────────────────────────────╯
```

## Commands

| Command | What it does |
|---|---|
| `talk2me` | One-screen overview of everything (default) |
| `talk2me watch` | The overview as a live dashboard (Ctrl+C to quit) |
| `talk2me last` | Your last command, whether it worked, and when |
| `talk2me why` | Plain-English guess at why your last command failed |
| `talk2me specs` | CPU, RAM, disk, OS, uptime |
| `talk2me hogs` | Top apps by CPU and RAM, grouped by name |
| `talk2me net` | Which programs are talking to the internet |
| `talk2me battery` | Charge level and time left |
| `talk2me lst` | List all commands |

Shortcuts: `wtf` = `why`, `live` = `watch`, `all` / `me` = overview.

## Quick setup (Windows PowerShell)

You need **Python 3** (`winget install Python.Python.3.12` if you don't have it).

```powershell
git clone https://github.com/j72664126-ui/talk2me.git
cd talk2me
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Then **close PowerShell, open a new window**, and type:

```powershell
talk2me
```

No git? Click **Code > Download ZIP** on the GitHub page, unzip it, open PowerShell in that folder, and run the installer line above.

The installer checks for Python, installs `psutil` and `rich`, and adds a `talk2me` command to your PowerShell profile. It is safe to run again; it replaces its own block instead of duplicating it. Don't move the folder afterwards, because the profile points at it. If you do, run the installer again from the new location.

### Manual setup

1. `python -m pip install -r requirements.txt`
2. Open your profile with `notepad $PROFILE` and paste the block between `# ---- talk2me ----` and `# ---- end talk2me ----` from `install.ps1`, replacing `__T2M_PATH__` with the full path to `talk2me.py`.
3. Open a new PowerShell window.

## How `last` and `why` work

A script can't see what your shell just ran, so the installer adds a small hook to your PowerShell profile. After every command it appends one line (time, exit code, command text) to `~\.talk2me_log` in your home folder. `talk2me last` and `talk2me why` read that file.

- The log stays on your computer. talk2me makes no network requests.
- It records commands typed in PowerShell only, not Command Prompt or other programs.
- `talk2me why` judges from the command and its exit code, so it gives likely causes, not certainties.
- Delete `~\.talk2me_log` any time to clear the history.

## Troubleshooting

- **"running scripts is disabled"**: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then open a new window.
- **"Python was not found"**: install Python, then **close and reopen PowerShell**. If a Microsoft Store window opens, turn off the python entries under Settings > "App execution aliases".
- **`talk2me` is not recognised**: open a new window, or run `. $PROFILE`. Check that the installer finished without errors.
- **`talk2me net` says access denied**: run PowerShell as Administrator.
- **Strange characters instead of bars and ticks**: use Windows Terminal.

## Uninstall

1. `notepad $PROFILE` and delete everything from `# ---- talk2me ----` to `# ---- end talk2me ----`.
2. Delete the talk2me folder and `~\.talk2me_log`.

## Adding your own command

Every command is a function with a decorator. Add this to `talk2me.py` and it appears in `talk2me lst` automatically:

```python
@command("hello", "Say hi")
def hello():
    console.print("Hi from talk2me!")
```

## Status

Built and tested on Windows 11 with Windows PowerShell 5.1. The core commands (`specs`, `hogs`, `net`, `battery`, `overview`, `watch`) are plain Python and may work on macOS and Linux, but the history hook (`last`, `why`) is PowerShell-only for now. Ports and fixes are welcome.

## Contributing

Issues and pull requests are welcome. Ideas: a bash/zsh hook, CPU temperature, recording the real error message for `why`, "did you mean" suggestions for mistyped commands.

## License

MIT. See [LICENSE](LICENSE).
