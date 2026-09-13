import { useState } from "react";
import { useRouter } from "next/router";

function randomCode() {
  return Math.random().toString(36).slice(2, 7).toUpperCase();
}

export default function Home() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [roomCode, setRoomCode] = useState("");

  function enterRoom(code) {
    if (!username.trim()) {
      alert("Enter a username first.");
      return;
    }
    router.push(`/room/${code.trim().toUpperCase()}?username=${encodeURIComponent(username.trim())}`);
  }

  return (
    <main style={{ maxWidth: 420, margin: "80px auto", fontFamily: "sans-serif" }}>
      <h1>PS3 Mem Relay</h1>
      <p style={{ color: "#666" }}>
        Enter a username, then create a room or join one with a code.
      </p>

      <label style={{ display: "block", marginTop: 24 }}>
        Username
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
        />
      </label>

      <button
        onClick={() => enterRoom(randomCode())}
        style={{ marginTop: 20, padding: "10px 16px", width: "100%" }}
      >
        Create new room
      </button>

      <div style={{ marginTop: 24, borderTop: "1px solid #ddd", paddingTop: 24 }}>
        <label style={{ display: "block" }}>
          Room code
          <input
            value={roomCode}
            onChange={(e) => setRoomCode(e.target.value)}
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
          />
        </label>
        <button
          onClick={() => enterRoom(roomCode)}
          style={{ marginTop: 12, padding: "10px 16px", width: "100%" }}
        >
          Join room
        </button>
      </div>
    </main>
  );
}
