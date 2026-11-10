export interface UserStats {
  total_documents: number;
  total_words: number;
  total_versions: number;
  average_words_per_document: number;
  documents_last_7_days: number;
  documents_last_30_days: number;
}

export interface DocumentStats {
  word_count: number;
  char_count: number;
  sentence_count: number;
  paragraph_count: number;
  estimated_reading_time_minutes: number;
}

export interface ReadabilityResult extends DocumentStats {
  flesch_reading_ease: number;
  flesch_kincaid_grade: number;
  suggestions: string[];
}

export type ExportFormat = 'markdown' | 'html' | 'text' | 'docx' | 'pdf';
