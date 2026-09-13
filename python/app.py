"""
app.py
======
The actual local application people run (this is what gets packaged into an
.exe with PyInstaller). It's a tkinter GUI that:
  - lets you enter your username, a room code, the backend server URL, and
    your own PS3's IP
  - joins that room by polling the Vercel/KV backend for new messages
  - shows a chat box shared by everyone in the room
  - lets you request memory reads/writes from other people in the room
  - pops up a Yes/No confirmation before ever honoring an incoming request
    against YOUR OWN PS3 - nothing happens to your console without you
    clicking "Yes" in that dialog (unless you tick "auto-approve")

Build a standalone .exe with:
    pip install pyinstaller
    pyinstaller --onefile --noconsole app.py
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import requests

import ps3mapi


# --------------------------------------------------------------------------
# Background networking thread: polls the Vercel/KV backend for new events
# and pushes them onto `event_queue` - it never touches tkinter directly,
# since tkinter must only be touched from the main thread.
# --------------------------------------------------------------------------

class NetworkThread(threading.Thread):
    def __init__(self, server: str, room: str, username: str, event_queue: queue.Queue, poll_interval: float = 1.0):
        super().__init__(daemon=True)
        self.server = server.rstrip("/")
        self.room = room
        self.username = username
        self.event_queue = event_queue
        self.poll_interval = poll_interval
        self.since = 0
        self.connected = threading.Event()
        self.connect_error: str | None = None
        self._stop = threading.Event()

    def run(self):
        try:
            self._post("chat", {"from": self.username, "text": f"{self.username} joined the room."})
        except Exception as e:
            self.connect_error = str(e)
            self.connected.set()
            return

        self.connected.set()

        while not self._stop.is_set():
            try:
                resp = requests.get(
                    f"{self.server}/api/poll",
                    params={"room": self.room, "since": self.since},
                    timeout=10,
                )
                resp.raise_for_status()
                payload = resp.json()
                for item in payload.get("messages", []):
                    self.event_queue.put((item["event"], item.get("data") or {}))
                self.since = payload.get("nextSince", self.since)
            except Exception as e:
                self.event_queue.put(("_poll_error", {"error": str(e)}))
            time.sleep(self.poll_interval)

    def _post(self, event_name: str, data: dict):
        resp = requests.post(
            f"{self.server}/api/send",
            json={"room": self.room, "event": event_name, "data": data},
            timeout=10,
        )
        resp.raise_for_status()

    def publish(self, event_name: str, data: dict):
        """Fire-and-forget: safe to call from the tkinter (main) thread."""
        def _send():
            try:
                self._post(event_name, data)
            except Exception as e:
                self.event_queue.put(("_poll_error", {"error": f"send failed: {e}"}))
        threading.Thread(target=_send, daemon=True).start()

    def stop(self):
        self._stop.set()


# --------------------------------------------------------------------------
# Main application window
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PS3 Mem Relay")
        self.geometry("640x560")

        self.event_queue: queue.Queue = queue.Queue()
        self.net: NetworkThread | None = None
        self.ps3: ps3mapi.PS3MAPI | None = None
        self.username = ""
        self.auto_approve = tk.BooleanVar(value=False)

        self._build_login_frame()
        self.after(100, self._poll_queue)

    # -- login / connect screen --------------------------------------------

    def _build_login_frame(self):
        self.login_frame = ttk.Frame(self, padding=20)
        self.login_frame.pack(fill="both", expand=True)

        fields = [
            ("Backend server URL", "server", "https://your-app.vercel.app"),
            ("Room code", "room", ""),
            ("Username", "username", ""),
            ("Your PS3 IP", "ps3_ip", "192.168.1.50"),
            ("Your PS3 port", "ps3_port", "7887"),
        ]
        self.login_vars: dict[str, tk.StringVar] = {}
        for i, (label, key, default) in enumerate(fields):
            ttk.Label(self.login_frame, text=label).grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=default)
            ttk.Entry(self.login_frame, textvariable=var, width=40).grid(row=i, column=1, pady=4)
            self.login_vars[key] = var

        ttk.Checkbutton(
            self.login_frame,
            text="Auto-approve incoming memory requests (skip confirmation)",
            variable=self.auto_approve,
        ).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=8)

        self.connect_btn = ttk.Button(self.login_frame, text="Connect", command=self._on_connect)
        self.connect_btn.grid(row=len(fields) + 1, column=0, columnspan=2, pady=12)

        self.status_label = ttk.Label(self.login_frame, text="", foreground="red")
        self.status_label.grid(row=len(fields) + 2, column=0, columnspan=2)

    def _on_connect(self):
        server = self.login_vars["server"].get().strip().rstrip("/")
        room = self.login_vars["room"].get().strip().upper()
        username = self.login_vars["username"].get().strip()
        ps3_ip = self.login_vars["ps3_ip"].get().strip()
        try:
            ps3_port = int(self.login_vars["ps3_port"].get().strip())
        except ValueError:
            self.status_label.config(text="PS3 port must be a number.")
            return

        if not (server and room and username and ps3_ip):
            self.status_label.config(text="Fill in all fields.")
            return

        self.username = username
        self.connect_btn.config(state="disabled")
        self.status_label.config(text="Connecting to your PS3...", foreground="black")
        self.update_idletasks()

        try:
            self.ps3 = ps3mapi.PS3MAPI()
            self.ps3.ConnectTarget(ps3_ip, ps3_port)
        except Exception as e:
            self.status_label.config(text=f"Couldn't reach your PS3: {e}", foreground="red")
            self.connect_btn.config(state="normal")
            return

        self.status_label.config(text="Connecting to relay...")
        self.update_idletasks()

        self.net = NetworkThread(server, room, username, self.event_queue)
        self.net.start()
        self._wait_for_network_connect(room)

    def _wait_for_network_connect(self, room):
        if not self.net.connected.is_set():
            self.after(100, lambda: self._wait_for_network_connect(room))
            return
        if self.net.connect_error:
            self.status_label.config(text=f"Relay connection failed: {self.net.connect_error}", foreground="red")
            self.connect_btn.config(state="normal")
            return
        self.login_frame.destroy()
        self._build_main_frame(room)

    # -- main chat / memory panel -------------------------------------------

    def _build_main_frame(self, room):
        self.main_frame = ttk.Frame(self, padding=10)
        self.main_frame.pack(fill="both", expand=True)

        ttk.Label(
            self.main_frame, text=f"Room {room} - connected as {self.username}"
        ).pack(anchor="w")

        self.chat_log = scrolledtext.ScrolledText(self.main_frame, height=16, state="disabled", wrap="word")
        self.chat_log.pack(fill="both", expand=True, pady=(6, 6))

        chat_row = ttk.Frame(self.main_frame)
        chat_row.pack(fill="x")
        self.chat_entry = ttk.Entry(chat_row)
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.bind("<Return>", lambda e: self._send_chat())
        ttk.Button(chat_row, text="Send", command=self._send_chat).pack(side="left", padx=(6, 0))

        mem_frame = ttk.LabelFrame(self.main_frame, text="Memory panel", padding=10)
        mem_frame.pack(fill="x", pady=(12, 0))

        self.target_var = tk.StringVar()
        self.pid_var = tk.StringVar(value="0")
        self.addr_var = tk.StringVar(value="0")
        self.len_var = tk.StringVar(value="16")
        self.write_hex_var = tk.StringVar()

        def row(label, var, r, c=0):
            ttk.Label(mem_frame, text=label).grid(row=r, column=c, sticky="w")
            ttk.Entry(mem_frame, textvariable=var, width=20).grid(row=r, column=c + 1, padx=(4, 16), pady=2)

        row("Target username", self.target_var, 0)
        row("PID (hex)", self.pid_var, 0, c=2)
        row("Address (hex)", self.addr_var, 1)
        row("Length (read)", self.len_var, 1, c=2)
        row("Write data (hex)", self.write_hex_var, 2)

        btn_row = ttk.Frame(mem_frame)
        btn_row.grid(row=3, column=0, columnspan=4, pady=(8, 0))
        ttk.Button(btn_row, text="Read", command=self._request_read).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Write", command=self._request_write).pack(side="left", padx=4)

        self._log("Connected. Nothing happens to your PS3 unless you approve an incoming request.")

    def _log(self, text: str):
        self.chat_log.config(state="normal")
        self.chat_log.insert("end", text + "\n")
        self.chat_log.see("end")
        self.chat_log.config(state="disabled")

    def _send_chat(self):
        text = self.chat_entry.get().strip()
        if not text or not self.net:
            return
        self.net.publish("chat", {"from": self.username, "text": text})
        self.chat_entry.delete(0, "end")

    def _request_read(self):
        target = self.target_var.get().strip()
        if not target or not self.net:
            return
        self.net.publish(
            "mem_read_request",
            {
                "from": self.username,
                "to": target,
                "pid": int(self.pid_var.get(), 16),
                "address": self.addr_var.get().strip(),
                "length": int(self.len_var.get()),
            },
        )
        self._log(f"Requested read from {target}...")

    def _request_write(self):
        target = self.target_var.get().strip()
        if not target or not self.net:
            return
        self.net.publish(
            "mem_write_request",
            {
                "from": self.username,
                "to": target,
                "pid": int(self.pid_var.get(), 16),
                "address": self.addr_var.get().strip(),
                "dataHex": self.write_hex_var.get().strip(),
            },
        )
        self._log(f"Requested write on {target}...")

    # -- queue polling / handling incoming events ---------------------------

    def _poll_queue(self):
        try:
            while True:
                kind, data = self.event_queue.get_nowait()
                self._handle_event(kind, data)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _handle_event(self, kind, data):
        if kind == "_poll_error":
            # Transient network hiccups are common with polling; just log them.
            self._log(f"(connection issue: {data.get('error')})")
            return

        if kind == "chat":
            if data.get("from") != self.username:
                self._log(f"{data.get('from')}: {data.get('text')}")

        elif kind == "mem_read_request":
            if data.get("to") != self.username:
                return
            self._handle_read_request(data)

        elif kind == "mem_write_request":
            if data.get("to") != self.username:
                return
            self._handle_write_request(data)

        elif kind == "mem_read_response":
            if data.get("to") != self.username:
                return
            if data.get("error"):
                self._log(f"Read failed from {data.get('from')}: {data.get('error')}")
            else:
                self._log(f"Read OK from {data.get('from')}: {data.get('dataHex')}")

        elif kind == "mem_write_response":
            if data.get("to") != self.username:
                return
            if data.get("error"):
                self._log(f"Write failed on {data.get('from')}: {data.get('error')}")
            else:
                self._log(f"Write OK on {data.get('from')}")

    def _confirm(self, prompt: str) -> bool:
        if self.auto_approve.get():
            return True
        return messagebox.askyesno("Incoming memory request", prompt)

    def _handle_read_request(self, data):
        requester = data.get("from")
        pid = data.get("pid", 0)
        address = int(data.get("address", "0"), 16)
        length = int(data.get("length", 0))

        ok = self._confirm(
            f"{requester} wants to READ {length} bytes\nfrom pid={pid:#x} addr={address:#x}\non YOUR PS3. Allow it?"
        )
        if not ok:
            self.net.publish("mem_read_response", {"from": self.username, "to": requester, "error": "Denied by target user."})
            self._log(f"Denied read request from {requester}.")
            return
        try:
            data_bytes = self.ps3.Process.Memory.Get(pid, address, length)
            self.net.publish("mem_read_response", {"from": self.username, "to": requester, "dataHex": data_bytes.hex()})
            self._log(f"Approved read for {requester}.")
        except Exception as e:
            self.net.publish("mem_read_response", {"from": self.username, "to": requester, "error": str(e)})

    def _handle_write_request(self, data):
        requester = data.get("from")
        pid = data.get("pid", 0)
        address = int(data.get("address", "0"), 16)
        data_hex = data.get("dataHex", "")

        ok = self._confirm(
            f"{requester} wants to WRITE {len(data_hex)//2} bytes\nto pid={pid:#x} addr={address:#x}\non YOUR PS3. Allow it?"
        )
        if not ok:
            self.net.publish("mem_write_response", {"from": self.username, "to": requester, "error": "Denied by target user."})
            self._log(f"Denied write request from {requester}.")
            return
        try:
            self.ps3.Process.Memory.Set(pid, address, bytes.fromhex(data_hex))
            self.net.publish("mem_write_response", {"from": self.username, "to": requester, "ok": True})
            self._log(f"Approved write for {requester}.")
        except Exception as e:
            self.net.publish("mem_write_response", {"from": self.username, "to": requester, "error": str(e)})


if __name__ == "__main__":
    app = App()
    app.mainloop()
