#!/usr/bin/env python3
"""
TCP-Nexus - WhatsApp-inspired Tkinter Client
Standard library only.
"""

import argparse
import json
import queue
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog


APP_BG = "#0B141A"
SIDEBAR_BG = "#111B21"
PANEL_BG = "#202C33"
INPUT_BG = "#2A3942"
TEXT = "#E9EDEF"
MUTED = "#8696A0"
ACCENT = "#00A884"
OWN_BUBBLE = "#005C4B"
OTHER_BUBBLE = "#202C33"
SYSTEM_BG = "#182229"
DANGER = "#EA5B64"


class TCPNexusClient:
    def __init__(self, root, host="127.0.0.1", port=5000):
        self.root = root
        self.host = host
        self.port = port
        self.sock = None
        self.running = threading.Event()
        self.recv_thread = None
        self.incoming = queue.Queue()

        self.username = ""
        self.current_room = None
        self.rooms = {}
        self.users = []
        self.active_private_user = None
        self.chat_mode = "room"  # room | private

        self.root.title("TCP-Nexus")
        self.root.geometry("1180x720")
        self.root.minsize(960, 620)
        self.root.configure(bg=APP_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_login()
        self.root.after(80, self.process_incoming)

    # ---------------- UI helpers ----------------
    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def build_login(self):
        self.clear_root()
        self.root.configure(bg=APP_BG)

        shell = tk.Frame(self.root, bg=APP_BG)
        shell.pack(fill="both", expand=True)

        card = tk.Frame(shell, bg=SIDEBAR_BG, bd=0, highlightthickness=0)
        card.place(relx=0.5, rely=0.5, anchor="center", width=430, height=510)

        tk.Label(
            card, text="TCP-Nexus", bg=SIDEBAR_BG, fg=TEXT,
            font=("Segoe UI", 28, "bold")
        ).pack(pady=(48, 6))

        tk.Label(
            card, text="Secure real-time TCP chat", bg=SIDEBAR_BG, fg=MUTED,
            font=("Segoe UI", 11)
        ).pack(pady=(0, 34))

        form = tk.Frame(card, bg=SIDEBAR_BG)
        form.pack(fill="x", padx=46)

        self.username_entry = self.field(form, "Username", "e.g. raj")
        self.host_entry = self.field(form, "Server IP", self.host)
        self.port_entry = self.field(form, "Port", str(self.port))

        self.connect_btn = tk.Button(
            card, text="Connect", command=self.connect,
            bg=ACCENT, fg="#04110D", activebackground="#06CF9C",
            activeforeground="#04110D", relief="flat", bd=0,
            font=("Segoe UI", 11, "bold"), cursor="hand2"
        )
        self.connect_btn.pack(fill="x", padx=46, pady=(28, 10), ipady=11)

        self.login_status = tk.Label(
            card, text="Server must be running first.",
            bg=SIDEBAR_BG, fg=MUTED, font=("Segoe UI", 9)
        )
        self.login_status.pack(pady=(8, 0))

        self.username_entry.focus_set()
        self.root.bind("<Return>", lambda _e: self.connect())

    def field(self, parent, label, default=""):
        tk.Label(
            parent, text=label, bg=SIDEBAR_BG, fg=MUTED,
            anchor="w", font=("Segoe UI", 9, "bold")
        ).pack(fill="x", pady=(8, 5))
        entry = tk.Entry(
            parent, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", bd=0, font=("Segoe UI", 11)
        )
        entry.pack(fill="x", ipady=9)
        if default:
            entry.insert(0, default)
        return entry

    def build_main_ui(self):
        self.root.unbind("<Return>")
        self.clear_root()

        # Top bar
        top = tk.Frame(self.root, bg=PANEL_BG, height=58)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(
            top, text="TCP-Nexus", bg=PANEL_BG, fg=TEXT,
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", padx=18)

        self.connection_label = tk.Label(
            top, text="● Connected", bg=PANEL_BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold")
        )
        self.connection_label.pack(side="right", padx=18)

        tk.Label(
            top, text=f"@{self.username}", bg=PANEL_BG, fg=MUTED,
            font=("Segoe UI", 10)
        ).pack(side="right")

        body = tk.Frame(self.root, bg=APP_BG)
        body.pack(fill="both", expand=True)

        # Left navigation
        left = tk.Frame(body, bg=SIDEBAR_BG, width=300)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        search_wrap = tk.Frame(left, bg=SIDEBAR_BG)
        search_wrap.pack(fill="x", padx=14, pady=(14, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_sidebars())
        search = tk.Entry(
            search_wrap, textvariable=self.search_var,
            bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=("Segoe UI", 10)
        )
        search.pack(fill="x", ipady=8)
        search.insert(0, "")

        tabs = tk.Frame(left, bg=SIDEBAR_BG)
        tabs.pack(fill="x", padx=14, pady=(0, 8))

        tk.Label(
            tabs, text="ROOMS", bg=SIDEBAR_BG, fg=MUTED,
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        tk.Button(
            tabs, text="+ Create", command=self.create_room_dialog,
            bg=SIDEBAR_BG, fg=ACCENT, activebackground=SIDEBAR_BG,
            activeforeground=ACCENT, relief="flat", cursor="hand2"
        ).pack(side="right")

        self.rooms_list = tk.Listbox(
            left, bg=SIDEBAR_BG, fg=TEXT, selectbackground=PANEL_BG,
            selectforeground=TEXT, activestyle="none", relief="flat",
            borderwidth=0, highlightthickness=0, font=("Segoe UI", 11)
        )
        self.rooms_list.pack(fill="x", padx=8, pady=(0, 12), ipady=4)
        self.rooms_list.bind("<Double-Button-1>", lambda _e: self.join_selected_room())
        self.rooms_list.bind("<<ListboxSelect>>", self.on_room_select)

        room_actions = tk.Frame(left, bg=SIDEBAR_BG)
        room_actions.pack(fill="x", padx=14, pady=(0, 14))
        self.small_button(room_actions, "Join", self.join_selected_room).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.small_button(room_actions, "Leave", self.leave_room).pack(side="left", fill="x", expand=True, padx=(4, 0))

        tk.Frame(left, bg=PANEL_BG, height=1).pack(fill="x", padx=14, pady=(0, 10))

        tk.Label(
            left, text="ONLINE USERS", bg=SIDEBAR_BG, fg=MUTED,
            anchor="w", font=("Segoe UI", 9, "bold")
        ).pack(fill="x", padx=14, pady=(0, 6))

        self.users_list = tk.Listbox(
            left, bg=SIDEBAR_BG, fg=TEXT, selectbackground=PANEL_BG,
            selectforeground=TEXT, activestyle="none", relief="flat",
            borderwidth=0, highlightthickness=0, font=("Segoe UI", 11)
        )
        self.users_list.pack(fill="both", expand=True, padx=8)
        self.users_list.bind("<Double-Button-1>", lambda _e: self.open_private_chat())

        pm_btn = tk.Button(
            left, text="Private Message", command=self.open_private_chat,
            bg=PANEL_BG, fg=TEXT, activebackground=INPUT_BG,
            activeforeground=TEXT, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold")
        )
        pm_btn.pack(fill="x", padx=14, pady=14, ipady=8)

        # Main chat
        main = tk.Frame(body, bg=APP_BG)
        main.pack(side="left", fill="both", expand=True)

        header = tk.Frame(main, bg=PANEL_BG, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        avatar = tk.Label(
            header, text="#", bg=ACCENT, fg="#07251D",
            width=3, height=1, font=("Segoe UI", 13, "bold")
        )
        avatar.pack(side="left", padx=(18, 12), pady=13)

        title_wrap = tk.Frame(header, bg=PANEL_BG)
        title_wrap.pack(side="left", fill="y", pady=12)
        self.chat_title = tk.Label(
            title_wrap, text="Lobby", bg=PANEL_BG, fg=TEXT,
            anchor="w", font=("Segoe UI", 13, "bold")
        )
        self.chat_title.pack(anchor="w")
        self.chat_subtitle = tk.Label(
            title_wrap, text="Group chat", bg=PANEL_BG, fg=MUTED,
            anchor="w", font=("Segoe UI", 9)
        )
        self.chat_subtitle.pack(anchor="w")

        tk.Button(
            header, text="Refresh", command=self.refresh_server_data,
            bg=PANEL_BG, fg=MUTED, activebackground=INPUT_BG,
            activeforeground=TEXT, relief="flat", cursor="hand2"
        ).pack(side="right", padx=16)

        # Chat canvas with scroll
        chat_container = tk.Frame(main, bg=APP_BG)
        chat_container.pack(fill="both", expand=True)

        self.chat_canvas = tk.Canvas(chat_container, bg=APP_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(chat_container, command=self.chat_canvas.yview)
        self.chat_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)

        self.messages_frame = tk.Frame(self.chat_canvas, bg=APP_BG)
        self.messages_window = self.chat_canvas.create_window(
            (0, 0), window=self.messages_frame, anchor="nw"
        )
        self.messages_frame.bind("<Configure>", self._update_scrollregion)
        self.chat_canvas.bind("<Configure>", self._resize_message_window)

        # Composer
        composer = tk.Frame(main, bg=PANEL_BG, height=72)
        composer.pack(fill="x")
        composer.pack_propagate(False)

        self.message_var = tk.StringVar()
        self.message_entry = tk.Entry(
            composer, textvariable=self.message_var,
            bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", font=("Segoe UI", 11)
        )
        self.message_entry.pack(side="left", fill="both", expand=True, padx=(16, 10), pady=14, ipady=9)
        self.message_entry.bind("<Return>", lambda _e: self.send_message())

        send = tk.Button(
            composer, text="Send", command=self.send_message,
            bg=ACCENT, fg="#04110D", activebackground="#06CF9C",
            activeforeground="#04110D", relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        send.pack(side="right", padx=(0, 16), pady=14, ipadx=17, ipady=8)

        self.refresh_server_data()
        self.add_system_message("Welcome to TCP-Nexus. Select a room or user to start chatting.")
        self.message_entry.focus_set()

    def small_button(self, parent, text, command):
        return tk.Button(
            parent, text=text, command=command,
            bg=PANEL_BG, fg=TEXT, activebackground=INPUT_BG,
            activeforeground=TEXT, relief="flat", cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )

    # ---------------- networking ----------------
    def connect(self):
        username = self.username_entry.get().strip()
        host = self.host_entry.get().strip() or "127.0.0.1"

        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be a number.")
            return

        if not username:
            messagebox.showwarning("Username required", "Please enter a username.")
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            sock.settimeout(None)
        except OSError as exc:
            messagebox.showerror("Connection failed", f"Could not connect to server.\n\n{exc}")
            return

        self.sock = sock
        self.host = host
        self.port = port
        self.username = username
        self.running.set()

        self.recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
        self.recv_thread.start()
        self.send_json({"type": "login", "username": username})
        self.login_status.configure(text="Logging in...", fg=ACCENT)

    def receive_loop(self):
        buffer = ""
        try:
            while self.running.is_set():
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.incoming.put(payload)
        except OSError:
            pass
        finally:
            if self.running.is_set():
                self.incoming.put({"type": "_disconnect"})

    def send_json(self, payload):
        if not self.sock:
            return False
        try:
            data = json.dumps(payload, ensure_ascii=False) + "\n"
            self.sock.sendall(data.encode("utf-8"))
            return True
        except OSError:
            self.incoming.put({"type": "_disconnect"})
            return False

    def process_incoming(self):
        try:
            while True:
                payload = self.incoming.get_nowait()
                self.handle_payload(payload)
        except queue.Empty:
            pass
        self.root.after(80, self.process_incoming)

    def handle_payload(self, p):
        t = p.get("type")

        if t == "login_ok":
            self.build_main_ui()

        elif t == "login_error":
            self.login_status.configure(text=p.get("message", "Login failed"), fg=DANGER)
            self.disconnect()

        elif t == "joined":
            self.current_room = p.get("room")
            self.chat_mode = "room"
            self.active_private_user = None
            self.chat_title.configure(text=f"# {self.current_room}")
            self.chat_subtitle.configure(text="Group chat • TCP room")
            self.clear_messages()
            self.add_system_message(p.get("message", f"Joined {self.current_room}"))
            self.refresh_server_data()

        elif t == "left":
            self.current_room = None
            self.add_system_message(p.get("message", "Left room"))
            self.refresh_server_data()

        elif t == "message":
            if self.chat_mode == "room" and p.get("room") == self.current_room:
                self.add_bubble(
                    p.get("from", "?"),
                    p.get("message", ""),
                    own=(p.get("from") == self.username),
                    timestamp=p.get("timestamp")
                )

        elif t == "private":
            sender = p.get("from", "?")
            if self.chat_mode == "private" and self.active_private_user == sender:
                self.add_bubble(sender, p.get("message", ""), own=False, timestamp=p.get("timestamp"))
            else:
                self.add_system_message(f"Private message from {sender}: {p.get('message', '')}")

        elif t == "private_sent":
            if self.chat_mode == "private" and self.active_private_user == p.get("to"):
                self.add_bubble(self.username, p.get("message", ""), own=True, timestamp=p.get("timestamp"))

        elif t == "rooms":
            self.rooms = {r["name"]: r.get("users", 0) for r in p.get("rooms", [])}
            self.refresh_sidebars()

        elif t == "users":
            self.users = p.get("users", [])
            self.refresh_sidebars()

        elif t == "system":
            self.add_system_message(p.get("message", ""))

        elif t == "error":
            self.add_system_message("Error: " + p.get("message", ""))

        elif t == "_disconnect":
            self.connection_label.configure(text="● Disconnected", fg=DANGER) if hasattr(self, "connection_label") else None
            self.running.clear()
            messagebox.showwarning("Disconnected", "Connection to the server was lost.")

    # ---------------- room/user actions ----------------
    def refresh_server_data(self):
        self.send_json({"type": "rooms"})
        self.send_json({"type": "users"})

    def refresh_sidebars(self):
        if not hasattr(self, "rooms_list"):
            return
        query = self.search_var.get().strip().lower()

        self.rooms_list.delete(0, tk.END)
        for name, count in sorted(self.rooms.items()):
            label = f"# {name}   ({count})"
            if not query or query in name.lower():
                self.rooms_list.insert(tk.END, label)

        self.users_list.delete(0, tk.END)
        for user in sorted(self.users):
            if user == self.username:
                continue
            if not query or query in user.lower():
                self.users_list.insert(tk.END, f"● {user}")

    def on_room_select(self, _event=None):
        # Selection only; joining is explicit by button/double-click.
        pass

    def selected_room_name(self):
        selection = self.rooms_list.curselection()
        if not selection:
            return None
        text = self.rooms_list.get(selection[0])
        # "# room   (2)" -> room
        return text[2:].split("   (", 1)[0].strip()

    def join_selected_room(self):
        room = self.selected_room_name()
        if not room:
            messagebox.showinfo("Select room", "Select a room first.")
            return
        self.send_json({"type": "join", "room": room})

    def create_room_dialog(self):
        room = simpledialog.askstring("Create Room", "Room name:", parent=self.root)
        if room:
            room = room.strip()
            if room:
                self.send_json({"type": "create", "room": room})
                self.root.after(250, self.refresh_server_data)

    def leave_room(self):
        self.send_json({"type": "leave"})

    def open_private_chat(self):
        selection = self.users_list.curselection()
        if not selection:
            messagebox.showinfo("Select user", "Select an online user first.")
            return
        user = self.users_list.get(selection[0]).replace("●", "", 1).strip()
        self.chat_mode = "private"
        self.active_private_user = user
        self.chat_title.configure(text=user)
        self.chat_subtitle.configure(text="● Online • Private chat")
        self.clear_messages()
        self.add_system_message(f"Private conversation with {user}")

    # ---------------- messages ----------------
    def send_message(self):
        text = self.message_var.get().strip()
        if not text:
            return

        if self.chat_mode == "private":
            if not self.active_private_user:
                messagebox.showinfo("Private chat", "Select an online user first.")
                return
            self.send_json({
                "type": "pm",
                "to": self.active_private_user,
                "message": text
            })
        else:
            if not self.current_room:
                messagebox.showinfo("Join a room", "Please join a room first.")
                return
            self.send_json({"type": "msg", "message": text})

        self.message_var.set("")

    def add_bubble(self, sender, message, own=False, timestamp=None):
        row = tk.Frame(self.messages_frame, bg=APP_BG)
        row.pack(fill="x", padx=20, pady=5)

        bubble = tk.Frame(row, bg=OWN_BUBBLE if own else OTHER_BUBBLE)
        bubble.pack(side="right" if own else "left", anchor="e" if own else "w")

        if not own:
            tk.Label(
                bubble, text=sender, bg=OTHER_BUBBLE, fg=ACCENT,
                font=("Segoe UI", 8, "bold"), anchor="w"
            ).pack(fill="x", padx=10, pady=(7, 0))

        tk.Label(
            bubble, text=message, bg=OWN_BUBBLE if own else OTHER_BUBBLE,
            fg=TEXT, justify="left", wraplength=520,
            font=("Segoe UI", 10), anchor="w"
        ).pack(fill="x", padx=10, pady=(5, 2))

        stamp = timestamp or datetime.now().strftime("%H:%M")
        tk.Label(
            bubble, text=stamp + ("  ✓✓" if own else ""),
            bg=OWN_BUBBLE if own else OTHER_BUBBLE,
            fg="#9CCFC0" if own else MUTED,
            font=("Segoe UI", 7), anchor="e"
        ).pack(fill="x", padx=10, pady=(0, 6))

        self.root.after(30, self.scroll_bottom)

    def add_system_message(self, text):
        if not hasattr(self, "messages_frame"):
            return
        wrap = tk.Frame(self.messages_frame, bg=APP_BG)
        wrap.pack(fill="x", padx=20, pady=6)
        tk.Label(
            wrap, text=text, bg=SYSTEM_BG, fg=MUTED,
            font=("Segoe UI", 8), padx=10, pady=5
        ).pack()
        self.root.after(30, self.scroll_bottom)

    def clear_messages(self):
        for child in self.messages_frame.winfo_children():
            child.destroy()

    def _update_scrollregion(self, _event=None):
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))

    def _resize_message_window(self, event):
        self.chat_canvas.itemconfigure(self.messages_window, width=event.width)

    def scroll_bottom(self):
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    # ---------------- shutdown ----------------
    def disconnect(self):
        self.running.clear()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
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
                self.send_json({"type": "quit"})
            except Exception:
                pass
        self.disconnect()
        self.root.destroy()


def parse_args():
    parser = argparse.ArgumentParser(description="TCP-Nexus visual client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    root = tk.Tk()
    TCPNexusClient(root, host=args.host, port=args.port)
    root.mainloop()
