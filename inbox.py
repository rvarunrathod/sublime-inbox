import os

import sublime
import sublime_plugin

from .inbox_fs import park_path as fs_park_path


def plugin_loaded():
    print("Inbox: loaded")
    from . import inbox_mcp
    inbox_mcp.start()


def plugin_unloaded():
    from . import inbox_mcp
    inbox_mcp.stop()


def inbox_settings():
    return sublime.load_settings("Inbox.sublime-settings")


def inbox_path():
    return os.path.expanduser(inbox_settings().get("inbox_path", "~/Notes/inbox"))


def _is_note_view(view):
    if view is None or view.settings().get("is_widget"):
        return False
    if hasattr(view, "element") and view.element() is not None:
        return False
    return True


def _park_path(text):
    ext = inbox_settings().get("inbox_extension", "md")
    return fs_park_path(inbox_path(), ext, text)


def _is_inbox_file(path):
    if not path:
        return False
    folder = os.path.abspath(inbox_path())
    try:
        return os.path.commonpath([os.path.abspath(path), folder]) == folder
    except ValueError:
        return False


def _view_text(view):
    return view.substr(sublime.Region(0, view.size()))


def untitled_note_views(window):
    views = []
    for view in window.views():
        if _is_note_view(view) and not view.file_name() and not view.is_scratch():
            views.append(view)
    return views


def discard_view(view):
    if view is None or not view.is_valid():
        return
    view.settings().set("inbox_discard", True)
    view.set_scratch(True)
    view.close()


def park_view(view):
    if not _is_note_view(view) or view.is_scratch() or view.file_name():
        return None
    if view.settings().get("inbox_discard"):
        return None
    text = _view_text(view)
    if not text.strip():
        return None
    path = _park_path(text)
    view.retarget(path)
    view.run_command("save")
    return path


def flush_inbox_view(view):
    path = park_view(view)
    if path:
        return path
    if (
        _is_note_view(view)
        and view.file_name()
        and view.is_dirty()
        and _is_inbox_file(view.file_name())
    ):
        view.run_command("save")
        return view.file_name()
    return None


def create_inbox_note(content="", title=""):
    window = sublime.active_window()
    if window is None:
        return None
    body = content or ""
    if title and title not in body[: len(title) + 1]:
        body = title + ("\n\n" + body if body else "")
    view = window.new_file()
    if body:
        view.run_command("append", {"characters": body})
    return park_view(view)


def _abs_inbox_in_folders(folders, abs_path):
    return any(
        os.path.abspath(os.path.expanduser(f.get("path", ""))) == abs_path
        for f in folders
    )


class InboxOpenCommand(sublime_plugin.WindowCommand):
    def run(self):
        path = inbox_path()
        os.makedirs(path, exist_ok=True)
        abs_path = os.path.abspath(path)
        data = self.window.project_data() or {}
        folders = list(data.get("folders") or [])
        if not _abs_inbox_in_folders(folders, abs_path):
            folders.append({"path": path})
            data["folders"] = folders
            self.window.set_project_data(data)
            self.window.set_sidebar_visible(True)
            sublime.status_message("Inbox: " + path)
            return
        visible = self.window.is_sidebar_visible()
        self.window.set_sidebar_visible(not visible)
        sublime.status_message("Inbox: hidden" if visible else "Inbox: " + path)


class InboxSetPathCommand(sublime_plugin.WindowCommand):
    def run(self):
        sublime.select_folder_dialog(self._picked, inbox_path())

    def _picked(self, path):
        if not path:
            return
        settings = inbox_settings()
        settings.set("inbox_path", path)
        sublime.save_settings("Inbox.sublime-settings")
        sublime.status_message("Inbox: " + path)


class InboxParkThisCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return _is_note_view(self.view) and self.view.file_name() is None

    def run(self, edit):
        view = self.view
        path = park_view(view)
        if path:
            sublime.status_message("Inbox: " + path)
            return
        if view.file_name():
            sublime.status_message("Inbox: already a file")
        else:
            sublime.status_message("Inbox: empty, nothing to park")


class InboxSilentParkListener(sublime_plugin.EventListener):
    def on_deactivated(self, view):
        if inbox_settings().get("silent_park", True):
            flush_inbox_view(view)

    def on_pre_close(self, view):
        if inbox_settings().get("silent_park", True):
            flush_inbox_view(view)

    def on_pre_close_window(self, window):
        if not inbox_settings().get("silent_park", True):
            return
        for view in window.views():
            flush_inbox_view(view)


def _harvest_preview(view):
    text = _view_text(view).strip()
    if not text:
        return "(empty)"
    return text.splitlines()[0][:80]


class InboxHarvestCommand(sublime_plugin.WindowCommand):
    def is_enabled(self):
        return bool(untitled_note_views(self.window))

    def run(self):
        views = untitled_note_views(self.window)
        if not views:
            sublime.status_message("Inbox: nothing to harvest")
            return
        nonempty = [v for v in views if _view_text(v).strip()]
        empty = [v for v in views if not _view_text(v).strip()]
        items = []
        self._actions = []
        if nonempty:
            items.append("Park all ({})".format(len(nonempty)))
            self._actions.append(("park_all", None))
        if empty:
            items.append("Discard empty ({})".format(len(empty)))
            self._actions.append(("discard_empty", None))
        for view in views:
            items.append(_harvest_preview(view))
            self._actions.append(("one", view.id()))
        self.window.show_quick_panel(items, self._picked)

    def _picked(self, index):
        if index < 0:
            return
        kind, vid = self._actions[index]
        if kind == "park_all":
            n = 0
            for view in untitled_note_views(self.window):
                if park_view(view):
                    n += 1
            sublime.status_message("Inbox: parked {}".format(n))
            return
        if kind == "discard_empty":
            n = 0
            for view in untitled_note_views(self.window):
                if not _view_text(view).strip():
                    discard_view(view)
                    n += 1
            sublime.status_message("Inbox: discarded {}".format(n))
            return
        view = None
        for candidate in self.window.views():
            if candidate.id() == vid:
                view = candidate
                break
        if view is None or not view.is_valid():
            return
        if not _view_text(view).strip():
            discard_view(view)
            sublime.set_timeout(self.run, 30)
            return
        self._pending = view
        self.window.show_quick_panel(["Park", "Discard"], self._one_picked)

    def _one_picked(self, index):
        view = getattr(self, "_pending", None)
        self._pending = None
        if index < 0 or view is None or not view.is_valid():
            return
        if index == 0:
            park_view(view)
        else:
            discard_view(view)
        sublime.set_timeout(self.run, 30)


class InboxNewNoteCommand(sublime_plugin.WindowCommand):
    def run(self, content="", title=""):
        path = create_inbox_note(content, title)
        sublime.status_message("Inbox: " + (path or "empty"))


class InboxSearchCommand(sublime_plugin.WindowCommand):
    def run(self):
        path = inbox_path()
        os.makedirs(path, exist_ok=True)
        self.window.run_command("show_panel", {
            "panel": "find_in_files",
            "where": "{},<open files>".format(path),
        })
        view = self.window.active_view()
        if view and view.sel() and not view.sel()[0].empty():
            self.window.run_command("slurp_find_string")
