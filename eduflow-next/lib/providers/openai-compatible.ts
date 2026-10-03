import { LLMMessage, LLMProvider, LLMResponse } from "./types";

export interface OpenAICompatibleConfig {
  name: string;
  model: string;
  baseUrl: string;
  apiKey?: string;
  requiresApiKey?: boolean;
}

export class OpenAICompatibleProvider implements LLMProvider {
  name: string;
  model: string;
  baseUrl: string;
  apiKey?: string;

  constructor(config: OpenAICompatibleConfig) {
    if (config.requiresApiKey !== false && !config.apiKey) {
      throw new Error(`${config.name}: no API key configured`);
    }
    if (!config.model?.trim()) {
      throw new Error(`${config.name}: no model configured`);
    }
    this.name = config.name;
    this.model = config.model;
    this.baseUrl = config.baseUrl.replace(/\/$/, "");
    this.apiKey = config.apiKey;
  }

  async complete(
    messages: LLMMessage[],
    options: { maxTokens?: number; temperature?: number } = {}
  ): Promise<LLMResponse> {
    const maxTokens = options.maxTokens ?? 1024;
    const temperature = options.temperature ?? 0.0;

    const url = `${this.baseUrl}/chat/completions`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey && this.apiKey !== "not-required") {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    const body = {
      model: this.model,
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      max_tokens: maxTokens,
      temperature,
    };

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
    } catch (err: any) {
      throw new Error(`${this.name}: connection failure (${err.message})`);
    }

    if (!response.ok) {
      const status = response.status;
      const text = await response.text().catch(() => "");
      const reasonMap: Record<number, string> = {
        401: "Invalid or expired API token",
        403: "Token lacks inference permission or model access",
        402: "Inference credits exhausted; check provider billing",
        404: "Model or endpoint unavailable",
        429: "Provider rate limit reached",
      };
      const reason = reasonMap[status] || `HTTP ${status}: ${text.slice(0, 100)}`;
      throw new Error(`${this.name}: ${reason}`);
    }

    const data = await response.json();
    const choice = data.choices?.[0];
    const text = choice?.message?.content?.trim() || "";

    if (!text) {
      throw new Error(
        `${this.name}: empty completion from ${data.model || this.model}`
      );
    }

    return {
      text,
      model: data.model || this.model,
      provider: this.name,
      inputTokens: data.usage?.prompt_tokens ?? 0,
      outputTokens: data.usage?.completion_tokens ?? 0,
    };
  }
}
