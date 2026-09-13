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
    <section className="chat-shell">
      <h1>Customer support</h1>
      <form className="chat-form" onSubmit={sendMessage}>
        <input value={message} onChange={(event) => setMessage(event.target.value)} />
        <button type="submit">Send message</button>
      </form>
    </section>
  );
}
