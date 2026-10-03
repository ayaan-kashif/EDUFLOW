import { LLMMessage, LLMProvider, LLMResponse } from "./types";

export class GeminiProvider implements LLMProvider {
  name = "gemini";
  private apiKey: string;
  private primaryModel: string;

  constructor(options: { apiKey: string; model?: string }) {
    this.apiKey = options.apiKey;
    this.primaryModel = options.model || "gemini-3.5-flash";
  }

  async complete(
    messages: LLMMessage[],
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<LLMResponse> {
    const candidateModels = [
      this.primaryModel,
      "gemini-3.5-flash",
      "gemini-3.8-flash",
      "gemini-2.5-flash",
    ].filter((v, i, a) => a.indexOf(v) === i); // deduplicate

    let lastError: Error | null = null;

    // Separate system message if present
    const systemMsg = messages.find((m) => m.role === "system");
    const chatMsgs = messages.filter((m) => m.role !== "system");

    const contents = chatMsgs.map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    }));

    for (const model of candidateModels) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${this.apiKey}`;

        const payload: any = {
          contents,
          generationConfig: {
            temperature: options.temperature ?? 0.3,
            maxOutputTokens: options.maxTokens ?? 2048,
          },
        };

        if (systemMsg) {
          payload.system_instruction = {
            parts: [{ text: systemMsg.content }],
          };
        }

        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          const errMsg = errData.error?.message || `HTTP ${res.status} ${res.statusText}`;
          throw new Error(`Gemini (${model}): ${errMsg}`);
        }

        const data = await res.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text || "";
        const inputTokens = data.usageMetadata?.promptTokenCount;
        const outputTokens = data.usageMetadata?.candidatesTokenCount;

        return {
          text,
          model,
          provider: "gemini",
          inputTokens,
          outputTokens,
        };
      } catch (err: any) {
        lastError = err;
        console.warn(`[GeminiProvider] Model ${model} failed: ${err.message}. Trying next candidate...`);
      }
    }

    throw lastError || new Error("Gemini generation failed on all candidate models");
  }
}
