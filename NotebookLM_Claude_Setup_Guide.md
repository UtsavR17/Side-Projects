# Claude × NotebookLM MCP Integration — Windows Setup Guide

A step-by-step guide to connecting Claude Desktop to Google NotebookLM using MCP (Model Context Protocol) on Windows.

---

## What You Are Setting Up

Since Google has no official API for personal NotebookLM accounts, this integration uses a community-built bridge tool (`notebooklm-mcp-cli`) that:
- Automates your browser in the background using your saved Google session
- Exposes NotebookLM as a set of tools Claude Desktop can call
- Lets you query notebooks, add sources, and trigger outputs (Audio Overviews, etc.) directly from Claude

---

## Prerequisites

- Windows 10 or 11
- Claude Desktop app installed ([download here](https://claude.ai/download))
- Google Chrome (or Edge/Brave) installed
- A Google account with NotebookLM access ([notebooklm.google.com](https://notebooklm.google.com))
- PowerShell (comes with Windows — search "PowerShell" in Start Menu)

---

## Step 1 — Install `uv` (Python Package Manager)

Open **PowerShell** and paste the following:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

When it finishes, you will see:
```
everything's installed!
```

Then add `uv` to your PATH for the current session:

```powershell
$env:Path = "C:\Users\YOUR_USERNAME\.local\bin;$env:Path"
```

> ⚠️ Replace `YOUR_USERNAME` with your actual Windows username (e.g. `NIRVA`).  
> You will need to run this PATH line every time you open a new PowerShell window.

---

## Step 2 — Install the NotebookLM MCP Package

In the same PowerShell window, run:

```powershell
uv tool install notebooklm-mcp-cli
```

Wait for it to finish. You will see a list of installed packages and at the end:
```
Installed 2 executables: nlm, notebooklm-mcp
```

---

## Step 3 — Authenticate with Google

> ⚠️ **Before running this step: fully close your browser** — right-click its taskbar icon and choose Quit/Close all windows. The tool needs to launch Chrome itself.

Run:

```powershell
nlm login
```

A Chrome window will open automatically. Log in with your Google account. Wait until PowerShell shows:

```
✓ Successfully authenticated!
  Account: yourname@gmail.com
  Credentials saved to: C:\Users\YOUR_USERNAME\.notebooklm-mcp-cli\profiles\default
```

Your session cookies are now saved locally. They typically last several weeks before needing a refresh.

---

## Step 4 — Configure Claude Desktop

Open the Claude Desktop config file in Notepad:

```powershell
notepad "$env:APPDATA\Claude\claude_desktop_config.json"
```

You will see the existing contents. Add the `mcpServers` block so the file looks like this (keep your existing `preferences` section, just add the new part):

```json
{
  "preferences": {
    "coworkScheduledTasksEnabled": false,
    "sidebarMode": "chat",
    "coworkWebSearchEnabled": true,
    "ccdScheduledTasksEnabled": false
  },
  "mcpServers": {
    "notebooklm-mcp": {
      "command": "C:\\Users\\YOUR_USERNAME\\.local\\bin\\notebooklm-mcp"
    }
  }
}
```

> ⚠️ Replace `YOUR_USERNAME` with your actual Windows username.  
> Use double backslashes `\\` in the path — this is required for JSON on Windows.

Save the file with **Ctrl+S**, then close Notepad.

---

## Step 5 — Restart Claude Desktop

1. Find the Claude icon in the **system tray** (bottom-right corner of taskbar — click the `^` arrow if hidden)
2. Right-click it → **Quit**
3. Reopen Claude Desktop from the Start Menu or desktop shortcut

---

## Step 6 — Verify the Connection

Once Claude Desktop has restarted, click the **+** button in the chat input area, then go to **Connectors**. You should see `notebooklm-mcp` listed there.

To test it, type in Claude Desktop:

```
List all my NotebookLM notebooks
```

Claude will call the MCP server in the background and return your notebook list.

---

## Daily Usage — Refreshing Your PATH

Every time you open a new PowerShell window and want to use `nlm` commands, run:

```powershell
$env:Path = "C:\Users\YOUR_USERNAME\.local\bin;$env:Path"
```

Or to make this permanent (so you never need to do it again), run this once:

```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Users\YOUR_USERNAME\.local\bin", "User")
```

Then restart PowerShell.

---

## Re-authenticating When Cookies Expire

If Claude starts failing to reach NotebookLM (usually after a few weeks), just re-run:

```powershell
nlm login
```

This refreshes your session without changing any other settings.

---

## Switching to a Different Google Account

### Option A — Replace the Default Account

This overwrites your current login with a new Google account:

```powershell
nlm login
```

Simply log in with the new account when Chrome opens. The old credentials will be replaced.

---

### Option B — Use Named Profiles (Keep Multiple Accounts)

You can maintain separate profiles for different Google accounts.

**Create a new profile:**

```powershell
nlm login --profile work
```

```powershell
nlm login --profile personal
```

Each profile stores its own cookies independently.

**List all profiles:**

```powershell
nlm login profile list
```

**Switch the active (default) profile:**

```powershell
nlm login switch work
```

```powershell
nlm login switch personal
```

After switching, Claude Desktop will use whichever profile is set as default. You do not need to restart Claude Desktop when switching profiles.

**Delete a profile you no longer need:**

```powershell
nlm login profile delete work
```

---

## Useful Commands Reference

```powershell
# Check if you are authenticated
nlm login --check

# List all your NotebookLM notebooks
nlm notebook list

# Create a new notebook
nlm notebook create "My Research"

# Add a URL source to a notebook
nlm source add <notebook-id> --url "https://example.com/article"

# Add a local PDF as a source
nlm source add <notebook-id> --file "C:\path\to\file.pdf"

# Generate an Audio Overview
nlm audio create <notebook-id> --confirm

# Run diagnostics if something is not working
nlm doctor
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `nlm` not recognized | Run `$env:Path = "C:\Users\YOUR_USERNAME\.local\bin;$env:Path"` |
| Login fails / Chrome won't open | Fully quit your browser before running `nlm login` |
| NotebookLM not showing in Claude Desktop | Make sure the full path is in the config and Claude was fully restarted |
| Auth errors after a few weeks | Run `nlm login` again to refresh cookies |
| Something else broken | Run `nlm doctor` for a full diagnostic |

---

*Guide based on `notebooklm-mcp-cli` by jacob-bd — [GitHub Repository](https://github.com/jacob-bd/notebooklm-mcp-cli)*
