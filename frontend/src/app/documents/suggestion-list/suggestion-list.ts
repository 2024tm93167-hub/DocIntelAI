import { Component, computed, input, output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';

import { Suggestion, SuggestionStatus } from '../../core/models/suggestion.model';
import { RelativeTimePipe } from '../../core/pipes/relative-time.pipe';

@Component({
  selector: 'app-suggestion-list',
  imports: [MatButtonModule, MatIconModule, MatProgressSpinnerModule, MatTooltipModule, RelativeTimePipe],
  templateUrl: './suggestion-list.html',
  styleUrl: './suggestion-list.scss',
})
export class SuggestionList {
  readonly suggestions = input<Suggestion[]>([]);
  readonly loading = input(false);
  readonly analyzed = input(false);
  readonly analyzing = input(false);
  readonly analyze = output<void>();
  readonly busy = input(false);
  readonly unsaved = input(false);
  readonly selectionActive = input(false);
  readonly errorMessage = input<string | null>(null);
  readonly accept = output<Suggestion>();
  readonly reject = output<Suggestion>();
  readonly remove = output<Suggestion>();
  readonly reload = output<void>();

  private readonly filterSignal = signal<'all' | SuggestionStatus>('pending');
  readonly filter = computed(() => this.filterSignal());

  readonly filtered = computed(() => {
    const f = this.filterSignal();
    const list = this.suggestions();
    if (f === 'all') return list;
    return list.filter((s) => s.status === f);
  });

  readonly counts = computed(() => {
    const list = this.suggestions();
    return {
      pending: list.filter((s) => s.status === 'pending').length,
      accepted: list.filter((s) => s.status === 'accepted').length,
      rejected: list.filter((s) => s.status === 'rejected').length,
    };
  });

  readonly typeLabels: Record<string, string> = {
    grammar: 'Grammar', clarity: 'Clarity', tone: 'Tone', wordiness: 'Conciseness',
    spelling: 'Spelling', conciseness: 'Conciseness', readability: 'Readability', word_choice: 'Word choice',
    repetition: 'Repetition', alternative: 'Alternative', rewrite: 'Rewrite', other: 'Suggestion',
  };

  readonly statusClasses: Record<SuggestionStatus, string> = {
    pending: 'status-pending', accepted: 'status-accepted', rejected: 'status-rejected',
  };

  setFilter(f: 'all' | SuggestionStatus): void {
    this.filterSignal.set(f);
  }

  onAccept(suggestion: Suggestion): void {
    if (this.busy() || this.unsaved()) return;
    this.accept.emit(suggestion);
  }

  onReject(suggestion: Suggestion): void {
    if (this.busy()) return;
    this.reject.emit(suggestion);
  }

  onRemove(suggestion: Suggestion): void {
    if (this.busy()) return;
    this.remove.emit(suggestion);
  }
}
