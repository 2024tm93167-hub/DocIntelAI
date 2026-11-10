import { Component, ElementRef, OnInit, ViewChild, computed, inject, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { toSignal } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';

import { AuthService } from '../core/services/auth.service';
import { DocumentService } from '../core/services/document.service';
import { NotificationService } from '../core/services/notification.service';
import { UserService } from '../core/services/user.service';
import { AnalyticsService } from '../core/services/analytics.service';
import { MetricsCollector } from '../core/services/metrics-collector.service';
import { AppUser } from '../core/models/user.model';
import { DocumentSummary } from '../core/models/document.model';
import { UserStats } from '../core/models/analytics.model';
import { RelativeTimePipe } from '../core/pipes/relative-time.pipe';
import { ConfirmDialog } from '../shared/confirm-dialog/confirm-dialog';

type FilterTab = 'all' | 'owned' | 'shared';
type SortKey = 'updated' | 'created' | 'title' | 'words';

@Component({
  selector: 'app-dashboard',
  imports: [
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatTooltipModule,
    ReactiveFormsModule,
    RelativeTimePipe,
    RouterLink,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly userService = inject(UserService);
  private readonly documentService = inject(DocumentService);
  private readonly analyticsService = inject(AnalyticsService);
  private readonly notifications = inject(NotificationService);
  private readonly metrics = inject(MetricsCollector);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);

  @ViewChild('documentsSection') private documentsSection?: ElementRef<HTMLElement>;

  readonly user = signal<AppUser | null>(null);
  readonly documents = signal<DocumentSummary[]>([]);
  readonly userStats = signal<UserStats | null>(null);
  readonly loadingProfile = signal(true);
  readonly loadingDocuments = signal(true);
  readonly loadingStats = signal(true);
  readonly errorMessage = signal<string | null>(null);

  readonly searchControl = new FormControl<string>('', { nonNullable: true });
  readonly searchQuery = toSignal(this.searchControl.valueChanges, { initialValue: '' });
  readonly activeFilter = signal<FilterTab>('all');
  readonly sortKey = signal<SortKey>('updated');
  readonly sortAsc = signal(false);

  readonly filteredDocuments = computed<DocumentSummary[]>(() => {
    const query = (this.searchQuery() ?? '').trim().toLowerCase();
    const filter = this.activeFilter();
    const key = this.sortKey();
    const asc = this.sortAsc();
    const docs = this.documents();

    let result = docs;
    if (query) {
      result = result.filter((d) => d.title.toLowerCase().includes(query));
    }
    if (filter === 'owned') {
      result = result.filter((d) => d.owner_id === this.user()?.uid);
    } else if (filter === 'shared') {
      result = result.filter((d) => d.owner_id !== this.user()?.uid);
    }

    const sorted = [...result].sort((a, b) => {
      let cmp = 0;
      switch (key) {
        case 'title':
          cmp = a.title.localeCompare(b.title);
          break;
        case 'words':
          cmp = a.word_count - b.word_count;
          break;
        case 'created':
          cmp = (a.created_at ?? '').localeCompare(b.created_at ?? '');
          break;
        case 'updated':
        default:
          cmp = (a.updated_at ?? '').localeCompare(b.updated_at ?? '');
          break;
      }
      return asc ? cmp : -cmp;
    });
    return sorted;
  });

  readonly counts = computed(() => {
    const docs = this.documents();
    const uid = this.user()?.uid;
    return {
      all: docs.length,
      owned: docs.filter((d) => d.owner_id === uid).length,
      shared: docs.filter((d) => d.owner_id !== uid).length,
    };
  });

  readonly hasResults = computed(() => this.filteredDocuments().length > 0);

  ngOnInit(): void {
    this.loadProfile();
    this.loadDocuments();
    this.loadUserStats();
  }

  loadProfile(): void {
    this.loadingProfile.set(true);
    this.errorMessage.set(null);
    this.userService.getMe().subscribe({
      next: (user) => {
        this.user.set(user);
        this.loadingProfile.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not reach the DocIntel AI backend. Is it running?');
        this.loadingProfile.set(false);
      },
    });
  }

  loadDocuments(): void {
    this.loadingDocuments.set(true);
    this.documentService.list().subscribe({
      next: (documents) => {
        this.documents.set(documents);
        this.loadingDocuments.set(false);
      },
      error: () => {
        this.loadingDocuments.set(false);
      },
    });
  }

  isLoading(): boolean {
    return this.loadingProfile() || this.loadingDocuments() || this.loadingStats();
  }

  loadUserStats(): void {
    this.loadingStats.set(true);
    this.analyticsService.getUserStats().subscribe({
      next: (stats) => {
        this.userStats.set(stats);
        this.loadingStats.set(false);
      },
      error: () => {
        this.loadingStats.set(false);
      },
    });
  }

  setFilter(filter: FilterTab): void {
    this.activeFilter.set(filter);
  }

  setSortKey(key: SortKey): void {
    if (this.sortKey() === key) {
      this.sortAsc.update((v) => !v);
    } else {
      this.sortKey.set(key);
      this.sortAsc.set(false);
    }
  }

  clearSearch(): void {
    this.searchControl.setValue('');
  }

  createDocument(): void {
    this.documentService.create().subscribe({
      next: (document) => {
        this.metrics.recordDocumentCreated();
        this.notifications.success('New document created.');
        void this.router.navigate(['/documents', document.id]);
      },
      error: () => {
        this.notifications.error('Could not create a new document.');
      },
    });
  }

  openDocument(id: string): void {
    void this.router.navigate(['/documents', id]);
  }

  scrollToDocuments(): void {
    this.documentsSection?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  deleteDocument(event: MouseEvent, document: DocumentSummary): void {
    event.stopPropagation();
    const dialogRef = this.dialog.open(ConfirmDialog, {
      data: {
        title: 'Delete document?',
        message: `This will permanently delete "${document.title}". This action cannot be undone.`,
        confirmText: 'Delete',
        cancelText: 'Cancel',
      },
      width: '380px',
    });

    dialogRef.afterClosed().subscribe((confirmed) => {
      if (!confirmed) return;

      this.documentService.delete(document.id).subscribe({
        next: () => {
          this.documents.update((docs) => docs.filter((d) => d.id !== document.id));
          this.notifications.success('Document deleted.');
        },
        error: () => {
          this.notifications.error('Could not delete document.');
        },
      });
    });
  }

  async logout(): Promise<void> {
    await this.auth.logout();
    this.notifications.info('You have been signed out.');
    await this.router.navigateByUrl('/auth/login');
  }

  initials(): string {
    const source = this.user()?.name ?? this.auth.currentUser()?.email ?? '?';
    return source.trim().charAt(0).toUpperCase();
  }

  isShared(doc: DocumentSummary): boolean {
    return doc.owner_id !== this.user()?.uid;
  }

  toggleMetrics(): void {
    this.metrics.toggle();
    if (this.metrics.enabled()) {
      this.notifications.info('Metrics collection enabled.');
    } else {
      this.notifications.info('Metrics collection disabled.');
    }
  }

  exportMetrics(): void {
    this.metrics.downloadJson();
    this.notifications.success('Metrics exported as JSON.');
  }

  readonly metricsEnabled = this.metrics.enabled;
}
