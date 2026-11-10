/** A user's document. Matches the backend DocumentOut schema. */
export interface Document {
  id: string;
  owner_id: string;
  title: string;
  content: Record<string, unknown>;
  word_count: number;
  revision: number;
  updated_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DocumentDraft {
  title: string;
  content: Record<string, unknown>;
}

export interface DocumentUpdate extends DocumentDraft {
  base_revision: number;
}

/** Lightweight representation for the dashboard list. */
export interface DocumentSummary {
  id: string;
  title: string;
  word_count: number;
  revision: number;
  owner_id: string;
  updated_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}
