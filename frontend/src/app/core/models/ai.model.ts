export interface AiRewriteRequest {
  text: string;
  instruction?: string;
}

export interface AiSummarizeRequest {
  text: string;
  max_words?: number;
}

export interface AiGenerateRequest {
  prompt: string;
}

export interface AiActionRequest {
  action: AiAction;
  text?: string;
  instruction?: string;
  tone?: string;
  max_words?: number;
  prompt?: string;
  document_title?: string;
  before?: string;
  after?: string;
}

export interface AiResponse {
  output: string;
}

export interface AiActionInfo {
  action: string;
  label: string;
  needs_text: boolean;
}

export type AiAction =
  | 'rewrite' | 'improve' | 'expand' | 'condense' | 'summarize'
  | 'grammar' | 'tone' | 'continue' | 'outline' | 'custom' | 'generate' | 'heading' | 'headings';

export type AiMode = AiAction;

export const AI_TONES = ['professional', 'casual', 'academic', 'friendly', 'confident'] as const;
export type AiTone = (typeof AI_TONES)[number];
