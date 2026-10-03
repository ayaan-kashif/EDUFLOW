import { LLMMessage, LLMProvider, LLMResponse } from "./types";
import { OpenAICompatibleProvider } from "./openai-compatible";
import { GeminiProvider } from "./gemini";

export interface ProviderEvent {
  timestamp: string;
  provider: string;
  model: string;
  status: "success" | "error" | "retry" | "fallback";
  latencyMs: number;
  error?: string;
  tokens?: { input: number; output: number };
}

export const PROVIDER_EVENTS: ProviderEvent[] = [];

function recordEvent(event: ProviderEvent) {
  PROVIDER_EVENTS.unshift(event);
  if (PROVIDER_EVENTS.length > 100) {
    PROVIDER_EVENTS.pop();
  }
}

class CircuitBreaker {
  private failureCount = 0;
  private openedAt: number | null = null;

  constructor(
    private failureThreshold: number = 3,
    private cooldownSeconds: number = 30
  ) {}

  check(providerName: string) {
    if (this.openedAt === null) return;
    const elapsed = (Date.now() - this.openedAt) / 1000;
    if (elapsed < this.cooldownSeconds) {
      throw new Error(
        `${providerName}: circuit open, ${Math.ceil(this.cooldownSeconds - elapsed)}s cooldown remaining`
      );
    }
    this.openedAt = null;
    this.failureCount = 0;
  }

  recordSuccess() {
    this.openedAt = null;
    this.failureCount = 0;
  }

  recordFailure(providerName: string) {
    this.failureCount += 1;
    if (this.failureCount >= this.failureThreshold) {
      this.openedAt = Date.now();
      console.warn(
        `[EduFlow] Circuit breaker opened for ${providerName} after ${this.failureCount} failures`
      );
    }
  }
}

export class FallbackLLMChain {
  private providers: { provider: LLMProvider; breaker: CircuitBreaker }[] = [];

  constructor(providers: LLMProvider[]) {
    this.providers = providers.map((p) => ({
      provider: p,
      breaker: new CircuitBreaker(3, 30),
    }));
  }

  async complete(
    messages: LLMMessage[],
    options: { maxTokens?: number; temperature?: number; excludeProvider?: string } = {}
  ): Promise<LLMResponse> {
    if (this.providers.length === 0) {
      throw new Error(
        "No LLM providers configured. Please provide GEMINI_API_KEY (primary) or GROQ_API_KEY (backup) in .env.local."
      );
    }
    if (options.excludeProvider && this.providers.every(
      ({ provider }) => provider.name === options.excludeProvider
    )) {
      throw new Error("Independent AI verifier is not configured. Add a second provider key.");
    }

    const errors: string[] = [];

    for (const { provider, breaker } of this.providers) {
      if (provider.name === options.excludeProvider) continue;
      const startTime = Date.now();
      try {
        breaker.check(provider.name);
        const res = await provider.complete(messages, options);
        breaker.recordSuccess();

        recordEvent({
          timestamp: new Date().toISOString(),
          provider: provider.name,
          model: res.model,
          status: "success",
          latencyMs: Date.now() - startTime,
          tokens: {
            input: res.inputTokens || 0,
            output: res.outputTokens || 0,
          },
        });

        return res;
      } catch (err: any) {
        breaker.recordFailure(provider.name);
        const errMsg = err.message || String(err);
        errors.push(`${provider.name}: ${errMsg}`);

        recordEvent({
          timestamp: new Date().toISOString(),
          provider: provider.name,
          model: (provider as any).model || "unknown",
          status: "fallback",
          latencyMs: Date.now() - startTime,
          error: errMsg,
        });

        console.warn(`[EduFlow] Provider ${provider.name} failed: ${errMsg}. Trying next provider in chain...`);
      }
    }

    throw new Error(`All configured LLM providers failed: ${errors.join("; ")}`);
  }
}

let cachedChain: FallbackLLMChain | null = null;

export function getLLMChain(): FallbackLLMChain {
  if (cachedChain) return cachedChain;

  const providers: LLMProvider[] = [];

  // 1. Primary: Google Gemini (Native Generative Language API)
  const geminiKey = process.env.GEMINI_API_KEY?.trim();
  if (geminiKey) {
    try {
      providers.push(
        new GeminiProvider({
          apiKey: geminiKey,
          model: process.env.GEMINI_MODEL || "gemini-3.5-flash",
        })
      );
    } catch (e: any) {
      console.warn("Failed to initialize Gemini provider:", e.message);
    }
  }

  // 2. Backup: Groq
  const groqKey = process.env.GROQ_API_KEY?.trim();
  if (groqKey) {
    try {
      providers.push(
        new OpenAICompatibleProvider({
          name: "groq",
          model: process.env.GROQ_MODEL || "qwen/qwen3.8-27b",
          baseUrl: "https://api.groq.com/openai/v1",
          apiKey: groqKey,
        })
      );
    } catch (e: any) {
      console.warn("Failed to initialize Groq provider:", e.message);
    }
  }

  cachedChain = new FallbackLLMChain(providers);
  return cachedChain;
}
