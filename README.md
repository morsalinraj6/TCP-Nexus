# 💬 TCP-Nexus

<p align="center">
  <b>Professional Real-Time Multi-User & Multi-Room Chat Application Using TCP/IP Socket Programming</b>
</p>

<p align="center">
  Python • TCP/IP • Socket • Threading • Tkinter • JSON Protocol
</p>

---

## 📌 Project Overview

**TCP-Nexus** is a professional real-time human-to-human chat application developed with **Python TCP socket programming**.

The system uses a centralized **client-server architecture** where multiple users can connect simultaneously, join chat rooms, exchange group messages, send private messages, and manage their own messages through a modern desktop GUI.

The project is designed to demonstrate both **Computer Networking** and **Software Engineering** concepts in a practical application.

### Main Capabilities

- 👥 Multiple concurrent users
- 💬 Real-time room/group chat
- 🔐 Private one-to-one messaging
- 🏠 Multiple chat rooms
- 🖥️ WhatsApp-inspired Tkinter GUI
- ⚡ Full-duplex TCP communication
- 🧵 Multithreaded client/server design
- 📨 Newline-delimited JSON protocol
- 🆔 Unique message IDs
- ✏️ Edit own messages
- 🗑️ Delete own messages for everyone
- 🟢 Online user list
- 🔄 Graceful disconnect handling

---

# ✨ Key Features

## 👤 User Login

Users connect using a unique username.

The server prevents duplicate usernames from being active at the same time.

Example:

```text
Username: Alice
Server IP: 127.0.0.1
Port: 5000
```

---

## 🖥️ Professional Visual Interface

TCP-Nexus provides a modern desktop GUI inspired by popular messaging applications.

The interface contains:

- Login screen
- Room sidebar
- Online users list
- Chat header
- Real-time message area
- Message input box
- Send button
- Create Room button
- Join / Leave buttons
- Private Chat button
- Search/filter field
- Connection status
- Message timestamps
- Chat bubbles
- Edit/Delete menu

Example layout:

```text
+-----------------------------------------------------------------------+
| TCP-Nexus                                        @Alice  ● Connected |
+----------------------+------------------------------------------------+
| Search...            | # networking                                  |
|                      | Group chat • TCP room                          |
| ROOMS                +------------------------------------------------+
| # lobby       (1)    |                                                |
| # networking  (3)    | Bob: Hello!                                    |
| # programming (2)    |                                                |
|                      |                     Hi Bob!   10:42 ✓✓          |
| ONLINE USERS         |                                                |
| ● Bob                | Carol: TCP project looks good.                 |
| ● Carol              |                                                |
| ● David              |                                                |
|                      |                                                |
| [Private Chat]       +------------------------------------------------+
|                      | Type a message...                     [Send]    |
+----------------------+------------------------------------------------+
```

---

# 💬 Real-Time Group Chat

Multiple users can join the same room and communicate live.

Example:

```text
Alice ─────┐
           │
Bob ───────┼────> TCP-Nexus Server ─────> #networking
           │
Carol ─────┘
```

If Alice sends:

```text
Hello everyone!
```

the server immediately broadcasts the same message event to all users in that room, including Alice.

This fixes sender-side delay and ensures the message appears immediately on both sender and receiver interfaces.

---

# 🔐 Private Messaging

Users can select another online user from the sidebar and open a private conversation.

No terminal command is required.

Example:

```text
Alice  <──── TCP Server ────>  Bob
```

A private message is delivered immediately to both:

- Receiver
- Sender's own chat view

Other users cannot see that private message.

---

# ✏️ Edit Message

Each message gets a unique server-generated message ID.

The sender can open the message menu:

```text
⋮
├── Edit message
└── Delete for everyone
```

When the sender edits a message:

```text
Original:
Hello Bob

Edited:
Hello Bob, how are you?
```

the server sends a `message_edited` event to all relevant clients.

The message updates live on both sides.

Only the original sender can edit the message.

---

# 🗑️ Delete for Everyone

Users can delete their own messages.

