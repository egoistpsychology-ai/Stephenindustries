const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const sendButton = document.querySelector("#send");
const messages = document.querySelector("#messages");
const statusLine = document.querySelector("#status");
const welcome = document.querySelector("#welcome");
const sessionId = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());

function addMessage(kind, text) {
  const element = document.createElement("article");
  element.className = "message " + kind;
  if (kind === "assistant") {
    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = "STEPHEN";
    const answer = document.createElement("div");
    answer.className = "answer";
    answer.textContent = text || "";
    const cost = document.createElement("div");
    cost.className = "cost";
    cost.hidden = true;
    element.append(label, answer, cost);
    messages.append(element);
    return { element, answer, cost };
  }
  element.textContent = text;
  messages.append(element);
  return { element };
}

async function readStream(taskId, assistant) {
  const response = await fetch("/api/stream/" + encodeURIComponent(taskId), {
    headers: { Accept: "text/event-stream" }
  });
  if (!response.ok || !response.body) throw new Error("Could not open task stream (" + response.status + ").");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finished = false;
  while (!finished) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      const data = frame.split("\n").find(line => line.startsWith("data:"));
      if (!data) continue;
      let event;
      try { event = JSON.parse(data.slice(5).trim()); } catch { continue; }
      if (event.type === "status") statusLine.textContent = event.text || event.agent || "Working…";
      if (event.type === "token") assistant.answer.textContent += event.text || "";
      if (event.type === "cost") {
        assistant.cost.textContent = "Estimated cost: $" + Number(event.usd || 0).toFixed(5);
        assistant.cost.hidden = false;
      }
      if (event.type === "error") {
        assistant.answer.textContent += (assistant.answer.textContent ? "\n\n" : "") + "Error: " + (event.message || "Task failed.");
        statusLine.textContent = "Task failed.";
      }
      if (event.type === "done") {
        finished = true;
        statusLine.textContent = "Finished.";
      }
    }
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || sendButton.disabled) return;
  welcome.hidden = true;
  addMessage("user", message);
  const assistant = addMessage("assistant", "");
  input.value = "";
  input.style.height = "auto";
  sendButton.disabled = true;
  statusLine.textContent = "Starting Stephen’s team…";
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not start task.");
    await readStream(result.task_id, assistant);
  } catch (error) {
    assistant.answer.textContent = "Error: " + error.message;
    statusLine.textContent = "Something went wrong.";
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
});
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
