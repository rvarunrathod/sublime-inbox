# Inbox

Scratch notes in Sublime without naming or filing them. Search the pile later.

## Problem

Untitled tabs pile up. Save asks for a name and folder. Find in Files misses scraps that were never written to disk.

## Approach

One folder. Automatic names. Search over kept files and still-open untitled tabs.

Default path: `~/Notes/inbox`  
Name: `YYYY-MM-DD-HHMMSS` + first line, sanitized (time keeps create order).

## Out of scope (for now)

Draw/sketch, Obsidian-style vault, tags, daily notes, replace-in-search, VS Code widget clone.

## Phases

1. **Package shell** — settings, commands, keymap, load in Sublime.
2. **Park** — save current untitled tab to inbox, retarget so the tab keeps the buffer.
3. **Silent park** — park on tab switch / close if the buffer is non-empty.
4. **Harvest** — list untitled tabs: park or discard.
5. **Search** — Find in Files scoped to inbox + `<open files>`.
6. **MCP** — in-process localhost server so an AI can create/list/read notes.

## Settings

- `inbox_path` — `~/Notes/inbox` (settings or **Inbox: Set Path**)
- `inbox_extension` — `md`
- `silent_park` — `true` (park on tab switch / close)
- `search_layout` — `tab` | `sidebar` (later)

## Commands (planned)

- `Inbox: Park This`
- `Inbox: Open Inbox`
- `Inbox: Harvest`
- `Inbox: Search`