After deletion, both sender and receiver see:

```text
This message was deleted
```

The server validates message ownership before allowing deletion.

Deleted messages cannot be edited again.

---

# 🆔 Unique Message IDs

Every room and private message gets a unique ID.

Example:

```json
{
  "id": "a91f82bd3c41",
  "type": "message",
  "from": "Alice",
  "room": "networking",
  "message": "Hello everyone!",
  "timestamp": "10:42"
}
```

Message IDs are used for:

- Edit operations
- Delete operations
- Duplicate prevention
- Synchronizing message updates across clients

---

# 🏗️ System Architecture

TCP-Nexus follows a centralized **Client-Server Architecture**.

```text
                         TCP/IP NETWORK

       +------------------+       +------------------+
       |   Alice Client   |------>|                  |
       +------------------+  TCP  |                  |
                                  |                  |
       +------------------+       |    TCP-NEXUS     |
       |    Bob Client    |------>|      SERVER      |
       +------------------+  TCP  |                  |
                                  |    Port: 5000    |
       +------------------+       |                  |
       |   Carol Client   |------>|                  |
       +------------------+  TCP  +------------------+
```

The server is responsible for:

1. Creating the TCP socket
2. Binding IP + port
3. Listening for connections
4. Accepting clients
5. Starting a thread per connected client
6. Managing usernames
7. Managing rooms
8. Broadcasting group messages
9. Routing private messages
10. Processing edit/delete events
11. Removing disconnected clients safely

---

# 🌐 TCP/IP Model Demonstration

TCP-Nexus directly demonstrates the TCP/IP networking model.

| TCP/IP Layer | TCP-Nexus Implementation |
|---|---|
| **Application Layer** | JSON protocol, login, room chat, PM, edit, delete |
| **Transport Layer** | TCP sockets, Port 5000, reliable full-duplex communication |
| **Internet Layer** | IPv4 addressing such as `127.0.0.1` or LAN IP |
| **Network Access Layer** | Wi-Fi / Ethernet / LAN |

---

## Application Layer

TCP-Nexus implements its own custom JSON-based application protocol.

Examples:

```json
{"type":"login","username":"Alice"}
```

```json
{"type":"msg","message":"Hello everyone!"}
```

```json
{"type":"pm","to":"Bob","message":"Private message"}
```

```json
{"type":"edit","id":"a91f82bd3c41","message":"Edited message"}
```

```json
{"type":"delete","id":"a91f82bd3c41"}
```

---

## Transport Layer

The project uses **TCP** because TCP provides:

- Reliable data delivery
- Ordered byte stream
- Connection-oriented communication
- Error recovery
- Full-duplex communication
- Retransmission when required

---

## Internet Layer

Clients connect using the server IP address.

Examples:

```text
127.0.0.1
192.168.0.105
192.168.1.20
```

---

## Network Access Layer

Actual network transmission occurs through technologies such as:

```text
Wi-Fi
Ethernet
LAN
```

---

# 🔄 Full-Duplex Communication

The client can send and receive at the same time.

```text
                 TCP-Nexus Client
                       |
              +--------+--------+
              |                 |
              v                 v
         GUI/Main Thread   Receiver Thread
              |                 |
              v                 v
        socket.sendall()    socket.recv()
              |                 |
              +--------+--------+
                       |
                    TCP Socket
```

The background receiver thread allows incoming messages to appear without freezing the GUI.

---

# 🧵 Server Concurrency

The server uses Python's `threading` module.

```text
                     Main Server Thread
                            |
                         accept()
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
  Client Thread 1     Client Thread 2     Client Thread 3
      Alice                Bob                Carol
```

Each connected client is handled independently.

---

# 📡 Custom Application Protocol

TCP-Nexus uses **newline-delimited JSON**.

Message framing:

```text
JSON_OBJECT + "\n"
```

Example:

```text
{"type":"msg","message":"Hello"}\n
```

Because TCP is a byte-stream protocol, the newline delimiter helps the application identify complete JSON messages.

---

# 📋 Supported Protocol Types

