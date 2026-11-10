import { Injectable, signal } from '@angular/core';

export interface MetricsSnapshot {
  sessionStart: string;
  sessionDurationMs: number;
  keystrokes: number;
  aiActions: Record<string, number>;
  suggestionsAccepted: number;
  suggestionsRejected: number;
  versionsSaved: number;
  versionsRestored: number;
  documentsCreated: number;
  documentsOpened: number;
  sharesInvited: number;
  exportCount: number;
}

const STORAGE_KEY = 'docintel.metrics';

@Injectable({ providedIn: 'root' })
export class MetricsCollector {
  private sessionStart = Date.now();
  private keystrokeCount = 0;
  private aiActionCounts: Record<string, number> = {};
  private acceptedCount = 0;
  private rejectedCount = 0;
  private versionsSavedCount = 0;
  private versionsRestoredCount = 0;
  private documentsCreatedCount = 0;
  private documentsOpenedCount = 0;
  private sharesInvitedCount = 0;
  private exportCounter = 0;

  readonly enabled = signal(false);

  enable(): void {
    this.enabled.set(true);
    this.sessionStart = Date.now();
  }

  disable(): void {
    this.enabled.set(false);
  }

  toggle(): void {
    if (this.enabled()) {
      this.disable();
    } else {
      this.enable();
    }
  }

  recordKeystroke(): void {
    if (!this.enabled()) return;
    this.keystrokeCount++;
  }

  recordAiAction(action: string): void {
    if (!this.enabled()) return;
    this.aiActionCounts[action] = (this.aiActionCounts[action] ?? 0) + 1;
  }

  recordSuggestionAccepted(): void {
    if (!this.enabled()) return;
    this.acceptedCount++;
  }

  recordSuggestionRejected(): void {
    if (!this.enabled()) return;
    this.rejectedCount++;
  }

  recordVersionSaved(): void {
    if (!this.enabled()) return;
    this.versionsSavedCount++;
  }

  recordVersionRestored(): void {
    if (!this.enabled()) return;
    this.versionsRestoredCount++;
  }

  recordDocumentCreated(): void {
    if (!this.enabled()) return;
    this.documentsCreatedCount++;
  }

  recordDocumentOpened(): void {
    if (!this.enabled()) return;
    this.documentsOpenedCount++;
  }

  recordShareInvited(): void {
    if (!this.enabled()) return;
    this.sharesInvitedCount++;
  }

  recordExport(): void {
    if (!this.enabled()) return;
    this.exportCounter++;
  }

  getSnapshot(): MetricsSnapshot {
    return {
      sessionStart: new Date(this.sessionStart).toISOString(),
      sessionDurationMs: Date.now() - this.sessionStart,
      keystrokes: this.keystrokeCount,
      aiActions: { ...this.aiActionCounts },
      suggestionsAccepted: this.acceptedCount,
      suggestionsRejected: this.rejectedCount,
      versionsSaved: this.versionsSavedCount,
      versionsRestored: this.versionsRestoredCount,
      documentsCreated: this.documentsCreatedCount,
      documentsOpened: this.documentsOpenedCount,
      sharesInvited: this.sharesInvitedCount,
      exportCount: this.exportCounter,
    };
  }

  exportJson(): string {
    return JSON.stringify(this.getSnapshot(), null, 2);
  }

  downloadJson(): void {
    const data = this.exportJson();
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `docintel-metrics-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  reset(): void {
    this.keystrokeCount = 0;
    this.aiActionCounts = {};
    this.acceptedCount = 0;
    this.rejectedCount = 0;
    this.versionsSavedCount = 0;
    this.versionsRestoredCount = 0;
    this.documentsCreatedCount = 0;
    this.documentsOpenedCount = 0;
    this.sharesInvitedCount = 0;
    this.exportCounter = 0;
    this.sessionStart = Date.now();
  }
}
