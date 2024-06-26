import sys
from tkinter import LEFT, Button, Frame, Label, Text, Tk
from typing import Any, Callable

from tktooltip import ToolTip

from tkinter_form import Form

from .auxiliary import FormDict, RedirectText, dataclass_to_dict, dict_to_dataclass, recursive_set_focus
from .Mininterface import Cancelled, ConfigInstance, Mininterface


class GuiInterface(Mininterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.window = TkWindow(self)
        self._always_shown = False
        self._original_stdout = sys.stdout

    def __enter__(self) -> "Mininterface":
        """ When used in the with statement, the GUI window does not vanish between dialogues. """
        self._always_shown = True
        sys.stdout = RedirectText(self.window.text_widget, self.window.pending_buffer, self.window)
        return self

    def __exit__(self, *_):
        self._always_shown = False
        sys.stdout = self._original_stdout
        if self.window.pending_buffer:  # display text sent to the window but not displayed
            print("".join(self.window.pending_buffer), end="")

    def alert(self, text: str) -> None:
        """ Display the OK dialog with text. """
        return self.window.buttons(text, [("Ok", None)])

    def ask(self, text: str) -> str:
        return self.window.run_dialog({text: ""})[text]

    def ask_args(self) -> ConfigInstance:
        """ Display a window form with all parameters. """
        params_ = dataclass_to_dict(self.args, self.descriptions)

        # fetch the dict of dicts values from the form back to the namespace of the dataclasses
        data = self.window.run_dialog(params_)
        dict_to_dataclass(self.args, data)
        return self.args

    def ask_form(self, args: FormDict, title: str = "") -> dict:
        """ Prompt the user to fill up whole form.
            :param args: Dict of `{labels: default value}`. The form widget infers from the default value type.
                The dict can be nested, it can contain a subgroup.
                The default value might be `mininterface.Value` that allows you to add descriptions.
                A checkbox example: {"my label": Value(True, "my description")}
            :param title: Optional form title.
        """
        return self.window.run_dialog(args, title=title)

    def ask_number(self, text: str) -> int:
        return self.window.run_dialog({text: 0})[text]

    def is_yes(self, text):
        return self.window.yes_no(text, False)

    def is_no(self, text):
        return self.window.yes_no(text, True)


class TkWindow(Tk):
    """ An editing window. """

    def __init__(self, interface: GuiInterface):
        super().__init__()
        self.params = None
        self._result = None
        self._event_bindings = {}
        self.interface = interface
        self.title(interface.title)
        self.bind('<Escape>', lambda _: self._ok(Cancelled))

        self.frame = Frame(self)
        """ dialog frame """

        self.text_widget = Text(self, wrap='word', height=20, width=80)
        self.text_widget.pack_forget()
        self.pending_buffer = []
        """ Text that has been written to the text widget but might not be yet seen by user. Because no mainloop was invoked. """

    def run_dialog(self, form: FormDict, title: str = "") -> dict:
        """ Let the user edit the form_dict values in a GUI window.
        On abrupt window close, the program exits.
        """
        if title:
            label = Label(self.frame, text=title)
            label.pack(pady=10)

        self.form = Form(self.frame,
                         name_form="",
                         form_dict=form,
                         name_config="Ok",
                         )
        self.form.pack()

        # Set the enter and exit options
        self.form.button.config(command=self._ok)
        # allow Enter for single field, otherwise Ctrl+Enter
        tip, keysym = ("Ctrl+Enter", '<Control-Return>') if len(form) > 1 else ("Enter", "<Return>")
        ToolTip(self.form.button, msg=tip)  # NOTE is not destroyed in _clear
        self._bind_event(keysym, self._ok)
        self.protocol("WM_DELETE_WINDOW", lambda: sys.exit(0))

        # focus the first element and run
        recursive_set_focus(self.form)
        return self.mainloop(lambda: self.form.get())

    def yes_no(self, text: str, focus_no=True):
        return self.buttons(text, [("Yes", True), ("No", False)], int(focus_no)+1)

    def buttons(self, text: str, buttons: list[tuple[str, Any]], focused: int = 1):
        label = Label(self.frame, text=text)
        label.pack(pady=10)

        for text, value in buttons:
            button = Button(self.frame, text=text, command=lambda v=value: self._ok(v))
            button.bind("<Return>", lambda _: button.invoke())
            button.pack(side=LEFT, padx=10)
        self.frame.winfo_children()[focused].focus_set()
        return self.mainloop()

    def _bind_event(self, event, handler):
        self._event_bindings[event] = handler
        self.bind(event, handler)

    def mainloop(self, callback: Callable = None):
        self.frame.pack(pady=5)
        self.deiconify()  # show if hidden
        self.pending_buffer.clear()
        super().mainloop()
        if not self.interface._always_shown:
            self.withdraw()  # hide

        if self._result is Cancelled:
            raise Cancelled
        if callback:
            return callback()
        return self._result

    def _ok(self, val=None):
        # self.destroy()
        self.quit()
        # self.withdraw()
        self._clear_dialog()
        self._result = val

    def _clear_dialog(self):
        self.frame.pack_forget()
        for widget in self.frame.winfo_children():
            widget.destroy()
        for key in self._event_bindings:
            self.unbind(key)
        self._event_bindings.clear()
        self._result = None
