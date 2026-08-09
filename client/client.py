import argparse
import json
import queue
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog


# ============================================================
# Theme
# ============================================================

APP_BG = "#0B141A"
SIDEBAR_BG = "#111B21"
HEADER_BG = "#202C33"
INPUT_BG = "#2A3942"
TEXT = "#E9EDEF"
MUTED = "#8696A0"
ACCENT = "#00A884"
OWN_BUBBLE = "#005C4B"
OTHER_BUBBLE = "#202C33"
SYSTEM_BG = "#182229"
DANGER = "#EA5B64"
MENU_BG = "#233138"


class TCPNexusGUI:
    def __init__(
        self,
        root,
        host="127.0.0.1",
        port=5000
    ):
        self.root = root
        self.host = host
        self.port = port

        self.sock = None
        self.running = threading.Event()
        self.incoming = queue.Queue()

        self.username = ""
        self.current_room = None

        self.chat_mode = "room"
        self.private_user = None

        self.rooms = {}
        self.users = []

        # message_id -> visible widget data
        self.message_widgets = {}

        # Context history during this client session
        self.room_messages = {}
        self.private_messages = {}

        self.root.title("TCP-Nexus")
        self.root.geometry("1200x760")
        self.root.minsize(980, 620)
        self.root.configure(bg=APP_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_login()

        # Process network events safely on Tkinter main thread
        self.root.after(70, self.process_incoming)

    # ============================================================
    # Generic UI
    # ============================================================

    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # ============================================================
    # Login Screen
    # ============================================================

    def build_login(self):
        self.clear_root()
        self.root.configure(bg=APP_BG)

        outer = tk.Frame(
            self.root,
            bg=APP_BG
        )
        outer.pack(
            fill="both",
            expand=True
        )

        card = tk.Frame(
            outer,
            bg=SIDEBAR_BG
        )

        card.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            width=440,
            height=520
        )

        tk.Label(
            card,
            text="TCP-Nexus",
            bg=SIDEBAR_BG,
            fg=TEXT,
            font=("Segoe UI", 29, "bold")
        ).pack(
            pady=(48, 7)
        )

        tk.Label(
            card,
            text="Real-time TCP messaging",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=("Segoe UI", 10)
        ).pack(
            pady=(0, 30)
        )

        form = tk.Frame(
            card,
            bg=SIDEBAR_BG
        )

        form.pack(
            fill="x",
            padx=48
        )

        self.username_entry = self.make_entry(
            form,
            "Username",
            ""
        )

        self.host_entry = self.make_entry(
            form,
            "Server IP",
            self.host
        )

        self.port_entry = self.make_entry(
            form,
            "Port",
            str(self.port)
        )

        tk.Button(
            card,
            text="CONNECT",
            command=self.connect,
            bg=ACCENT,
            fg="#04110D",
            activebackground="#05C99A",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        ).pack(
            fill="x",
            padx=48,
            pady=(30, 12),
            ipady=11
        )

        self.login_status = tk.Label(
            card,
            text="Start server.py before connecting.",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=("Segoe UI", 9)
        )

        self.login_status.pack()

        self.username_entry.focus_set()

        self.root.bind(
            "<Return>",
            lambda _event: self.connect()
        )

    def make_entry(
        self,
        parent,
        label,
        initial
    ):
        tk.Label(
            parent,
            text=label,
            bg=SIDEBAR_BG,
            fg=MUTED,
            anchor="w",
            font=("Segoe UI", 9, "bold")
        ).pack(
            fill="x",
            pady=(9, 5)
        )

        entry = tk.Entry(
            parent,
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 11)
        )

        entry.pack(
            fill="x",
            ipady=9
        )

        if initial:
            entry.insert(
                0,
                initial
            )

        return entry

    # ============================================================
    # Main UI
    # ============================================================

    def build_main(self):
        self.root.unbind("<Return>")
        self.clear_root()

        # ---------------- Top bar ----------------

        top = tk.Frame(
            self.root,
            bg=HEADER_BG,
            height=58
        )

        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(
            top,
            text="TCP-Nexus",
            bg=HEADER_BG,
            fg=TEXT,
            font=("Segoe UI", 16, "bold")
        ).pack(
            side="left",
            padx=18
        )

        self.connection_label = tk.Label(
            top,
            text="● Connected",
            bg=HEADER_BG,
            fg=ACCENT,
            font=("Segoe UI", 10, "bold")
        )

        self.connection_label.pack(
            side="right",
            padx=18
        )

        tk.Label(
            top,
            text=f"@{self.username}",
            bg=HEADER_BG,
            fg=MUTED,
            font=("Segoe UI", 10)
        ).pack(
            side="right"
        )

        # ---------------- Main body ----------------

        body = tk.Frame(
            self.root,
            bg=APP_BG
        )

        body.pack(
            fill="both",
            expand=True
        )

        self.build_sidebar(body)
        self.build_chat_panel(body)

        # IMPORTANT:
        # Refresh once immediately
        self.refresh_server_data()

        # IMPORTANT:
        # Refresh again after GUI is fully built.
        # This prevents login-event timing race.
        self.root.after(
            200,
            self.refresh_server_data
        )

    # ============================================================
    # Sidebar
    # ============================================================

    def build_sidebar(self, parent):
        left = tk.Frame(
            parent,
            bg=SIDEBAR_BG,
            width=310
        )

        left.pack(
            side="left",
            fill="y"
        )

        left.pack_propagate(False)

        # Search
        search_frame = tk.Frame(
            left,
            bg=SIDEBAR_BG
        )

        search_frame.pack(
            fill="x",
            padx=14,
            pady=(14, 10)
        )

        self.search_var = tk.StringVar()

        self.search_var.trace_add(
            "write",
            lambda *_: self.refresh_lists()
        )

        tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 10)
        ).pack(
            fill="x",
            ipady=8
        )

        # Rooms header
        room_header = tk.Frame(
            left,
            bg=SIDEBAR_BG
        )

        room_header.pack(
            fill="x",
            padx=14,
            pady=(2, 6)
        )

        tk.Label(
            room_header,
            text="ROOMS",
            bg=SIDEBAR_BG,
            fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(
            side="left"
        )

        tk.Button(
            room_header,
            text="+ Create",
            command=self.create_room,
            bg=SIDEBAR_BG,
            fg=ACCENT,
            activebackground=SIDEBAR_BG,
            activeforeground=ACCENT,
            relief="flat",
            cursor="hand2"
        ).pack(
            side="right"
        )

        # Room list
        self.rooms_list = tk.Listbox(
            left,
            bg=SIDEBAR_BG,
            fg=TEXT,
            selectbackground=HEADER_BG,
            selectforeground=TEXT,
            relief="flat",
            highlightthickness=0,
            activestyle="none",
            font=("Segoe UI", 10)
        )

        self.rooms_list.pack(
            fill="x",
            padx=8,
            pady=(0, 8)
        )

        self.rooms_list.bind(
            "<Double-Button-1>",
            lambda _event: self.join_selected_room()
        )

        room_buttons = tk.Frame(
            left,
            bg=SIDEBAR_BG
        )

        room_buttons.pack(
            fill="x",
            padx=14,
            pady=(0, 12)
        )

        self.side_button(
            room_buttons,
            "Join",
            self.join_selected_room
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 4)
        )

        self.side_button(
            room_buttons,
            "Leave",
            self.leave_room
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(4, 0)
        )

        tk.Frame(
            left,
            height=1,
            bg=HEADER_BG
        ).pack(
            fill="x",
            padx=14,
            pady=(0, 10)
        )

        # Online users
        tk.Label(
            left,
            text="ONLINE USERS",
            bg=SIDEBAR_BG,
            fg=MUTED,
            anchor="w",
            font=("Segoe UI", 9, "bold")
        ).pack(
            fill="x",
            padx=14,
            pady=(0, 6)
        )

        self.users_list = tk.Listbox(
            left,
            bg=SIDEBAR_BG,
            fg=TEXT,
            selectbackground=HEADER_BG,
            selectforeground=TEXT,
            relief="flat",
            highlightthickness=0,
            activestyle="none",
            font=("Segoe UI", 10)
        )

        self.users_list.pack(
            fill="both",
            expand=True,
            padx=8
        )

        self.users_list.bind(
            "<Double-Button-1>",
            lambda _event: self.open_private_chat()
        )

        tk.Button(
            left,
            text="Private Chat",
            command=self.open_private_chat,
            bg=HEADER_BG,
            fg=TEXT,
            activebackground=INPUT_BG,
            activeforeground=TEXT,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        ).pack(
            fill="x",
            padx=14,
            pady=14,
            ipady=8
        )

    def side_button(
        self,
        parent,
        text,
        command
    ):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=HEADER_BG,
            fg=TEXT,
            activebackground=INPUT_BG,
            activeforeground=TEXT,
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )

    # ============================================================
    # Chat panel
    # ============================================================

    def build_chat_panel(self, parent):
        main = tk.Frame(
            parent,
            bg=APP_BG
        )

        main.pack(
            side="left",
            fill="both",
            expand=True
        )

        # Chat header
        chat_header = tk.Frame(
            main,
            bg=HEADER_BG,
            height=70
        )

        chat_header.pack(
            fill="x"
        )

        chat_header.pack_propagate(False)

        self.avatar_label = tk.Label(
            chat_header,
            text="#",
            bg=ACCENT,
            fg="#04271F",
            font=("Segoe UI", 13, "bold"),
            width=3
        )

        self.avatar_label.pack(
            side="left",
            padx=(18, 12),
            pady=14
        )

        header_text = tk.Frame(
            chat_header,
            bg=HEADER_BG
        )

        header_text.pack(
            side="left",
            pady=12
        )

        self.chat_title = tk.Label(
            header_text,
            text="# lobby",
            bg=HEADER_BG,
            fg=TEXT,
            font=("Segoe UI", 13, "bold"),
            anchor="w"
        )

        self.chat_title.pack(
            anchor="w"
        )

        self.chat_subtitle = tk.Label(
            header_text,
            text="Group chat",
            bg=HEADER_BG,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w"
        )

        self.chat_subtitle.pack(
            anchor="w"
        )

        tk.Button(
            chat_header,
            text="Refresh",
            command=self.refresh_server_data,
            bg=HEADER_BG,
            fg=MUTED,
            activebackground=INPUT_BG,
            activeforeground=TEXT,
            relief="flat",
            cursor="hand2"
        ).pack(
            side="right",
            padx=16
        )

        # Chat canvas
        chat_container = tk.Frame(
            main,
            bg=APP_BG
        )

        chat_container.pack(
            fill="both",
            expand=True
        )

        self.chat_canvas = tk.Canvas(
            chat_container,
            bg=APP_BG,
            highlightthickness=0
        )

        scrollbar = tk.Scrollbar(
            chat_container,
            orient="vertical",
            command=self.chat_canvas.yview
        )

        self.chat_canvas.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y"
        )

        self.chat_canvas.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.messages_frame = tk.Frame(
            self.chat_canvas,
            bg=APP_BG
        )

        self.messages_window = self.chat_canvas.create_window(
            (0, 0),
            window=self.messages_frame,
            anchor="nw"
        )

        self.messages_frame.bind(
            "<Configure>",
            self.update_scrollregion
        )

        self.chat_canvas.bind(
            "<Configure>",
            self.resize_messages_frame
        )

        # Composer
        composer = tk.Frame(
            main,
            bg=HEADER_BG,
            height=74
        )

        composer.pack(
            fill="x"
        )

        composer.pack_propagate(False)

        self.message_var = tk.StringVar()

        self.message_entry = tk.Entry(
            composer,
            textvariable=self.message_var,
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 11)
        )

        self.message_entry.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(16, 10),
            pady=14,
            ipady=9
        )

        self.message_entry.bind(
            "<Return>",
            lambda _event: self.send_message()
        )

        tk.Button(
            composer,
            text="Send",
            command=self.send_message,
            bg=ACCENT,
            fg="#04110D",
            activebackground="#05C99A",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        ).pack(
            side="right",
            padx=(0, 16),
            pady=14,
            ipadx=18,
            ipady=8
        )

    # ============================================================
    # Networking
    # ============================================================

    def connect(self):
        username = self.username_entry.get().strip()
        host = self.host_entry.get().strip() or "127.0.0.1"

        try:
            port = int(
                self.port_entry.get().strip()
            )

        except ValueError:
            messagebox.showerror(
                "Invalid Port",
                "Port must be a number."
            )
            return

        if not username:
            messagebox.showwarning(
                "Username",
                "Enter a username."
            )
            return

        try:
            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            sock.settimeout(5)
            sock.connect((host, port))
            sock.settimeout(None)

        except OSError as exc:
            messagebox.showerror(
                "Connection Failed",
                f"Could not connect to {host}:{port}\n\n{exc}"
            )
            return

        self.sock = sock
        self.username = username
        self.host = host
        self.port = port
        self.running.set()

        threading.Thread(
            target=self.receive_loop,
            daemon=True,
            name="TCP-Nexus-Receiver"
        ).start()

        self.send_json({
            "type": "login",
            "username": username
        })

        self.login_status.configure(
            text="Connecting...",
            fg=ACCENT
        )

    def receive_loop(self):
        buffer = ""

        try:
            while self.running.is_set():
                data = self.sock.recv(4096)

                if not data:
                    break

                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split(
                        "\n",
                        1
                    )

                    line = line.strip()

                    if not line:
                        continue

                    try:
                        payload = json.loads(line)

                    except json.JSONDecodeError:
                        continue

                    self.incoming.put(payload)

        except (
            OSError,
            ConnectionResetError,
            BrokenPipeError
        ):
            pass

        finally:
            if self.running.is_set():
                self.incoming.put({
                    "type": "_disconnect"
                })

    def send_json(self, payload) -> bool:
        if not self.sock:
            return False

        try:
            raw = (
                json.dumps(
                    payload,
                    ensure_ascii=False
                )
                + "\n"
            )

            self.sock.sendall(
                raw.encode("utf-8")
            )

            return True

        except OSError:
            self.incoming.put({
                "type": "_disconnect"
            })

            return False

    def process_incoming(self):
        try:
            while True:
                payload = self.incoming.get_nowait()
                self.handle_payload(payload)

        except queue.Empty:
            pass

        self.root.after(
            70,
            self.process_incoming
        )

    # ============================================================
    # Server Events
    # ============================================================

    def handle_payload(self, p):
        msg_type = p.get("type")

        if msg_type == "login_ok":
            self.build_main()

            # Extra refresh after build
            self.root.after(
                200,
                self.refresh_server_data
            )

        elif msg_type == "login_error":
            self.login_status.configure(
                text=p.get(
                    "message",
                    "Login failed"
                ),
                fg=DANGER
            )

            self.disconnect()

        elif msg_type == "joined":
            self.current_room = p.get("room")
            self.chat_mode = "room"
            self.private_user = None

            self.chat_title.configure(
                text=f"# {self.current_room}"
            )

            self.chat_subtitle.configure(
                text="Group chat • TCP room"
            )

            self.avatar_label.configure(
                text="#"
            )

            self.redraw_current_chat()

            self.add_system_message(
                p.get(
                    "message",
                    "Joined room"
                )
            )

            self.refresh_server_data()

        elif msg_type == "left":
            self.current_room = None

            self.add_system_message(
                p.get(
                    "message",
                    "Left room"
                )
            )

            self.refresh_server_data()

        elif msg_type == "rooms":
            self.rooms = {
                item["name"]: item.get(
                    "users",
                    0
                )
                for item in p.get(
                    "rooms",
                    []
                )
            }

            self.refresh_lists()

        elif msg_type == "users":
            self.users = p.get(
                "users",
                []
            )

            self.refresh_lists()

        elif msg_type == "message":
            self.store_room_message(p)

            if (
                self.chat_mode == "room"
                and p.get("room") == self.current_room
            ):
                self.render_message_event(p)

        elif msg_type == "private":
            self.store_private_message(p)

            if p.get("from") == self.username:
                other = p.get("to")
            else:
                other = p.get("from")

            if (
                self.chat_mode == "private"
                and self.private_user == other
            ):
                self.render_message_event(p)

            elif p.get("from") != self.username:
                self.add_system_message(
                    f"New private message from {p.get('from')}"
                )

        elif msg_type == "message_edited":
            self.apply_edit_event(p)

        elif msg_type == "message_deleted":
            self.apply_delete_event(p)

        elif msg_type == "system":
            self.add_system_message(
                p.get(
                    "message",
                    ""
                )
            )

        elif msg_type == "error":
            self.add_system_message(
                "Error: "
                + p.get(
                    "message",
                    ""
                )
            )

        elif msg_type == "_disconnect":
            self.running.clear()

            if hasattr(
                self,
                "connection_label"
            ):
                self.connection_label.configure(
                    text="● Disconnected",
                    fg=DANGER
                )

            messagebox.showwarning(
                "Disconnected",
                "Connection to the server was lost."
            )

    # ============================================================
    # Online Users + Rooms
    # ============================================================

    def refresh_server_data(self):
        if not self.sock:
            return

        self.send_json({
            "type": "rooms"
        })

        self.send_json({
            "type": "users"
        })

    def refresh_lists(self):
        if not hasattr(
            self,
            "rooms_list"
        ):
            return

        query = self.search_var.get().strip().lower()

        # ---------------- Rooms ----------------

        self.rooms_list.delete(
            0,
            tk.END
        )

        for room, count in sorted(
            self.rooms.items()
        ):
            if (
                query
                and query not in room.lower()
            ):
                continue

            self.rooms_list.insert(
                tk.END,
                f"# {room}   ({count})"
            )

        # ---------------- Users ----------------

        self.users_list.delete(
            0,
            tk.END
        )

        for user in sorted(self.users):
            if (
                query
                and query not in user.lower()
            ):
                continue

            # FIX:
            # Show own username instead of hiding it.
            if user == self.username:
                label = f"● {user} (You)"
            else:
                label = f"● {user}"

            self.users_list.insert(
                tk.END,
                label
            )

    # ============================================================
    # Room Actions
    # ============================================================

    def selected_room(self):
        selected = self.rooms_list.curselection()

        if not selected:
            return None

        raw = self.rooms_list.get(
            selected[0]
        )

        return (
            raw[2:]
            .split(
                "   (",
                1
            )[0]
            .strip()
        )

    def join_selected_room(self):
        room = self.selected_room()

        if not room:
            messagebox.showinfo(
                "Join Room",
                "Select a room first."
            )
            return

        self.send_json({
            "type": "join",
            "room": room
        })

    def create_room(self):
        room = simpledialog.askstring(
            "Create Room",
            "Enter room name:",
            parent=self.root
        )

        if room:
            room = room.strip()

            if room:
                self.send_json({
                    "type": "create",
                    "room": room
                })

                self.root.after(
                    250,
                    self.refresh_server_data
                )

    def leave_room(self):
        self.send_json({
            "type": "leave"
        })

    # ============================================================
    # Private Chat
    # ============================================================

    def selected_online_user(self):
        selected = self.users_list.curselection()

        if not selected:
            return None

        raw = self.users_list.get(
            selected[0]
        )

        user = (
            raw
            .replace(
                "●",
                "",
                1
            )
            .strip()
        )

        # Remove "(You)"
        if user.endswith("(You)"):
            user = (
                user[:-5]
                .strip()
            )

        return user

    def open_private_chat(self):
        user = self.selected_online_user()

        if not user:
            messagebox.showinfo(
                "Private Chat",
                "Select an online user first."
            )
            return

        # Prevent private-chatting yourself
        if user == self.username:
            messagebox.showinfo(
                "Private Chat",
                "This is your own account."
            )
            return

        self.chat_mode = "private"
        self.private_user = user

        self.chat_title.configure(
            text=user
        )

        self.chat_subtitle.configure(
            text="● Online • Private chat"
        )

        self.avatar_label.configure(
            text=(
                user[:1].upper()
                if user
                else "U"
            )
        )

        self.redraw_current_chat()
        self.message_entry.focus_set()

    # ============================================================
    # Message storage
    # ============================================================

    def store_room_message(self, p):
        room = p.get("room")

        if not room:
            return

        messages = self.room_messages.setdefault(
            room,
            []
        )

        if any(
            item.get("id") == p.get("id")
            for item in messages
        ):
            return

        messages.append(
            dict(p)
        )

    def private_key(self, user):
        return user

    def store_private_message(self, p):
        if p.get("from") == self.username:
            other = p.get("to")
        else:
            other = p.get("from")

        if not other:
            return

        key = self.private_key(other)

        messages = self.private_messages.setdefault(
            key,
            []
        )

        if any(
            item.get("id") == p.get("id")
            for item in messages
        ):
            return

        messages.append(
            dict(p)
        )

    def find_stored_message(
        self,
        message_id
    ):
        for messages in self.room_messages.values():
            for item in messages:
                if item.get("id") == message_id:
                    return item

        for messages in self.private_messages.values():
            for item in messages:
                if item.get("id") == message_id:
                    return item

        return None

    # ============================================================
    # Edit/Delete
    # ============================================================

    def edit_message_dialog(
        self,
        message_id
    ):
        item = self.find_stored_message(
            message_id
        )

        if not item:
            return

        if item.get("from") != self.username:
            return

        current = item.get(
            "message",
            ""
        )

        new_text = simpledialog.askstring(
            "Edit Message",
            "Edit your message:",
            initialvalue=current,
            parent=self.root
        )

        if new_text is None:
            return

        new_text = new_text.strip()

        if not new_text:
            messagebox.showwarning(
                "Edit Message",
                "Message cannot be empty."
            )
            return

        self.send_json({
            "type": "edit",
            "id": message_id,
            "message": new_text
        })

    def delete_message_confirm(
        self,
        message_id
    ):
        item = self.find_stored_message(
            message_id
        )

        if (
            not item
            or item.get("from") != self.username
        ):
            return

        if messagebox.askyesno(
            "Delete Message",
            "Delete this message for everyone?"
        ):
            self.send_json({
                "type": "delete",
                "id": message_id
            })

    def apply_edit_event(self, p):
        message_id = p.get("id")

        item = self.find_stored_message(
            message_id
        )

        if item:
            item["message"] = p.get(
                "message",
                ""
            )

            item["edited"] = True

        widget_data = self.message_widgets.get(
            message_id
        )

        if widget_data:
            widget_data[
                "text_label"
            ].configure(
                text=p.get(
                    "message",
                    ""
                )
            )

            widget_data[
                "meta_label"
            ].configure(
                text=self.meta_text(
                    widget_data["timestamp"],
                    widget_data["own"],
                    edited=True
                )
            )

    def apply_delete_event(self, p):
        message_id = p.get("id")

        item = self.find_stored_message(
            message_id
        )

        if item:
            item["deleted"] = True
            item["message"] = (
                "This message was deleted"
            )

        widget_data = self.message_widgets.get(
            message_id
        )

        if widget_data:
            widget_data[
                "text_label"
            ].configure(
                text="This message was deleted",
                fg=MUTED,
                font=(
                    "Segoe UI",
                    10,
                    "italic"
                )
            )

            menu_button = widget_data.get(
                "menu_button"
            )

            if menu_button:
                menu_button.destroy()

                widget_data[
                    "menu_button"
                ] = None

    # ============================================================
    # Message rendering
    # ============================================================

    def meta_text(
        self,
        timestamp,
        own,
        edited=False
    ):
        text = (
            timestamp
            or datetime.now().strftime("%H:%M")
        )

        if edited:
            text += "  edited"

        if own:
            text += "  ✓✓"

        return text

    def render_message_event(self, p):
        message_id = p.get("id")

        if not message_id:
            return

        if message_id in self.message_widgets:
            return

        sender = p.get(
            "from",
            "?"
        )

        own = (
            sender == self.username
        )

        deleted = p.get(
            "deleted",
            False
        )

        text = (
            "This message was deleted"
            if deleted
            else p.get(
                "message",
                ""
            )
        )

        timestamp = (
            p.get("timestamp")
            or datetime.now().strftime("%H:%M")
        )

        edited = p.get(
            "edited",
            False
        )

        row = tk.Frame(
            self.messages_frame,
            bg=APP_BG
        )

        row.pack(
            fill="x",
            padx=22,
            pady=5
        )

        bubble_bg = (
            OWN_BUBBLE
            if own
            else OTHER_BUBBLE
        )

        bubble = tk.Frame(
            row,
            bg=bubble_bg
        )

        bubble.pack(
            side=(
                "right"
                if own
                else "left"
            ),
            anchor=(
                "e"
                if own
                else "w"
            )
        )

        top_line = tk.Frame(
            bubble,
            bg=bubble_bg
        )

        top_line.pack(
            fill="x",
            padx=9,
            pady=(6, 0)
        )

        if not own:
            tk.Label(
                top_line,
                text=sender,
                bg=bubble_bg,
                fg=ACCENT,
                font=(
                    "Segoe UI",
                    8,
                    "bold"
                )
            ).pack(
                side="left"
            )

        menu_button = None

        if own and not deleted:
            menu_button = tk.Button(
                top_line,
                text="⋮",
                bg=bubble_bg,
                fg=MUTED,
                activebackground=bubble_bg,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=(
                    "Segoe UI",
                    12,
                    "bold"
                ),
                cursor="hand2",
                command=lambda mid=message_id:
                    self.show_message_menu(mid)
            )

            menu_button.pack(
                side="right"
            )

        text_label = tk.Label(
            bubble,
            text=text,
            bg=bubble_bg,
            fg=(
                MUTED
                if deleted
                else TEXT
            ),
            justify="left",
            wraplength=520,
            anchor="w",
            font=(
                "Segoe UI",
                10,
                "italic"
                if deleted
                else "normal"
            )
        )

        text_label.pack(
            fill="x",
            padx=10,
            pady=(4, 2)
        )

        meta_label = tk.Label(
            bubble,
            text=self.meta_text(
                timestamp,
                own,
                edited
            ),
            bg=bubble_bg,
            fg=(
                "#9CCFC0"
                if own
                else MUTED
            ),
            font=(
                "Segoe UI",
                7
            ),
            anchor="e"
        )

        meta_label.pack(
            fill="x",
            padx=10,
            pady=(0, 6)
        )

        self.message_widgets[
            message_id
        ] = {
            "row": row,
            "bubble": bubble,
            "text_label": text_label,
            "meta_label": meta_label,
            "menu_button": menu_button,
            "timestamp": timestamp,
            "own": own
        }

        self.root.after(
            20,
            self.scroll_bottom
        )

    def show_message_menu(
        self,
        message_id
    ):
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg=MENU_BG,
            fg=TEXT,
            activebackground=ACCENT,
            activeforeground="#04110D"
        )

        menu.add_command(
            label="Edit message",
            command=lambda:
                self.edit_message_dialog(
                    message_id
                )
        )

        menu.add_command(
            label="Delete for everyone",
            command=lambda:
                self.delete_message_confirm(
                    message_id
                )
        )

        try:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()

            menu.tk_popup(
                x,
                y
            )

        finally:
            menu.grab_release()

    def redraw_current_chat(self):
        self.clear_messages()

        if self.chat_mode == "room":
            messages = self.room_messages.get(
                self.current_room,
                []
            )

        else:
            messages = self.private_messages.get(
                self.private_key(
                    self.private_user
                ),
                []
            )

        for item in messages:
            self.render_message_event(
                item
            )

    def clear_messages(self):
        for child in self.messages_frame.winfo_children():
            child.destroy()

        self.message_widgets.clear()

    def add_system_message(self, text):
        if (
            not hasattr(
                self,
                "messages_frame"
            )
            or not text
        ):
            return

        wrap = tk.Frame(
            self.messages_frame,
            bg=APP_BG
        )

        wrap.pack(
            fill="x",
            padx=20,
            pady=7
        )

        tk.Label(
            wrap,
            text=text,
            bg=SYSTEM_BG,
            fg=MUTED,
            font=(
                "Segoe UI",
                8
            ),
            padx=10,
            pady=5
        ).pack()

        self.root.after(
            20,
            self.scroll_bottom
        )

    # ============================================================
    # Send Message
    # ============================================================

    def send_message(self):
        text = self.message_var.get().strip()

        if not text:
            return

        if self.chat_mode == "private":
            if not self.private_user:
                messagebox.showinfo(
                    "Private Chat",
                    "Select a user first."
                )
                return

            ok = self.send_json({
                "type": "pm",
                "to": self.private_user,
                "message": text
            })

        else:
            if not self.current_room:
                messagebox.showinfo(
                    "Room",
                    "Join a room first."
                )
                return

            ok = self.send_json({
                "type": "msg",
                "message": text
            })

        if ok:
            self.message_var.set("")

    # ============================================================
    # Canvas
    # ============================================================

    def update_scrollregion(
        self,
        _event=None
    ):
        self.chat_canvas.configure(
            scrollregion=self.chat_canvas.bbox(
                "all"
            )
        )

    def resize_messages_frame(
        self,
        event
    ):
        self.chat_canvas.itemconfigure(
            self.messages_window,
            width=event.width
        )

    def scroll_bottom(self):
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    # ============================================================
    # Shutdown
    # ============================================================

    def disconnect(self):
        self.running.clear()

        if self.sock:
            try:
                self.sock.shutdown(
                    socket.SHUT_RDWR
                )
            except OSError:
                pass

            try:
                self.sock.close()
            except OSError:
                pass

        self.sock = None

    def on_close(self):
        if self.sock:
            try:
                self.send_json({
                    "type": "quit"
                })
            except Exception:
                pass

        self.disconnect()
        self.root.destroy()


def parse_args():
    parser = argparse.ArgumentParser(
        description="TCP-Nexus professional GUI client"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5000
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    root = tk.Tk()

    TCPNexusGUI(
        root,
        host=args.host,
        port=args.port
    )

    root.mainloop()