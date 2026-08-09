import argparse
import json
import socket
import threading
import uuid
from datetime import datetime
from typing import Dict, Optional, Set


class ChatServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port

        self.server_socket: Optional[socket.socket] = None
        self.running = threading.Event()
        self.lock = threading.RLock()

        # username -> socket
        self.clients: Dict[str, socket.socket] = {}

        # socket -> username
        self.usernames: Dict[socket.socket, str] = {}

        # room -> usernames
        self.rooms: Dict[str, Set[str]] = {"lobby": set()}

        # username -> current room
        self.user_rooms: Dict[str, Optional[str]] = {}

        # message_id -> metadata
        self.messages: Dict[str, dict] = {}

    @staticmethod
    def now() -> str:
        return datetime.now().strftime("%H:%M")

    @staticmethod
    def new_message_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def send_json(sock: socket.socket, payload: dict) -> bool:
        try:
            raw = json.dumps(payload, ensure_ascii=False) + "\n"
            sock.sendall(raw.encode("utf-8"))
            return True
        except (OSError, BrokenPipeError, ConnectionResetError):
            return False

    def send_to_user(self, username: str, payload: dict) -> bool:
        with self.lock:
            sock = self.clients.get(username)

        if not sock:
            return False

        return self.send_json(sock, payload)

    def broadcast_room(
        self,
        room: str,
        payload: dict,
        exclude: Optional[str] = None
    ):
        with self.lock:
            members = list(self.rooms.get(room, set()))

        for username in members:
            if username != exclude:
                self.send_to_user(username, payload)

    def broadcast_users(self):
        """Push latest online user list to every connected client."""
        with self.lock:
            users = sorted(self.clients.keys())

        payload = {
            "type": "users",
            "users": users
        }

        for username in users:
            self.send_to_user(username, payload)

    # ============================================================
    # Login
    # ============================================================

    def register_username(self, sock: socket.socket, username: str) -> bool:
        username = username.strip()

        if not username:
            self.send_json(sock, {
                "type": "login_error",
                "message": "Username cannot be empty."
            })
            return False

        if len(username) > 30:
            self.send_json(sock, {
                "type": "login_error",
                "message": "Username is too long."
            })
            return False

        if not username.replace("_", "").replace("-", "").isalnum():
            self.send_json(sock, {
                "type": "login_error",
                "message": "Use only letters, numbers, underscores and hyphens."
            })
            return False

        with self.lock:
            if username in self.clients:
                self.send_json(sock, {
                    "type": "login_error",
                    "message": "This username is already online."
                })
                return False

            self.clients[username] = sock
            self.usernames[sock] = username
            self.user_rooms[username] = None

        self.send_json(sock, {
            "type": "login_ok",
            "username": username,
            "message": f"Welcome to TCP-Nexus, {username}!"
        })

        # Auto join lobby
        self.join_room(username, "lobby")

        # IMPORTANT:
        # Send updated online list to everyone after login.
        self.broadcast_users()

        return True

    # ============================================================
    # Rooms
    # ============================================================

    def create_room(self, username: str, room: str):
        room = room.strip()

        if not room:
            self.send_to_user(username, {
                "type": "error",
                "message": "Room name cannot be empty."
            })
            return

        if len(room) > 40:
            self.send_to_user(username, {
                "type": "error",
                "message": "Room name is too long."
            })
            return

        with self.lock:
            if room in self.rooms:
                self.send_to_user(username, {
                    "type": "error",
                    "message": f"Room '{room}' already exists."
                })
                return

            self.rooms[room] = set()

        self.send_to_user(username, {
            "type": "system",
            "message": f"Room '{room}' created."
        })

        self.broadcast_rooms()

    def broadcast_rooms(self):
        """Push updated room list to all online users."""
        with self.lock:
            rooms = [
                {"name": name, "users": len(members)}
                for name, members in sorted(self.rooms.items())
            ]
            usernames = list(self.clients.keys())

        payload = {
            "type": "rooms",
            "rooms": rooms
        }

        for username in usernames:
            self.send_to_user(username, payload)

    def join_room(self, username: str, room: str):
        room = room.strip()

        if not room:
            return

        with self.lock:
            self.rooms.setdefault(room, set())
            old_room = self.user_rooms.get(username)

            if old_room == room:
                self.send_to_user(username, {
                    "type": "joined",
                    "room": room,
                    "message": f"You are already in '{room}'."
                })
                return

            if old_room:
                self.rooms.get(old_room, set()).discard(username)

            self.rooms[room].add(username)
            self.user_rooms[username] = room

        if old_room:
            self.broadcast_room(
                old_room,
                {
                    "type": "system",
                    "room": old_room,
                    "message": f"{username} left the room."
                },
                exclude=username
            )

        self.send_to_user(username, {
            "type": "joined",
            "room": room,
            "message": f"Joined room '{room}'."
        })

        self.broadcast_room(
            room,
            {
                "type": "system",
                "room": room,
                "message": f"{username} joined the room."
            },
            exclude=username
        )

        self.broadcast_rooms()

    def leave_room(self, username: str):
        with self.lock:
            room = self.user_rooms.get(username)

            if not room:
                self.send_to_user(username, {
                    "type": "error",
                    "message": "You are not in a room."
                })
                return

            self.rooms.get(room, set()).discard(username)
            self.user_rooms[username] = None

        self.send_to_user(username, {
            "type": "left",
            "room": room,
            "message": f"Left room '{room}'."
        })

        self.broadcast_room(
            room,
            {
                "type": "system",
                "room": room,
                "message": f"{username} left the room."
            }
        )

        self.broadcast_rooms()

    def list_rooms(self, username: str):
        with self.lock:
            rooms = [
                {"name": name, "users": len(members)}
                for name, members in sorted(self.rooms.items())
            ]

        self.send_to_user(username, {
            "type": "rooms",
            "rooms": rooms
        })

    def list_users(self, username: str):
        with self.lock:
            users = sorted(self.clients.keys())

        self.send_to_user(username, {
            "type": "users",
            "users": users
        })

    # ============================================================
    # Messaging
    # ============================================================

    def room_message(self, sender: str, text: str):
        text = text.strip()

        if not text:
            return

        if len(text) > 4000:
            self.send_to_user(sender, {
                "type": "error",
                "message": "Message is too long."
            })
            return

        with self.lock:
            room = self.user_rooms.get(sender)

        if not room:
            self.send_to_user(sender, {
                "type": "error",
                "message": "Join a room before sending messages."
            })
            return

        message_id = self.new_message_id()
        timestamp = self.now()

        record = {
            "id": message_id,
            "kind": "room",
            "sender": sender,
            "room": room,
            "message": text,
            "timestamp": timestamp,
            "deleted": False
        }

        with self.lock:
            self.messages[message_id] = record

        # Sender ALSO receives this event immediately.
        self.broadcast_room(room, {
            "type": "message",
            "id": message_id,
            "room": room,
            "from": sender,
            "message": text,
            "timestamp": timestamp,
            "edited": False,
            "deleted": False
        })

    def private_message(
        self,
        sender: str,
        recipient: str,
        text: str
    ):
        recipient = recipient.strip()
        text = text.strip()

        if not recipient or not text:
            self.send_to_user(sender, {
                "type": "error",
                "message": "Private message requires a user and message."
            })
            return

        if recipient == sender:
            self.send_to_user(sender, {
                "type": "error",
                "message": "You cannot send a private message to yourself."
            })
            return

        with self.lock:
            online = recipient in self.clients

        if not online:
            self.send_to_user(sender, {
                "type": "error",
                "message": f"User '{recipient}' is not online."
            })
            return

        message_id = self.new_message_id()
        timestamp = self.now()

        record = {
            "id": message_id,
            "kind": "private",
            "sender": sender,
            "recipient": recipient,
            "message": text,
            "timestamp": timestamp,
            "deleted": False
        }

        with self.lock:
            self.messages[message_id] = record

        payload = {
            "type": "private",
            "id": message_id,
            "from": sender,
            "to": recipient,
            "message": text,
            "timestamp": timestamp,
            "edited": False,
            "deleted": False
        }

        # Receiver
        self.send_to_user(recipient, payload)

        # Sender
        self.send_to_user(sender, payload)

    # ============================================================
    # Edit / Delete
    # ============================================================

    def edit_message(
        self,
        username: str,
        message_id: str,
        new_text: str
    ):
        new_text = new_text.strip()

        if not new_text:
            self.send_to_user(username, {
                "type": "error",
                "message": "Edited message cannot be empty."
            })
            return

        with self.lock:
            record = self.messages.get(message_id)

            if not record:
                self.send_to_user(username, {
                    "type": "error",
                    "message": "Message not found."
                })
                return

            if record["sender"] != username:
                self.send_to_user(username, {
                    "type": "error",
                    "message": "You can edit only your own messages."
                })
                return

            if record.get("deleted"):
                self.send_to_user(username, {
                    "type": "error",
                    "message": "Deleted messages cannot be edited."
                })
                return

            record["message"] = new_text
            kind = record["kind"]

        event = {
            "type": "message_edited",
            "id": message_id,
            "message": new_text,
            "edited": True,
            "timestamp": self.now()
        }

        if kind == "room":
            event["room"] = record["room"]
            self.broadcast_room(record["room"], event)
        else:
            event["from"] = record["sender"]
            event["to"] = record["recipient"]

            self.send_to_user(record["sender"], event)
            self.send_to_user(record["recipient"], event)

    def delete_message(self, username: str, message_id: str):
        with self.lock:
            record = self.messages.get(message_id)

            if not record:
                self.send_to_user(username, {
                    "type": "error",
                    "message": "Message not found."
                })
                return

            if record["sender"] != username:
                self.send_to_user(username, {
                    "type": "error",
                    "message": "You can delete only your own messages."
                })
                return

            if record.get("deleted"):
                return

            record["deleted"] = True
            kind = record["kind"]

        event = {
            "type": "message_deleted",
            "id": message_id
        }

        if kind == "room":
            event["room"] = record["room"]
            self.broadcast_room(record["room"], event)
        else:
            event["from"] = record["sender"]
            event["to"] = record["recipient"]

            self.send_to_user(record["sender"], event)
            self.send_to_user(record["recipient"], event)

    # ============================================================
    # Protocol Router
    # ============================================================

    def process_message(self, username: str, payload: dict):
        msg_type = str(payload.get("type", "")).lower()

        if msg_type == "join":
            self.join_room(username, str(payload.get("room", "")))

        elif msg_type == "create":
            self.create_room(username, str(payload.get("room", "")))

        elif msg_type == "leave":
            self.leave_room(username)

        elif msg_type == "rooms":
            self.list_rooms(username)

        elif msg_type == "users":
            self.list_users(username)

        elif msg_type == "msg":
            self.room_message(
                username,
                str(payload.get("message", ""))
            )

        elif msg_type == "pm":
            self.private_message(
                username,
                str(payload.get("to", "")),
                str(payload.get("message", ""))
            )

        elif msg_type == "edit":
            self.edit_message(
                username,
                str(payload.get("id", "")),
                str(payload.get("message", ""))
            )

        elif msg_type == "delete":
            self.delete_message(
                username,
                str(payload.get("id", ""))
            )

        elif msg_type == "quit":
            raise ConnectionAbortedError("Client requested quit")

        else:
            self.send_to_user(username, {
                "type": "error",
                "message": f"Unknown protocol message: {msg_type}"
            })

    # ============================================================
    # Client lifecycle
    # ============================================================

    def remove_client(self, sock: socket.socket):
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
            self.broadcast_room(
                room,
                {
                    "type": "system",
                    "room": room,
                    "message": f"{username} disconnected."
                }
            )

        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            sock.close()
        except OSError:
            pass

        print(f"[DISCONNECTED] {username}")

        # IMPORTANT:
        # Push latest online list and room counts after disconnect.
        self.broadcast_users()
        self.broadcast_rooms()

    def handle_client(self, sock: socket.socket, address):
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
                        self.send_json(sock, {
                            "type": "error",
                            "message": "Invalid JSON."
                        })
                        continue

                    if not isinstance(payload, dict):
                        continue

                    if username is None:
                        if str(payload.get("type", "")).lower() != "login":
                            self.send_json(sock, {
                                "type": "login_error",
                                "message": "Login is required first."
                            })
                            continue

                        requested = str(
                            payload.get("username", "")
                        ).strip()

                        if self.register_username(sock, requested):
                            username = requested
                    else:
                        self.process_message(username, payload)

        except (
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            UnicodeDecodeError,
            OSError
        ):
            pass

        finally:
            self.remove_client(sock)

    # ============================================================
    # Server lifecycle
    # ============================================================

    def start(self):
        self.server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.running.set()

        print("=" * 62)
        print("TCP-Nexus Server")
        print(f"Listening on {self.host}:{self.port}")
        print("Press Ctrl+C to stop.")
        print("=" * 62)

        try:
            while self.running.is_set():
                client, address = self.server_socket.accept()

                threading.Thread(
                    target=self.handle_client,
                    args=(client, address),
                    daemon=True
                ).start()

        except KeyboardInterrupt:
            print("\n[SERVER] Shutdown requested.")

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
    parser = argparse.ArgumentParser(
        description="TCP-Nexus TCP chat server"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5000
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ChatServer(args.host, args.port).start()