## Client → Server

| Type | Purpose |
|---|---|
| `login` | Login with username |
| `join` | Join a room |
| `create` | Create a room |
| `leave` | Leave current room |
| `rooms` | Request room list |
| `users` | Request online user list |
| `msg` | Send room message |
| `pm` | Send private message |
| `edit` | Edit own message |
| `delete` | Delete own message |
| `quit` | Disconnect |

## Server → Client

| Type | Purpose |
|---|---|
| `login_ok` | Login accepted |
| `login_error` | Login rejected |
| `joined` | Room joined |
| `left` | Room left |
| `rooms` | Room list |
| `users` | Online users |
| `message` | Group/room message |
| `private` | Private message |
| `message_edited` | Message update event |
| `message_deleted` | Message deletion event |
| `system` | System notification |
| `error` | Error response |

---

# 📁 Project Structure

```text
TCP-Nexus/
│
├── server/
│   └── server.py
│
├── client/
│   └── client.py
│
├── README.md
│
└── requirements.txt
```

---

# 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3 |
| Networking | TCP/IP |
| Socket API | Python `socket` |
| Concurrency | Python `threading` |
| GUI | Tkinter |
| Data Format | JSON |
| Message Framing | Newline-delimited JSON |
| Message IDs | UUID-based IDs |
| Version Control | Git |
| Repository Hosting | GitHub |

---

# 🚀 Setup & Run

## 1. Open the Project

Open the `TCP-Nexus` folder in VS Code.

Example path:

```text
C:\Users\HP\OneDrive\Desktop\TCP-Nexus
```

---

## 2. Check Python

On Windows:

```powershell
py --version
```

Example:

```text
Python 3.14.3
```

---

## 3. Start the Server

Open VS Code terminal:

```powershell
py server\server.py
```

Expected output:

```text
==============================================================
TCP-Nexus Server
Listening on 0.0.0.0:5000
Press Ctrl+C to stop.
==============================================================
```

Keep this terminal running.

---

## 4. Start Client 1

Open another terminal:

```powershell
py client\client.py
```

A graphical login window will open.

Example:

```text
Username: Alice
Server IP: 127.0.0.1
Port: 5000
```

Click:

```text
CONNECT
```

---

## 5. Start Client 2

Open another terminal:

```powershell
py client\client.py
```

Login as:

```text
Bob
```

Now two GUI windows are connected to the same TCP server.

---

# 👥 How to Test Group Chat

1. Start Alice
2. Start Bob
3. Select the same room on both clients
4. Click **Join**
5. Send a message

Example:

```text
Alice:
Hello Bob!
```

Bob should receive the message immediately.

Alice should also see her own sent message immediately.

---

# 🔐 How to Test Private Chat

1. Alice selects Bob from **ONLINE USERS**
2. Click **Private Chat**
3. Alice sends:

```text
Hello Bob, this is private.
```

Bob receives it immediately.

Alice also sees it immediately in her own private chat window.

---

# ✏️ How to Edit a Message

For your own message:

1. Click the `⋮` menu
2. Select **Edit message**
3. Change the text
4. Confirm

The updated message appears live for all relevant users.

---

# 🗑️ How to Delete a Message

For your own message:

1. Click the `⋮` menu
2. Select **Delete for everyone**
3. Confirm deletion

Both sides will see:

```text
This message was deleted
```

---

# 🌍 Connecting Two Computers on the Same Wi-Fi

Suppose the server computer IP is:

```text
192.168.0.105
```

Run server:

```powershell
py server\server.py --host 0.0.0.0 --port 5000
```

On another computer, start client:

```powershell
py client\client.py --host 192.168.0.105 --port 5000
```

Or enter the IP directly in the GUI login screen.

Requirements:

- Both devices must be on the same LAN/Wi-Fi
- TCP port `5000` must be allowed through firewall
- Client must use the server machine's LAN IP

---

# 🧪 Tested Scenarios

TCP-Nexus has been designed/tested for:

