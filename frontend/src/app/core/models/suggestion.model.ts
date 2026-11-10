export type SuggestionType =
  | 'grammar' | 'clarity' | 'tone' | 'wordiness' | 'repetition'
  | 'alternative' | 'rewrite' | 'other' | 'spelling' | 'conciseness' | 'readability' | 'word_choice';

export type SuggestionStatus = 'pending' | 'accepted' | 'rejected';

export interface Suggestion {
  id: string;
  document_id: string;
  user_id: string;
  type: SuggestionType;
  original_text: string;
  suggested_text: string;
  reason: string | null;
  status: SuggestionStatus;
  document_revision: number;
  created_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface SuggestionCreate {
  type: SuggestionType;
  original_text?: string;
  suggested_text?: string;
  reason?: string;
  document_revision?: number;
}

export interface SuggestionUpdate {
  status: 'accepted' | 'rejected';
  base_revision?: number;
}
