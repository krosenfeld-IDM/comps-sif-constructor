import getpass
import os
import platform
import sys
from future.utils import with_metaclass
from abc import ABCMeta, abstractmethod


class CredentialPrompt(with_metaclass(ABCMeta, object)):
    """
    Abstract definition for our credential prompts.
    """
    @abstractmethod
    def prompt(self):
        """
        The prompt method will ask a user for COMPS usernme and password. It should return a duct containing the
        username and password keys and values
        :return:
        """
        pass


class ConsoleCredentialPrompt(CredentialPrompt):
    """
    A simple console based credential prompt
    """
    def prompt(self):
        username = input("Username: ")
        password = getpass.getpass()
        return dict(Username=username.strip(), Password=password)


class TKCredentialPrompt(CredentialPrompt):
    """
    A TK based credential prompt
    """
    def prompt(self):
        if sys.version_info[0] == 2:
            import Tkinter as tk
        else:
            import tkinter as tk
        master = tk.Tk()
        master.title('COMPS Login')
        master["padx"] = 12
        master["pady"] = 10

        input_frame = tk.Frame(master)
        input_frame.grid(row=0)

        username = tk.StringVar(master)
        password = tk.StringVar(master)
        ret_ok = tk.BooleanVar(master)

        tk.Label(input_frame, text='Username', padx=10).grid(row=0)
        usrbox = tk.Entry(input_frame, textvariable=username)
        usrbox.grid(row=0, column=1)
        usrbox.focus()

        tk.Label(input_frame, text='Password', padx=10, pady=5).grid(row=1)
        pwdbox = tk.Entry(input_frame, show='*', textvariable=password)
        pwdbox.grid(row=1, column=1)

        def inputchanged(*args):
            if username.get() and password.get():
                okay_button.config(state='normal')
            else:
                okay_button.config(state='disabled')

        def onok(evt=None):
            if okay_button.cget('state') in ['normal', 'active']:
                ret_ok.set(True)
                master.destroy()

        def oncancel(evt=None):
            username.set('')
            password.set('')
            ret_ok.set(False)
            master.destroy()

        username.trace("w", inputchanged)
        password.trace("w", inputchanged)

        button_frame = tk.Frame(master)
        button_frame["pady"] = 4
        button_frame.grid(row=1)
        button_frame.columnconfigure(0, weight=1, pad=6)
        button_frame.columnconfigure(1, weight=1, pad=6)

        okay_button = tk.Button(button_frame, command=onok, text='OK', state="disabled", width=10)
        okay_button.grid(row=0, column=0)
        tk.Button(button_frame, command=oncancel, text='Cancel', width=10).grid(row=0, column=1)

        master.bind('<Return>', onok)
        master.bind('<Escape>', oncancel)

        # reposition to the middle of the screen
        master.update_idletasks()
        w = master.winfo_screenwidth()
        h = master.winfo_screenheight()
        size = tuple(int(_) for _ in master.geometry().split('+')[0].split('x'))
        x = w / 2 - size[0] / 2
        y = h / 2 - size[1] / 2
        master.geometry("%dx%d+%d+%d" % (size + (x, y)))

        # make sure the dialog is in the front
        # if platform.system() != 'Darwin':
        #     master.lift()
        if platform.system() != 'Darwin':
            master.lift()
        else:
            # .lift() apparently doesn't work on OSX... try this instead
            os.system('''/usr/bin/osascript -e 'tell app "Finder" to set frontmost of process "Python" to true' ''')

        master.mainloop()

        if not ret_ok.get():
            raise RuntimeError('User canceled attempt to get security credentials.')

        if len(username.get()) == 0 or len(password.get()) == 0:
            return None
        else:
            return {'Username': username.get(), 'Password': password.get()}


def get_credential_prompt():
    """
    Determines the appropriate CredentialPrompt. If TK is available, we use that, otherwise we fallback to Console 
    based login.
    
    :return: CredentialPrompt factory 
    """

    try:
        if sys.version_info[0] == 2:
            import Tkinter as tk
        else:
            import tkinter as tk
        # attempt to initialize tk to test if we have a display. This mainly applies to linux systems where
        # tk is installed but we are running in a headless session such as through SSH
        testwin = tk.Tk()
        testwin.destroy()
        return TKCredentialPrompt()
    except:
        return ConsoleCredentialPrompt()