- ✅ Multiple concurrent clients
- ✅ Real-time sender-side message display
- ✅ Real-time receiver delivery
- ✅ Group chat
- ✅ Private messaging
- ✅ Multi-room support
- ✅ Online user listing
- ✅ Unique message IDs
- ✅ Edit message
- ✅ Delete for everyone
- ✅ Duplicate-message prevention
- ✅ Graceful disconnect handling
- ✅ JSON message parsing
- ✅ Full-duplex communication
- ✅ Multithreaded server handling

---

# 🛡️ Error Handling

The application handles common socket/network problems such as:

```text
ConnectionResetError
BrokenPipeError
ConnectionAbortedError
Invalid JSON
Duplicate Username
Unexpected Client Disconnect
```

A disconnected client is removed from:

- Connected user list
- Socket mapping
- Room membership
- Current-room mapping

The server continues running for other users.

---

# 🧠 Networking Concepts Demonstrated

TCP-Nexus demonstrates:

- TCP/IP Model
- TCP Socket Programming
- Client-Server Architecture
- IPv4 Addressing
- Port Numbers
- TCP Connection Management
- TCP Three-Way Handshake
- Full-Duplex Communication
- Multithreading
- Concurrent Clients
- Application-Layer Protocol Design
- JSON Serialization
- Message Framing
- Group Broadcast
- Private Message Routing
- Message Synchronization
- Unique Message Identification
- Error Handling

---

# 🔁 TCP Three-Way Handshake

Before chat data is transferred, TCP establishes a connection:

```text
CLIENT                           SERVER

   | -------- SYN ------------> |
   |                            |
   | <----- SYN + ACK --------- |
   |                            |
   | -------- ACK ------------> |
   |                            |
   |====== Connection Ready ====|
```

After the connection is established, application JSON messages can be exchanged.

---

# 📸 Screenshots

For a professional GitHub repository, create:

```text
screenshots/
├── login.png
├── main-chat.png
├── group-chat.png
├── private-chat.png
├── edit-message.png
├── delete-message.png
└── server-terminal.png
```

Then add them to this README:

```markdown
![Login Screen](screenshots/login.png)

![Main Chat](screenshots/main-chat.png)

![Group Chat](screenshots/group-chat.png)

![Private Chat](screenshots/private-chat.png)
```

---

# 🔮 Future Improvements

Possible future extensions:

- 🔐 Password authentication
- 🗄️ SQLite/PostgreSQL database
- 🔑 Password hashing
- 🔒 TLS encryption
- 📁 File transfer
- 📷 Image sharing
- 🎤 Voice messages
- 🟢 Presence status
- ⌨️ Typing indicator
- ✓ Message delivered status
- ✓✓ Read receipts
- 📜 Persistent chat history
- 👑 Admin dashboard
- 🔇 Mute users
- 🚫 Ban users
- 👢 Kick users
- ⚡ Rate limiting
- 💓 Heartbeat / timeout detection
- 🔄 Automatic reconnect
- 🖼️ Profile pictures
- 😀 Emoji picker

---

# 🎓 Final-Year Project Value

TCP-Nexus combines networking and application development in one complete project.

```text
Python
  +
TCP/IP
  +
Socket Programming
  +
Threading
  +
Tkinter GUI
  +
Custom JSON Protocol
  +
Real-Time Messaging
```

The project is suitable for:

- Final Year Project
- Networking Lab Project
- Software Engineering Project
- University Viva
- Project Defense
- GitHub Portfolio
- Internship Portfolio

---

# 📌 Suggested Project Title

> **TCP-Nexus: Design and Implementation of a Real-Time Multi-User, Multi-Room Messaging System Using TCP/IP Socket Programming**

---

# 👨‍💻 Author

**Your Name**

Department of Computer Science / Software Engineering  
Your University Name

GitHub: `https://github.com/YOUR_USERNAME`

---

## ⭐ Support

If you find this project useful, consider giving the repository a **Star ⭐**.

<p align="center">
  <b>TCP-Nexus — Real-Time Communication Powered by TCP/IP</b>
</p>
