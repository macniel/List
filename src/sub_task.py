# MIT License

# Copyright (c) 2023 Vlad Krupinski <mrvladus@yandex.ru>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# from gettext import gettext as _
from gi.repository import Gtk, Adw, GObject, Gdk, Gio
from .utils import Log, UserData, Markup


@Gtk.Template(resource_path="/io/github/mrvladus/List/sub_task.ui")
class SubTask(Gtk.Revealer):
    __gtype_name__ = "SubTask"

    sub_task_box_rev = Gtk.Template.Child()
    sub_task_text = Gtk.Template.Child()
    sub_task_completed_btn = Gtk.Template.Child()
    sub_task_edit_box_rev = Gtk.Template.Child()
    sub_task_edit_entry = Gtk.Template.Child()

    def __init__(self, task: dict, parent: Gtk.Box, window: Adw.ApplicationWindow):
        super().__init__()
        Log.info("Add sub-task: " + task["text"])
        self.parent = parent
        self.task = task
        self.window = window
        # Escape text and find URL's'
        self.text = Markup.escape(self.task["text"])
        self.text = Markup.find_url(self.text)
        # Check if sub-task completed and toggle checkbox
        self.sub_task_completed_btn.props.active = self.task["completed"]
        # Set text
        self.sub_task_text.props.label = self.text
        self.add_actions()

    def add_actions(self):
        group = Gio.SimpleActionGroup.new()
        self.insert_action_group("sub_task", group)

        def add_action(name: str, callback):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            group.add_action(action)

        add_action("delete", self.delete)
        add_action("edit", self.edit)
        add_action("copy", self.copy)

    def copy(self, *_) -> None:
        Log.info("Copy to clipboard: " + self.task["text"])
        clp: Gdk.Clipboard = Gdk.Display.get_default().get_clipboard()
        clp.set(self.task["text"])
        self.window.add_toast(self.window.toast_copied)

    def delete(self, *_, update_sts: bool = True) -> None:
        Log.info(f"Delete sub-task: {self.task['text']}")
        self.toggle_visibility()
        new_data: dict = UserData.get()
        new_data["history"].append(self.task["id"])
        UserData.set(new_data)
        # Don't update if called externally
        if update_sts:
            self.parent.update_statusbar()
        self.window.trash_add(self.task)

    def edit(self, *_) -> None:
        self.toggle_edit_box()
        # Set entry text and select it
        self.sub_task_edit_entry.get_buffer().props.text = self.task["text"]
        self.sub_task_edit_entry.select_region(0, len(self.task["text"]))
        self.sub_task_edit_entry.grab_focus()

    def toggle_edit_box(self) -> None:
        self.sub_task_box_rev.set_reveal_child(
            not self.sub_task_box_rev.get_child_revealed()
        )
        self.sub_task_edit_box_rev.set_reveal_child(
            not self.sub_task_edit_box_rev.get_child_revealed()
        )

    def toggle_visibility(self) -> None:
        self.set_reveal_child(not self.get_child_revealed())

    def update_data(self) -> None:
        new_data: dict = UserData.get()
        for task in new_data["tasks"]:
            if task["id"] == self.parent.task["id"]:
                for i, sub in enumerate(task["sub"]):
                    if sub["id"] == self.task["id"]:
                        task["sub"][i] = self.task
                        UserData.set(new_data)
                        # Update parent data
                        self.parent.task["sub"] = task["sub"]
                        return

    # --- Template handlers --- #

    @Gtk.Template.Callback()
    def on_drag_begin(self, _source, drag) -> bool:
        self.add_css_class("dim-label")
        widget = Gtk.Button(
            label=self.task["text"]
            if len(self.task["text"]) < 20
            else f"{self.task['text'][0:20]}..."
        )
        icon = Gtk.DragIcon.get_for_drag(drag)
        icon.set_child(widget)

    @Gtk.Template.Callback()
    def on_drag_cancel(self, *_) -> bool:
        self.remove_css_class("dim-label")
        return True

    @Gtk.Template.Callback()
    def on_drag_end(self, *_) -> bool:
        self.remove_css_class("dim-label")
        return True

    @Gtk.Template.Callback()
    def on_drag_prepare(self, _source, _x, _y) -> Gdk.ContentProvider:
        value = GObject.Value(SubTask)
        value.set_object(self)
        return Gdk.ContentProvider.new_for_value(value)

    @Gtk.Template.Callback()
    def on_drop(self, _drop, sub_task, _x, _y) -> None:
        if sub_task == self:
            return
        if sub_task.parent != self.parent:
            # Remove sub-task
            sub_task.parent.task["sub"].remove(sub_task.task)
            sub_task.parent.sub_tasks.remove(sub_task)
            sub_task.parent.update_data()
            sub_task.parent.update_statusbar()
            # Insert new sub-task
            self.parent.task["sub"].insert(
                self.parent.task["sub"].index(self.task), sub_task.task.copy()
            )
            self.parent.update_data()
            self.parent.update_statusbar()
            new_sub_task = SubTask(sub_task.task.copy(), self.parent, self.window)
            self.parent.sub_tasks.insert_child_after(
                new_sub_task,
                self,
            )
            self.parent.sub_tasks.reorder_child_after(self, new_sub_task)
            new_sub_task.toggle_visibility()
        else:
            # Get indexes
            self_idx = self.parent.task["sub"].index(self.task)
            sub_idx = self.parent.task["sub"].index(sub_task.task)
            # Move widget
            self.parent.sub_tasks.reorder_child_after(sub_task, self)
            self.parent.sub_tasks.reorder_child_after(self, sub_task)
            # Update data
            self.parent.task["sub"].insert(
                self_idx, self.parent.task["sub"].pop(sub_idx)
            )
            self.parent.update_data()

    @Gtk.Template.Callback()
    def on_completed_btn_toggled(self, btn: Gtk.Button) -> None:
        self.task["completed"] = btn.props.active
        self.update_data()
        self.parent.update_statusbar()
        # Set crosslined text
        if self.task["completed"]:
            self.text = Markup.add_crossline(self.text)
        else:
            self.text = Markup.rm_crossline(self.text)
        self.sub_task_text.props.label = self.text

    @Gtk.Template.Callback()
    def on_sub_task_cancel_edit_btn_clicked(self, *_) -> None:
        self.toggle_edit_box()

    @Gtk.Template.Callback()
    def on_sub_task_edit(self, entry: Gtk.Entry) -> None:
        old_text: str = self.task["text"]
        new_text: str = entry.get_buffer().props.text
        # Return if text the same or empty
        if new_text == old_text or new_text == "":
            return
        Log.info(f"Change sub-task: '{old_text}' to '{new_text}'")
        self.task["text"] = new_text
        self.task["completed"] = False
        self.update_data()
        self.parent.update_statusbar()
        # Escape text and find URL's'
        self.text = Markup.escape(self.task["text"])
        self.text = Markup.find_url(self.text)
        # Check if text crosslined and toggle checkbox
        self.sub_task_completed_btn.props.active = False
        # Set text
        self.sub_task_text.props.label = self.text
        self.toggle_edit_box()
