import { Component, computed, input, output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';

import { VersionSummary } from '../../core/models/version.model';
import { RelativeTimePipe } from '../../core/pipes/relative-time.pipe';

@Component({
  selector: 'app-version-history',
  imports: [MatButtonModule, MatIconModule, MatProgressSpinnerModule, MatTooltipModule, RelativeTimePipe],
  templateUrl: './version-history.html',
  styleUrl: './version-history.scss',
})
export class VersionHistory {
  readonly versions = input<VersionSummary[]>([]);
  readonly currentUserId = input('');
  readonly previewText = input<string | null>(null);
  readonly preview = output<VersionSummary>();
  readonly selectedId = signal<string | null>(null);
  readonly selected = computed(() => this.versions().find(v => v.id === this.selectedId()) ?? this.versions()[0]);

  selectVersion(version: VersionSummary): void {
    this.selectedId.set(version.id);
    this.preview.emit(version);
  }

  author(version: VersionSummary): string {
    return version.author_name || (version.created_by === this.currentUserId() ? 'You' : 'Collaborator');
  }
  readonly loading = input(false);
  readonly busy = input(false);
  readonly unsaved = input(false);
  readonly errorMessage = input<string | null>(null);
  readonly compare = output<{ version: VersionSummary; compareTo: string | null }>();
  readonly restore = output<VersionSummary>();
  readonly remove = output<VersionSummary>();
  readonly reload = output<void>();
  private readonly selectedComparison = signal('');
  readonly compareTo = computed(() => this.versions().some((version) => version.id === this.selectedComparison())
    ? this.selectedComparison() : '');
  readonly sourceLabels = { manual: 'Manual snapshot', autosave: 'Automatic checkpoint', before_restore: 'Before restore', restore: 'Restored' };

  selectComparison(event: Event): void {
    this.selectedComparison.set((event.target as HTMLSelectElement).value);
  }

  compareVersion(version: VersionSummary): void {
    this.compare.emit({ version, compareTo: this.compareTo() || null });
  }
}
