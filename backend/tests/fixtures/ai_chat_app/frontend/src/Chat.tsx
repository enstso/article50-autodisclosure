import { useState } from "react";

export function Chat() {
  const [message, setMessage] = useState("");

  async function sendMessage() {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    return response.json();
  }

  return (
    <form onSubmit={sendMessage}>
      <input value={message} onChange={(event) => setMessage(event.target.value)} />
      <button type="submit">Send</button>
    </form>
  );
}
