export interface VersionSummary {
  id: string;
  document_id: string;
  title: string;
  word_count: number;
  label: string | null;
  created_at: string | null;
  created_by: string | null;
  author_name: string | null;
  source: 'manual' | 'autosave' | 'before_restore' | 'restore';
  document_revision: number;
  restored_from_version_id: string | null;
}

export interface VersionOut extends VersionSummary {
  content: Record<string, unknown>;
}

export interface DiffChunk {
  op: 'equal' | 'insert' | 'delete' | 'replace';
  old_text: string | null;
  new_text: string | null;
}

export interface DiffOut {
  from_version_id: string | null;
  to_version_id: string | null;
  chunks: DiffChunk[];
}
