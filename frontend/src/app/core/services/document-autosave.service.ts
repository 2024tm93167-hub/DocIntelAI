import { Injectable, OnDestroy, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Subscription } from 'rxjs';

import { Document, DocumentDraft } from '../models/document.model';
import { DocumentService } from './document.service';

export type SaveStatus = 'saved' | 'unsaved' | 'saving' | 'error' | 'conflict';

@Injectable()
export class DocumentAutosaveService implements OnDestroy {
  private readonly api = inject(DocumentService);
  private readonly savedDocument = signal<Document | null>(null);
  private readonly saveState = signal<SaveStatus>('saved');
  readonly document = this.savedDocument.asReadonly();
  readonly status = this.saveState.asReadonly();
  readonly errorMessage = signal<string | null>(null);
  readonly hasUnsavedChanges = computed(() => this.status() !== 'saved');
  private pending: DocumentDraft | null = null;
  private inFlight = false;
  private request: Subscription | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;

  initialize(document: Document): void {
    this.ngOnDestroy();
    this.savedDocument.set(document);
    this.pending = null;
    this.inFlight = false;
    this.saveState.set('saved');
    this.errorMessage.set(null);
  }

  queue(draft: DocumentDraft): void {
    this.pending = draft;
    clearTimeout(this.timer);
    if (this.status() === 'conflict' || this.status() === 'error') return;
    this.saveState.set(this.inFlight ? 'saving' : 'unsaved');
    this.timer = setTimeout(() => this.flush(), 1200);
  }

  flush(): void {
    clearTimeout(this.timer);
    const document = this.document();
    if (!document || !this.pending || this.inFlight || this.status() === 'conflict' || this.status() === 'error') return;
    const draft = this.pending;
    if (!draft.title.trim() || draft.title.length > 200) {
      this.saveState.set('error');
      this.errorMessage.set('Use a document title between 1 and 200 characters, then retry.');
      return;
    }
    this.pending = null;
    this.inFlight = true;
    this.saveState.set('saving');
    this.request = this.api.update(document.id, { ...draft, base_revision: document.revision }).subscribe({
      next: (updated) => {
        this.inFlight = false;
        this.savedDocument.set(updated);
        this.saveState.set(this.pending ? 'unsaved' : 'saved');
        this.errorMessage.set(null);
        if (this.pending) this.flush();
      },
      error: (error: HttpErrorResponse) => {
        this.inFlight = false;
        this.pending ??= draft;
        const conflict = error.status === 409;
        this.saveState.set(conflict ? 'conflict' : 'error');
        this.errorMessage.set(conflict
          ? 'This document changed in another session. Your local draft is still here. Download it before loading the latest version.'
          : error.status === 422
            ? 'The document could not be saved. Check the title and content size (maximum 750 KB), then retry.'
            : 'Saving failed. Your local draft is still here. Check your connection and retry.');
      },
    });
  }

  retry(): void {
    if (this.status() !== 'error') return;
    this.saveState.set('unsaved');
    this.errorMessage.set(null);
    this.flush();
  }

  ngOnDestroy(): void {
    clearTimeout(this.timer);
    this.request?.unsubscribe();
    this.request = null;
  }
}
