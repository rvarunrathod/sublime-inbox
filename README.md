# Inbox

Scratch notes in Sublime Text 4. No name, no folder picker. Search later.

Works on **macOS, Linux, and Windows**. Requires Sublime Text 4.

## Problem

Sublime is a good place to dump thoughts: new tab, type, leave it. After a while you have dozens of untitled tabs.

You do not save them because you do not know if the note will matter later, what to call the file, or which folder it belongs in. Closing a tab feels like throwing the thought away. Sublime’s session keeps unsaved buffers around, so the pile just grows.

Find in Files also misses scraps that were never written to disk (unless you remember to add `<open files>`). So the thing you like — search — does not see everything you wrote.

Inbox is that missing step: one folder, automatic names, park or harvest instead of Save As. Search works because the notes are real files.

## Install

Repo: [rvarunrathod/sublime-inbox](https://github.com/rvarunrathod/sublime-inbox). Install folder name is `sublime-inbox`.

### Package Control

1. Command Palette → **Package Control: Add Repository**
2. Paste `https://github.com/rvarunrathod/sublime-inbox`
3. **Package Control: Install Package** → **sublime-inbox**
4. Restart Sublime

### Manual

Clone or unzip as a folder named `sublime-inbox`:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Sublime Text/Packages/sublime-inbox` |
| Linux | `~/.config/sublime-text/Packages/sublime-inbox` |
| Windows | `%APPDATA%\Sublime Text\Packages\sublime-inbox` |

`Preferences → Browse Packages…` opens that folder. Restart Sublime.

## Use

| Command | Linux / Windows | macOS |
|---|---|---|
| Open / hide inbox sidebar | Ctrl+Alt+I | Cmd+Option+I |
| Park this untitled tab | Ctrl+Alt+K | Cmd+Option+K |
| Harvest untitled tabs | Ctrl+Alt+H | Cmd+Option+H |
| Search inbox + open tabs | Ctrl+Alt+F | Cmd+Option+F |

**Preferences → Package Settings → Inbox**, or **Inbox: Set Path**.  
Default folder: `~/Notes/inbox`.  
Names: `YYYY-MM-DD-HHMMSS-first-line.md` (local time).

Silent park (on by default) saves untitled notes when you switch tab or close.

## AI (MCP)

Starts with Sublime. Nothing on `PATH`. Nothing to configure in Inbox.

URL: `http://127.0.0.1:8766/mcp` (also printed in the Sublime console)

**grok-cli**

```bash
# Sublime must be running
grok mcp add inbox http://127.0.0.1:8766/mcp
grok mcp doctor inbox
```

**Other clients**

```json
{
  "mcpServers": {
    "inbox": {
      "type": "http",
      "url": "http://127.0.0.1:8766/mcp"
    }
  }
}
```

Tools: `new_note`, `list_notes`, `read_note`. Same on macOS, Linux, and Windows.
