import { useState } from "react";

type CompleteResponse = {
  response: string;
  model_id: string;
  usage: { input_tokens: number; output_tokens: number };
  latency_ms: number;
};

export default function LlmForm() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CompleteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSend = prompt.trim() !== "" && !loading;

  const send = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const response = await fetch("/api/llm/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = data?.detail;
        setError(
          typeof detail === "string"
            ? detail
            : `Request failed (${response.status})`,
        );
        return;
      }
      setResult(data as CompleteResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) send();
      }}
      style={{ textAlign: "left", width: "100%" }}
    >
      <h2>Ask the LLM</h2>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={4}
        placeholder="Type a prompt..."
        style={{ width: "100%", boxSizing: "border-box" }}
      />
      <button type="submit" disabled={!canSend}>
        {loading ? "Sending..." : "Send"}
      </button>
      {error && (
        <p role="alert" style={{ color: "crimson" }}>
          {error}
        </p>
      )}
      {result && (
        <div>
          <p style={{ whiteSpace: "pre-wrap" }}>{result.response}</p>
          <small>
            {result.model_id} · {result.usage.input_tokens} in /{" "}
            {result.usage.output_tokens} out · {result.latency_ms} ms
          </small>
        </div>
      )}
    </form>
  );
}
