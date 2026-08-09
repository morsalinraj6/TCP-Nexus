#!/usr/bin/env python3
"""
TCP-Nexus Server
Multi-client, multi-room TCP chat server.
Standard library only.
"""

import argparse
import json
import socket
import threading
from datetime import datetime


class ChatServer:
    def __init__(self, host="0.0.0.0", port=5000):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = threading.Event()
        self.lock = threading.RLock()

        self.clients = {}       # username -> socket
        self.usernames = {}     # socket -> username
        self.rooms = {"lobby": set()}
        self.user_rooms = {}    # username -> room or None

    @staticmethod
    def now():
        return datetime.now().strftime("%H:%M")

    @staticmethod
    def send_json(sock, payload):
        try:
            sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            return True
        except OSError:
            return False

    def send_to_user(self, username, payload):
        with self.lock:
            sock = self.clients.get(username)
        return bool(sock and self.send_json(sock, payload))

    def broadcast_room(self, room, payload, exclude=None):
        with self.lock:
            members = list(self.rooms.get(room, set()))
        for username in members:
            if username != exclude:
                self.send_to_user(username, payload)

    def broadcast_user_list(self):
        with self.lock:
            users = sorted(self.clients.keys())
        payload = {"type": "users", "users": users}
        for username in users:
            self.send_to_user(username, payload)

    def register_username(self, sock, username):
        username = username.strip()

        if not username:
            self.send_json(sock, {"type": "login_error", "message": "Username cannot be empty."})
            return False

        if len(username) > 30:
            self.send_json(sock, {"type": "login_error", "message": "Username is too long."})
            return False

        if not username.replace("_", "").replace("-", "").isalnum():
            self.send_json(sock, {
                "type": "login_error",
                "message": "Use letters, numbers, underscores or hyphens only."
            })
            return False

        with self.lock:
            if username in self.clients:
                self.send_json(sock, {"type": "login_error", "message": "Username already in use."})
                return False

            self.clients[username] = sock
            self.usernames[sock] = username
            self.user_rooms[username] = None

        self.send_json(sock, {
            "type": "login_ok",
            "username": username,
            "message": f"Welcome, {username}!"
        })
        self.join_room(username, "lobby")
        self.broadcast_user_list()
        return True

    def create_room(self, username, room):
        room = room.strip()
        if not room:
            self.send_to_user(username, {"type": "error", "message": "Room name cannot be empty."})
            return

        with self.lock:
            if room in self.rooms:
                self.send_to_user(username, {"type": "error", "message": f"Room '{room}' already exists."})
                return
            self.rooms[room] = set()

        self.send_to_user(username, {"type": "system", "message": f"Room '{room}' created."})
        self.list_rooms(username)

    def join_room(self, username, room):
        room = room.strip()
        if not room:
            return

        with self.lock:
            self.rooms.setdefault(room, set())
            old_room = self.user_rooms.get(username)

            if old_room == room:
                self.send_to_user(username, {
                    "type": "joined", "room": room,
                    "message": f"You are already in '{room}'."
                })
                return

            if old_room:
                self.rooms.get(old_room, set()).discard(username)

            self.rooms[room].add(username)
            self.user_rooms[username] = room

        if old_room:
            self.broadcast_room(old_room, {
                "type": "system",
                "room": old_room,
                "message": f"{username} left the room."
            }, exclude=username)

        self.send_to_user(username, {
            "type": "joined",
            "room": room,
            "message": f"Joined room '{room}'."
        })
        self.broadcast_room(room, {
            "type": "system",
            "room": room,
            "message": f"{username} joined the room."
        }, exclude=username)

    def leave_room(self, username):
        with self.lock:
            room = self.user_rooms.get(username)
            if not room:
                self.send_to_user(username, {"type": "error", "message": "You are not in a room."})
                return
            self.rooms.get(room, set()).discard(username)
            self.user_rooms[username] = None

        self.send_to_user(username, {
            "type": "left",
            "room": room,
            "message": f"Left room '{room}'."
        })
        self.broadcast_room(room, {
            "type": "system",
            "room": room,
            "message": f"{username} left the room."
        })

    def list_rooms(self, username):
        with self.lock:
            rooms = [
                {"name": name, "users": len(members)}
                for name, members in sorted(self.rooms.items())
            ]
        self.send_to_user(username, {"type": "rooms", "rooms": rooms})

    def list_users(self, username):
        with self.lock:
            users = sorted(self.clients.keys())
        self.send_to_user(username, {"type": "users", "users": users})

    def room_message(self, username, text):
        text = text.strip()
        if not text:
            return

        with self.lock:
            room = self.user_rooms.get(username)

        if not room:
            self.send_to_user(username, {"type": "error", "message": "Join a room first."})
            return

        self.broadcast_room(room, {
            "type": "message",
            "room": room,
            "from": username,
            "message": text,
            "timestamp": self.now()
        })

    def private_message(self, sender, recipient, text):
        recipient = recipient.strip()
        text = text.strip()

        with self.lock:
            exists = recipient in self.clients

        if not exists:
            self.send_to_user(sender, {
                "type": "error",
                "message": f"User '{recipient}' is not online."
            })
            return

        payload = {
            "type": "private",
            "from": sender,
            "to": recipient,
            "message": text,
            "timestamp": self.now()
        }
        self.send_to_user(recipient, payload)

        if recipient != sender:
            self.send_to_user(sender, {
                "type": "private_sent",
                "from": sender,
                "to": recipient,
                "message": text,
                "timestamp": self.now()
            })

    def process_message(self, username, payload):
        t = str(payload.get("type", "")).lower()

        if t == "join":
            self.join_room(username, str(payload.get("room", "")))
        elif t == "create":
            self.create_room(username, str(payload.get("room", "")))
        elif t == "leave":
            self.leave_room(username)
        elif t == "rooms":
            self.list_rooms(username)
        elif t == "users":
            self.list_users(username)
        elif t == "msg":
            self.room_message(username, str(payload.get("message", "")))
        elif t == "pm":
            self.private_message(
                username,
                str(payload.get("to", "")),
                str(payload.get("message", ""))
            )
        elif t == "quit":
            raise ConnectionAbortedError
        else:
            self.send_to_user(username, {"type": "error", "message": f"Unknown type: {t}"})

    def remove_client(self, sock):
        with self.lock:
            username = self.usernames.pop(sock, None)
            if not username:
                try:
                    sock.close()
                except OSError:
                    pass
                return

            room = self.user_rooms.pop(username, None)
            self.clients.pop(username, None)

            if room:
                self.rooms.get(room, set()).discard(username)

        if room:
            self.broadcast_room(room, {
                "type": "system",
                "room": room,
                "message": f"{username} disconnected."
            })

        try:
            sock.close()
        except OSError:
            pass

        print(f"[DISCONNECTED] {username}")
        self.broadcast_user_list()

    def handle_client(self, sock, address):
        print(f"[CONNECTED] {address}")
        username = None
        buffer = ""

        try:
            while self.running.is_set():
                data = sock.recv(4096)
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
                        self.send_json(sock, {"type": "error", "message": "Invalid JSON."})
                        continue

                    if username is None:
                        if str(payload.get("type", "")).lower() != "login":
                            self.send_json(sock, {"type": "login_error", "message": "Login required first."})
                            continue
                        requested = str(payload.get("username", "")).strip()
                        if self.register_username(sock, requested):
                            username = requested
                    else:
                        self.process_message(username, payload)

        except (OSError, ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        finally:
            self.remove_client(sock)

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.running.set()

        print("=" * 60)
        print("TCP-Nexus Server")
        print(f"Listening on {self.host}:{self.port}")
        print("=" * 60)

        try:
            while self.running.is_set():
                client, address = self.server_socket.accept()
                threading.Thread(
                    target=self.handle_client,
                    args=(client, address),
                    daemon=True
                ).start()
        except KeyboardInterrupt:
            print("\n[SERVER] Shutting down...")
        finally:
            self.stop()

    def stop(self):
        self.running.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass

        with self.lock:
            sockets = list(self.clients.values())

        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass


def parse_args():
    parser = argparse.ArgumentParser(description="TCP-Nexus server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ChatServer(args.host, args.port).start()
