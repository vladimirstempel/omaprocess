# OmaProcess

See what is running on your Omarchy desktop by program, not by PID, and end
the one that misbehaves. A bar icon opens a panel listing your programs with
their real names and icons, "Chromium", "Zed", "Steam", instead of `chromium`
times forty-seven. Expand a program to see its processes, and terminate either
the whole program or a single process, always after a confirmation.

## What it shows

- **Applications**: everything you launched, grouped by the systemd scope
  Omarchy starts each app in. One row per program with process count, memory
  and CPU.
- **System**: your session services (PipeWire, portals, Hyprland, …), collapsed
  by default. You can end them too, with an extra warning.
- Only your own processes. Nothing owned by root or other users is listed or
  touched.

Names and icons come from the program's window (Hyprland) and its `.desktop`
entry, falling back to the process name.

## Terminating

1. Press the terminate button on a row (or `x`) and confirm. The default
   choice is Cancel, so a stray Enter ends nothing.
2. A program is stopped through `systemctl --user stop`, a single process gets
   `SIGTERM`, so it has a chance to save and exit cleanly.
3. If it is still there after a few seconds, the row says "Not responding"
   and offers **Force kill** (`SIGKILL`), behind another confirmation.

The shell itself (`omarchy-shell` / Quickshell) is never offered for
termination: ending it would take the panel and the bar with it.

## Requirements

- Omarchy 4 (the Quickshell `omarchy-shell`, plugin schema 1)
- Python 3, which Omarchy already installs

## Install

```bash
omarchy plugin add https://github.com/vladimirstempel/omaprocess.git --enable --yes
```

Optional keybinding in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + CTRL + P", "Processes", "omarchy-shell omaprocess toggle")
```

## Keys

| Key | Action |
|---|---|
| type | filter by program name, process name or PID |
| `↓` / `j`, `↑` / `k` | move |
| `Enter`, `Space`, `l` / `h` | expand / collapse |
| `x` | terminate the selected program or process |
| `/` | back to the search field |
| `Esc` | clear the search, then close |

## Settings

In the Omarchy bar settings for the widget:

- **Panel width**, in the shell's spacing units (default 460)
- **Refresh interval**, seconds between updates while the panel is open
  (default 2). Nothing is polled while it is closed.

## From a terminal

Everything the panel does goes through `bin/omaprocess`, which also works on
its own:

```bash
bin/omaprocess list | jq '.apps[] | {name, count, rss}'
bin/omaprocess stop <unit>     # end a program
bin/omaprocess term <pid>      # end one process
bin/omaprocess kill <pid>      # force kill one process
```

## License

MIT
