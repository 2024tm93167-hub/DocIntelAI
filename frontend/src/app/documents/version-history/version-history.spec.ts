import { ComponentFixture, TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { VersionHistory } from './version-history';
import { VersionSummary } from '../../core/models/version.model';

const version: VersionSummary = {
  id: 'first', document_id: 'doc', title: 'Document', label: 'First draft', word_count: 20,
  created_at: null, created_by: 'owner', author_name: 'Owner', source: 'manual',
  document_revision: 1, restored_from_version_id: null,
};

describe('VersionHistory', () => {
  let fixture: ComponentFixture<VersionHistory>;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [VersionHistory] });
    fixture = TestBed.createComponent(VersionHistory);
    fixture.componentRef.setInput('versions', [version, { ...version, id: 'second', label: 'Second draft' }]);
    fixture.detectChanges();
  });

  it('shows actor, source and document revision', () => {
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Saved by Owner');
    expect(text).toContain('Manual snapshot');
    expect(text).toContain('Document revision 1');
  });

  it('emits the two selected snapshot IDs for comparison', () => {
    const compare = vi.fn();
    fixture.componentInstance.compare.subscribe(compare);
    const select: HTMLSelectElement = fixture.nativeElement.querySelector('select');
    select.value = 'second';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    fixture.nativeElement.querySelector('[aria-label="Compare First draft"]').click();
    expect(compare).toHaveBeenCalledWith({ version, compareTo: 'second' });
    expect(fixture.nativeElement.querySelector('[aria-label="Compare Second draft"]')).toBeNull();
    fixture.nativeElement.querySelectorAll('.version-heading')[1].click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[aria-label="Compare Second draft"]').disabled).toBe(true);
  });

  it('blocks restore and current-document comparison while unsaved', () => {
    fixture.componentRef.setInput('unsaved', true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[aria-label="Restore First draft"]').disabled).toBe(true);
    expect(fixture.nativeElement.querySelector('[aria-label="Compare First draft"]').disabled).toBe(true);
  });

  it('resets comparison when the target snapshot has been removed', () => {
    const select: HTMLSelectElement = fixture.nativeElement.querySelector('select');
    select.value = 'second';
    select.dispatchEvent(new Event('change'));
    fixture.componentRef.setInput('versions', [version]);
    fixture.detectChanges();
    expect(fixture.componentInstance.compareTo()).toBe('');
  });

  it('shows an actionable empty state', () => {
    fixture.componentRef.setInput('versions', []);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Your history starts here');
  });

  it('labels automatic checkpoints distinctly from manual snapshots', () => {
    fixture.componentRef.setInput('versions', [
      { ...version, id: 'auto', label: 'Automatic checkpoint', source: 'autosave' },
    ]);
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Automatic checkpoint');
    expect(text).not.toContain('Manual snapshot');
  });
});
