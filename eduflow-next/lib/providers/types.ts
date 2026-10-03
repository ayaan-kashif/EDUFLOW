export interface LLMMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LLMResponse {
  text: string;
  model: string;
  provider: string;
  inputTokens?: number;
  outputTokens?: number;
}

export interface EmbeddingResponse {
  vectors: number[][];
  model: string;
  provider: string;
}

export interface ExtractedBlock {
  blockId: string;
  page: number;
  kind: "heading" | "paragraph" | "table" | "figure" | "list_item";
  text: string;
  bbox: { x0: number; y0: number; x1: number; y1: number };
  readingOrder: number;
  confidence: number;
}

export interface ParsedDocument {
  blocks: ExtractedBlock[];
  parserConfidence: number;
  parserName: string;
}

export interface LLMProvider {
  name: string;
  complete(
    messages: LLMMessage[],
    options?: { maxTokens?: number; temperature?: number }
  ): Promise<LLMResponse>;
}
