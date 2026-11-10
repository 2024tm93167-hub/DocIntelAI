import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SuggestionList } from './suggestion-list';
import { Suggestion } from '../../core/models/suggestion.model';

const pending: Suggestion = {
  id: 's1', document_id: 'doc', user_id: 'owner', type: 'grammar',
  original_text: 'hello', suggested_text: 'Hello', reason: 'Capitalize',
  status: 'pending', document_revision: 1, created_at: null, resolved_at: null, resolved_by: null,
};
const accepted: Suggestion = { ...pending, id: 's2', status: 'accepted' };
const rejected: Suggestion = { ...pending, id: 's3', status: 'rejected' };

describe('SuggestionList', () => {
  let fixture: ComponentFixture<SuggestionList>;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [SuggestionList] });
    fixture = TestBed.createComponent(SuggestionList);
    fixture.componentRef.setInput('suggestions', [pending, accepted, rejected]);
    fixture.detectChanges();
  });

  it('shows only pending by default and displays counts', () => {
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Pending (1)');
    expect(text).toContain('Accepted (1)');
    expect(text).toContain('Rejected (1)');
    expect(fixture.nativeElement.querySelector('.suggestion-item.status-pending')).toBeTruthy();
    expect(fixture.nativeElement.querySelectorAll('.suggestion-item').length).toBe(1);
  });

  it('shows all when the All filter is clicked', () => {
    fixture.nativeElement.querySelector('.filter-chip:last-child').click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('.suggestion-item').length).toBe(3);
  });

  it('emits accept with the suggestion', () => {
    const accept = vi.fn();
    fixture.componentInstance.accept.subscribe(accept);
    fixture.nativeElement.querySelector('[aria-label="Accept suggestion"]').click();
    expect(accept).toHaveBeenCalledWith(pending);
  });

  it('emits reject with the suggestion', () => {
    const reject = vi.fn();
    fixture.componentInstance.reject.subscribe(reject);
    fixture.nativeElement.querySelector('[aria-label="Dismiss suggestion"]').click();
    expect(reject).toHaveBeenCalledWith(pending);
  });

  it('disables accept while unsaved', () => {
    fixture.componentRef.setInput('unsaved', true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[aria-label="Accept suggestion"]').disabled).toBe(true);
  });

  it('shows an empty state when no suggestions match the filter', () => {
    fixture.componentRef.setInput('suggestions', []);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Analyze your document');
    fixture.componentRef.setInput('analyzed', true);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Looking good');
  });
});
