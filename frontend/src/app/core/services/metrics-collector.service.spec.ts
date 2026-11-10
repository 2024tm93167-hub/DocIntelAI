import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MetricsCollector } from './metrics-collector.service';

describe('MetricsCollector', () => {
  let service: MetricsCollector;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(MetricsCollector);
    service.reset();
    service.disable();
  });

  it('starts disabled by default', () => {
    expect(service.enabled()).toBe(false);
  });

  it('enables and disables', () => {
    service.enable();
    expect(service.enabled()).toBe(true);
    service.disable();
    expect(service.enabled()).toBe(false);
  });

  it('toggles enabled state', () => {
    expect(service.enabled()).toBe(false);
    service.toggle();
    expect(service.enabled()).toBe(true);
    service.toggle();
    expect(service.enabled()).toBe(false);
  });

  it('records keystrokes when enabled', () => {
    service.enable();
    service.recordKeystroke();
    service.recordKeystroke();
    service.recordKeystroke();
    expect(service.getSnapshot().keystrokes).toBe(3);
  });

  it('does not record when disabled', () => {
    service.disable();
    service.recordKeystroke();
    service.recordAiAction('rewrite');
    service.recordSuggestionAccepted();
    expect(service.getSnapshot().keystrokes).toBe(0);
    expect(service.getSnapshot().aiActions['rewrite']).toBeUndefined();
    expect(service.getSnapshot().suggestionsAccepted).toBe(0);
  });

  it('records AI actions by type', () => {
    service.enable();
    service.recordAiAction('rewrite');
    service.recordAiAction('rewrite');
    service.recordAiAction('summarize');
    expect(service.getSnapshot().aiActions['rewrite']).toBe(2);
    expect(service.getSnapshot().aiActions['summarize']).toBe(1);
  });

  it('records suggestion accept/reject', () => {
    service.enable();
    service.recordSuggestionAccepted();
    service.recordSuggestionRejected();
    service.recordSuggestionAccepted();
    expect(service.getSnapshot().suggestionsAccepted).toBe(2);
    expect(service.getSnapshot().suggestionsRejected).toBe(1);
  });

  it('records version saves and restores', () => {
    service.enable();
    service.recordVersionSaved();
    service.recordVersionSaved();
    service.recordVersionRestored();
    expect(service.getSnapshot().versionsSaved).toBe(2);
    expect(service.getSnapshot().versionsRestored).toBe(1);
  });

  it('records document creation and opening', () => {
    service.enable();
    service.recordDocumentCreated();
    service.recordDocumentOpened();
    service.recordDocumentOpened();
    expect(service.getSnapshot().documentsCreated).toBe(1);
    expect(service.getSnapshot().documentsOpened).toBe(2);
  });

  it('records share invitations and exports', () => {
    service.enable();
    service.recordShareInvited();
    service.recordShareInvited();
    service.recordExport();
    expect(service.getSnapshot().sharesInvited).toBe(2);
    expect(service.getSnapshot().exportCount).toBe(1);
  });

  it('exports JSON with all fields', () => {
    service.enable();
    service.recordKeystroke();
    service.recordAiAction('rewrite');
    const json = service.exportJson();
    const parsed = JSON.parse(json);
    expect(parsed.keystrokes).toBe(1);
    expect(parsed.aiActions['rewrite']).toBe(1);
    expect(parsed.sessionStart).toBeTruthy();
    expect(parsed.sessionDurationMs).toBeGreaterThanOrEqual(0);
  });

  it('resets all counters', () => {
    service.enable();
    service.recordKeystroke();
    service.recordAiAction('rewrite');
    service.recordSuggestionAccepted();
    service.reset();
    const snapshot = service.getSnapshot();
    expect(snapshot.keystrokes).toBe(0);
    expect(snapshot.aiActions['rewrite']).toBeUndefined();
    expect(snapshot.suggestionsAccepted).toBe(0);
  });
});
