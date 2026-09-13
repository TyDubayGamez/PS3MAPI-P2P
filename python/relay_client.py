"""
relay_client.py
================
Local agent that bridges a room on your Vercel/Ably relay to your own PS3
via ps3mapi.py. Run this on the same PC as your PS3MAPI/webMAN-MOD target.

Setup:
    pip install ably requests

Usage:
    python relay_client.py --server https://your-app.vercel.app --room ABCDE \
        --username alice --ps3-ip 192.168.1.50

By default, every incoming read/write request from someone else in the room
requires you to type `y` before it runs. Pass --auto-approve to skip that
(only do this with people you fully trust).
"""

from __future__ import annotations

import argparse
import json
import threading
import time

import requests
from ably import AblyRealtime

import ps3mapi


def get_token_request(server: str, client_id: str) -> dict:
    resp = requests.get(f"{server}/api/ably-auth", params={"clientId": client_id}, timeout=10)
    resp.raise_for_status()
    return resp.json()


class Agent:
    def __init__(self, server: str, room: str, username: str, ps3_ip: str, ps3_port: int, auto_approve: bool):
        self.server = server
        self.room = room
        self.username = username
        self.auto_approve = auto_approve

        self.ps3 = ps3mapi.PS3MAPI()
        self.ps3.ConnectTarget(ps3_ip, ps3_port)
        print(f"Connected to PS3 at {ps3_ip}:{ps3_port} (fw {self.ps3.PS3.GetFirmwareVersion_Str()})")

        self.ably = AblyRealtime(auth_callback=self._auth_callback)
        self.channel = self.ably.channels.get(f"room-{room}")

    def _auth_callback(self, token_params):
        return get_token_request(self.server, self.username)

    def start(self):
        self.channel.subscribe("chat", self._on_chat)
        self.channel.subscribe("mem_read_request", self._on_read_request)
        self.channel.subscribe("mem_write_request", self._on_write_request)
        self.channel.publish(
            "presence_note", {"text": f"{self.username}'s agent is online and listening."}
        )
        print(f"Agent online in room {self.room} as {self.username}. Ctrl+C to quit.")

    def _on_chat(self, msg):
        d = msg.data
        if d.get("from") != self.username:
            print(f"[chat] {d.get('from')}: {d.get('text')}")

    def _confirm(self, prompt: str) -> bool:
        if self.auto_approve:
            return True
        try:
            answer = input(f"{prompt} [y/N]: ").strip().lower()
        except EOFError:
            return False
        return answer == "y"

    def _on_read_request(self, msg):
        d = msg.data
        if d.get("to") != self.username:
            return
        requester = d.get("from")
        pid = d.get("pid", 0)
        address = int(d.get("address", "0"), 16)
        length = int(d.get("length", 0))

        ok = self._confirm(
            f"{requester} wants to READ {length} bytes from pid={pid:#x} addr={address:#x} on YOUR PS3."
        )
        if not ok:
            self._publish_read_response(requester, error="Denied by target user.")
            return

        try:
            data = self.ps3.Process.Memory.Get(pid, address, length)
            self._publish_read_response(requester, data_hex=data.hex())
        except Exception as e:
            self._publish_read_response(requester, error=str(e))

    def _on_write_request(self, msg):
        d = msg.data
        if d.get("to") != self.username:
            return
        requester = d.get("from")
        pid = d.get("pid", 0)
        address = int(d.get("address", "0"), 16)
        data_hex = d.get("dataHex", "")

        ok = self._confirm(
            f"{requester} wants to WRITE {len(data_hex)//2} bytes to pid={pid:#x} addr={address:#x} on YOUR PS3."
        )
        if not ok:
            self._publish_write_response(requester, error="Denied by target user.")
            return

        try:
            self.ps3.Process.Memory.Set(pid, address, bytes.fromhex(data_hex))
            self._publish_write_response(requester, ok=True)
        except Exception as e:
            self._publish_write_response(requester, error=str(e))

    def _publish_read_response(self, to, data_hex=None, error=None):
        self.channel.publish(
            "mem_read_response",
            {"from": self.username, "to": to, "dataHex": data_hex, "error": error},
        )

    def _publish_write_response(self, to, ok=False, error=None):
        self.channel.publish(
            "mem_write_response",
            {"from": self.username, "to": to, "ok": ok, "error": error},
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="Your deployed Vercel app URL, e.g. https://foo.vercel.app")
    ap.add_argument("--room", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--ps3-ip", required=True)
    ap.add_argument("--ps3-port", type=int, default=7887)
    ap.add_argument("--auto-approve", action="store_true", help="Skip the y/N consent prompt for incoming requests.")
    args = ap.parse_args()

    agent = Agent(args.server, args.room, args.username, args.ps3_ip, args.ps3_port, args.auto_approve)
    agent.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down.")
        agent.ps3.DisconnectTarget()


if __name__ == "__main__":
    main()
