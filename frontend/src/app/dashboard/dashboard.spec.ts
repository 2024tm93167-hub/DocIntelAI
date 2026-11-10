import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Dashboard } from './dashboard';
import { AuthService } from '../core/services/auth.service';
import { UserService } from '../core/services/user.service';
import { DocumentService } from '../core/services/document.service';
import { AnalyticsService } from '../core/services/analytics.service';
import { NotificationService } from '../core/services/notification.service';
import { DocumentSummary } from '../core/models/document.model';

const mockUser = { uid: 'u1', name: 'Alice', email: 'a@e.com' };

function makeDoc(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    id: 'd1', title: 'Untitled', word_count: 0, revision: 1, owner_id: 'u1',
    updated_by: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z',
    ...overrides,
  };
}

function observable(value: unknown) {
  return { subscribe: (obs: any) => { if (typeof obs === 'function') { obs(value); } else { obs.next?.(value); } return { unsubscribe: () => {} }; } };
}

describe('Dashboard', () => {
  let component: Dashboard;
  let fixture: ReturnType<typeof TestBed.createComponent<Dashboard>>;
  let documentService: { list: ReturnType<typeof vi.fn>; create: ReturnType<typeof vi.fn>; delete: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    documentService = {
      list: vi.fn().mockReturnValue(observable([makeDoc({ id: 'd1', title: 'My Doc', owner_id: 'u1' }), makeDoc({ id: 'd2', title: 'Shared Doc', owner_id: 'other' })])),
      create: vi.fn().mockReturnValue(observable({ id: 'd3' })),
      delete: vi.fn().mockReturnValue(observable(undefined)),
    };

    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [
        provideHttpClient(), provideHttpClientTesting(), provideRouter([]),
        { provide: AuthService, useValue: { currentUser: vi.fn(() => ({ email: 'a@e.com' })), logout: vi.fn().mockResolvedValue(undefined) } },
        { provide: UserService, useValue: { getMe: vi.fn().mockReturnValue(observable(mockUser)) } },
        { provide: DocumentService, useValue: documentService },
        { provide: AnalyticsService, useValue: { getUserStats: vi.fn().mockReturnValue(observable({ total_documents: 2, total_versions: 5, total_words: 100, average_words_per_document: 50 })) } },
        { provide: NotificationService, useValue: { success: vi.fn(), error: vi.fn(), info: vi.fn() } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Dashboard);
    component = fixture.componentInstance;
    fixture.detectChanges(); // triggers ngOnInit
  });

  it('navigates to the editor when a document card is clicked', async () => {
    const router = TestBed.inject(Router);
    const navigateByUrl = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    fixture.detectChanges();
    const card: HTMLElement | null = fixture.nativeElement.querySelector('.document-card');
    expect(card).not.toBeNull();
    card!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await fixture.whenStable();
    expect(navigateByUrl).toHaveBeenCalled();
  });

  it('loads user and documents', () => {
    expect(component.user()?.name).toBe('Alice');
    expect(component.documents().length).toBe(2);
  });

  it('filters by search query', () => {
    component.searchControl.setValue('shared');
    expect(component.filteredDocuments().length).toBe(1);
    expect(component.filteredDocuments()[0].title).toBe('Shared Doc');
  });

  it('filters owned documents', () => {
    component.setFilter('owned');
    expect(component.filteredDocuments().length).toBe(1);
    expect(component.filteredDocuments()[0].title).toBe('My Doc');
  });

  it('filters shared documents', () => {
    component.setFilter('shared');
    expect(component.filteredDocuments().length).toBe(1);
    expect(component.filteredDocuments()[0].title).toBe('Shared Doc');
  });

  it('shows all documents with all filter', () => {
    component.setFilter('all');
    expect(component.filteredDocuments().length).toBe(2);
  });

  it('computes counts correctly', () => {
    expect(component.counts().all).toBe(2);
    expect(component.counts().owned).toBe(1);
    expect(component.counts().shared).toBe(1);
  });

  it('sorts by title descending then ascending', () => {
    component.setSortKey('title');
    expect(component.sortKey()).toBe('title');
    expect(component.sortAsc()).toBe(false);
    // First click sets to desc (Z->A): Shared Doc, My Doc
    expect(component.filteredDocuments()[0].title).toBe('Shared Doc');
    // Second click toggles to asc
    component.setSortKey('title');
    expect(component.sortAsc()).toBe(true);
    expect(component.filteredDocuments()[0].title).toBe('My Doc');
  });

  it('clears search', () => {
    component.searchControl.setValue('shared');
    component.clearSearch();
    expect(component.searchControl.value).toBe('');
  });

  it('identifies shared documents', () => {
    const shared = makeDoc({ owner_id: 'other' });
    expect(component.isShared(shared)).toBe(true);
    const owned = makeDoc({ owner_id: 'u1' });
    expect(component.isShared(owned)).toBe(false);
  });
});
