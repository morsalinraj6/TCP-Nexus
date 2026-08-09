import argparse
import json
import socket
import threading
from typing import Dict, Optional, Set


class ChatServer:
    """Threaded TCP chat server supporting rooms and private messages."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5000) -> None:
        self.host = host
        self.port = port

        self.server_socket: Optional[socket.socket] = None
        self.running = threading.Event()

        # Shared state protected by a lock.
        self.lock = threading.RLock()

        # username -> client socket
        self.clients: Dict[str, socket.socket] = {}

        # client socket -> username
        self.usernames: Dict[socket.socket, str] = {}

        # room name -> set of usernames
        self.rooms: Dict[str, Set[str]] = {"lobby": set()}

        # username -> current room, or None
        self.user_rooms: Dict[str, Optional[str]] = {}

    # ------------------------------------------------------------------
    # Socket / protocol helpers
    # ------------------------------------------------------------------
    @staticmethod
    def send_json(sock: socket.socket, payload: dict) -> bool:
        """Send one newline-delimited JSON message."""
        try:
            data = json.dumps(payload, ensure_ascii=False) + "\n"
            sock.sendall(data.encode("utf-8"))
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def send_to_user(self, username: str, payload: dict) -> bool:
        """Send a message to one connected user."""
        with self.lock:
            sock = self.clients.get(username)
        if not sock:
            return False
        return self.send_json(sock, payload)

    def broadcast_room(
        self,
        room: str,
        payload: dict,
        exclude: Optional[str] = None,
    ) -> None:
        """Broadcast a payload to all currently connected users in a room."""
        with self.lock:
            members = list(self.rooms.get(room, set()))

        for username in members:
            if username == exclude:
                continue
            self.send_to_user(username, payload)

    # ------------------------------------------------------------------
    # Room management
    # ------------------------------------------------------------------
    def create_room(self, room: str) -> bool:
        """Create a room if it does not already exist."""
        with self.lock:
            if room in self.rooms:
                return False
            self.rooms[room] = set()
            return True

    def join_room(self, username: str, room: str) -> None:
        """Move a user into the requested room, creating it if necessary."""
        room = room.strip()

        if not room:
            self.send_to_user(
                username,
                {"type": "error", "message": "Room name cannot be empty."},
            )
            return

        if len(room) > 40:
            self.send_to_user(
                username,
                {"type": "error", "message": "Room name is too long."},
            )
            return

        with self.lock:
            if room not in self.rooms:
                self.rooms[room] = set()

            previous_room = self.user_rooms.get(username)

            if previous_room == room:
                self.send_to_user(
                    username,
                    {
                        "type": "system",
                        "message": f"You are already in room '{room}'.",
                    },
                )
                return

            if previous_room and previous_room in self.rooms:
                self.rooms[previous_room].discard(username)

            self.rooms[room].add(username)
            self.user_rooms[username] = room

        if previous_room:
            self.broadcast_room(
                previous_room,
                {
                    "type": "system",
                    "message": f"{username} left the room.",
                    "room": previous_room,
                },
                exclude=username,
            )

        self.send_to_user(
            username,
            {
                "type": "joined",
                "room": room,
                "message": f"Joined room '{room}'.",
            },
        )

        self.broadcast_room(
            room,
            {
                "type": "system",
                "message": f"{username} joined the room.",
                "room": room,
            },
            exclude=username,
        )

    def leave_room(self, username: str) -> None:
        """Remove a user from their current room."""
        with self.lock:
            room = self.user_rooms.get(username)

            if not room:
                self.send_to_user(
                    username,
                    {"type": "error", "message": "You are not in a room."},
                )
                return

            self.rooms.get(room, set()).discard(username)
            self.user_rooms[username] = None

        self.send_to_user(
            username,
            {
                "type": "left",
                "room": room,
                "message": f"Left room '{room}'.",
            },
        )

        self.broadcast_room(
            room,
            {
                "type": "system",
                "message": f"{username} left the room.",
                "room": room,
            },
        )

    def list_rooms(self, username: str) -> None:
        """Return all rooms and their current member counts."""
        with self.lock:
            rooms = [
                {"name": room, "users": len(members)}
                for room, members in sorted(self.rooms.items())
            ]

        self.send_to_user(username, {"type": "rooms", "rooms": rooms})

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------
    def handle_room_message(self, username: str, text: str) -> None:
        """Broadcast a normal chat message to the sender's current room."""
        text = text.strip()

        if not text:
            return

        if len(text) > 4000:
            self.send_to_user(
                username,
                {"type": "error", "message": "Message is too long."},
            )
            return

        with self.lock:
            room = self.user_rooms.get(username)

        if not room:
            self.send_to_user(
                username,
                {
                    "type": "error",
                    "message": "Join a room before sending messages.",
                },
            )
            return

        self.broadcast_room(
            room,
            {
                "type": "message",
                "room": room,
                "from": username,
                "message": text,
            },
        )

    def handle_private_message(
        self,
        sender: str,
        recipient: str,
        text: str,
    ) -> None:
        """Send a private message to one connected user."""
        recipient = recipient.strip()
        text = text.strip()

        if not recipient or not text:
            self.send_to_user(
                sender,
                {
                    "type": "error",
                    "message": "Private message requires a username and message.",
                },
            )
            return

        with self.lock:
            recipient_exists = recipient in self.clients

        if not recipient_exists:
            self.send_to_user(
                sender,
                {
                    "type": "error",
                    "message": f"User '{recipient}' is not online.",
                },
            )
            return

        payload = {
            "type": "private",
            "from": sender,
            "to": recipient,
            "message": text,
        }

        self.send_to_user(recipient, payload)

        # Echo to sender so the sender can see confirmation in their client.
        if recipient != sender:
            self.send_to_user(
                sender,
                {
                    "type": "private_sent",
                    "from": sender,
                    "to": recipient,
                    "message": text,
                },
            )

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------
    def register_username(self, sock: socket.socket, username: str) -> bool:
        """Register a unique username for a socket."""
        username = username.strip()

        if not username:
            self.send_json(
                sock,
                {"type": "login_error", "message": "Username cannot be empty."},
            )
            return False

        if len(username) > 30:
            self.send_json(
                sock,
                {"type": "login_error", "message": "Username is too long."},
            )
            return False

        if not username.replace("_", "").replace("-", "").isalnum():
            self.send_json(
                sock,
                {
                    "type": "login_error",
                    "message": (
                        "Username may contain letters, numbers, "
                        "underscores, and hyphens only."
                    ),
                },
            )
            return False

        with self.lock:
            if username in self.clients:
                self.send_json(
                    sock,
                    {
                        "type": "login_error",
                        "message": "That username is already connected.",
                    },
                )
                return False

            self.clients[username] = sock
            self.usernames[sock] = username
            self.user_rooms[username] = None

        self.send_json(
            sock,
            {
                "type": "login_ok",
                "username": username,
                "message": f"Welcome to TCP-Nexus, {username}!",
            },
        )

        # Automatically join lobby after successful login.
        self.join_room(username, "lobby")
        return True

    def process_message(self, username: str, payload: dict) -> None:
        """Route one protocol message from a logged-in client."""
        msg_type = str(payload.get("type", "")).lower()

        if msg_type == "join":
            self.join_room(username, str(payload.get("room", "")))

        elif msg_type == "leave":
            self.leave_room(username)

        elif msg_type == "rooms":
            self.list_rooms(username)

        elif msg_type == "create":
            room = str(payload.get("room", "")).strip()
            if not room:
                self.send_to_user(
                    username,
                    {"type": "error", "message": "Room name cannot be empty."},
                )
                return

            created = self.create_room(room)
            if created:
                self.send_to_user(
                    username,
                    {
                        "type": "system",
                        "message": f"Created room '{room}'.",
                    },
                )
            else:
                self.send_to_user(
                    username,
                    {
                        "type": "error",
                        "message": f"Room '{room}' already exists.",
                    },
                )

        elif msg_type == "msg":
            self.handle_room_message(
                username,
                str(payload.get("message", "")),
            )

        elif msg_type == "pm":
            self.handle_private_message(
                username,
                str(payload.get("to", "")),
                str(payload.get("message", "")),
            )

        elif msg_type == "quit":
            # The handler loop will stop after this exception.
            raise ConnectionAbortedError("Client requested quit.")

        else:
            self.send_to_user(
                username,
                {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type!r}",
                },
            )

    def remove_client(self, sock: socket.socket) -> None:
        """Remove a disconnected client from all server state."""
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

            if room and room in self.rooms:
                self.rooms[room].discard(username)

        if room:
            self.broadcast_room(
                room,
                {
                    "type": "system",
                    "message": f"{username} disconnected.",
                    "room": room,
                },
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

    def handle_client(
        self,
        client_socket: socket.socket,
        address,
    ) -> None:
        """Handle one client connection in its own thread."""
        print(f"[CONNECTED] {address}")

        username: Optional[str] = None
        buffer = ""

        try:
            client_socket.settimeout(None)

            while self.running.is_set():
                data = client_socket.recv(4096)

                if not data:
                    break

                buffer += data.decode("utf-8")

                # Newline-delimited JSON framing.
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        self.send_json(
                            client_socket,
                            {
                                "type": "error",
                                "message": "Invalid JSON message.",
                            },
                        )
                        continue

                    if not isinstance(payload, dict):
                        self.send_json(
                            client_socket,
                            {
                                "type": "error",
                                "message": "JSON message must be an object.",
                            },
                        )
                        continue

                    # First valid action must be login.
                    if username is None:
                        if str(payload.get("type", "")).lower() != "login":
                            self.send_json(
                                client_socket,
                                {
                                    "type": "login_error",
                                    "message": "Login is required first.",
                                },
                            )
                            continue

                        requested_username = str(
                            payload.get("username", "")
                        )

                        if self.register_username(
                            client_socket,
                            requested_username,
                        ):
                            username = requested_username.strip()
                        else:
                            # Keep connection alive so user may try another name.
                            continue
                    else:
                        self.process_message(username, payload)

        except (
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            UnicodeDecodeError,
            OSError,
        ):
            pass
        finally:
            self.remove_client(client_socket)

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start listening and accepting clients."""
        self.server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        self.server_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        self.running.set()

        actual_host, actual_port = self.server_socket.getsockname()

        print("=" * 60)
        print("TCP-Nexus Server")
        print(f"Listening on {actual_host}:{actual_port}")
        print("Press Ctrl+C to stop the server.")
        print("=" * 60)

        try:
            while self.running.is_set():
                try:
                    client_socket, address = self.server_socket.accept()
                except OSError:
                    break

                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True,
                )
                thread.start()

        except KeyboardInterrupt:
            print("\n[SERVER] Shutdown requested.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop server and disconnect all active clients."""
        if not self.running.is_set():
            return

        self.running.clear()

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass

        with self.lock:
            active_sockets = list(self.clients.values())

        for sock in active_sockets:
            self.send_json(
                sock,
                {
                    "type": "system",
                    "message": "Server is shutting down.",
                },
            )
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

        print("[SERVER] Stopped.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="TCP-Nexus multi-room TCP chat server"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host/IP address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="TCP port to listen on (default: 5000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    server = ChatServer(host=args.host, port=args.port)
    server.start()