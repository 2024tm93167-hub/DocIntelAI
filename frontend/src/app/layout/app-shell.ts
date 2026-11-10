import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatMenuModule } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';

import { AuthService } from '../core/services/auth.service';
import { UserService } from '../core/services/user.service';
import { NotificationService } from '../core/services/notification.service';
import { DocumentService } from '../core/services/document.service';
import { MetricsCollector } from '../core/services/metrics-collector.service';
import { AppUser } from '../core/models/user.model';
import { DocumentSummary } from '../core/models/document.model';

@Component({
  selector: 'app-shell',
  imports: [
    RouterOutlet,
    MatButtonModule,
    MatIconModule,
    MatListModule,
    MatMenuModule,
    MatTooltipModule,
  ],
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.scss',
})
export class AppShell {
  private readonly auth = inject(AuthService);
  private readonly userService = inject(UserService);
  private readonly notifications = inject(NotificationService);
  private readonly metrics = inject(MetricsCollector);
  private readonly router = inject(Router);
  private readonly documents = inject(DocumentService);
  readonly creating = signal(false);

  readonly user = signal<AppUser | null>(null);
  readonly collapsed = signal(false);
  readonly mobileOpen = signal(false);
  readonly metricsEnabled = this.metrics.enabled;

  readonly docsExpanded = signal(false);
  readonly sidebarDocs = signal<DocumentSummary[]>([]);
  readonly docsLoading = signal(false);
  readonly docsError = signal(false);

  readonly initials = computed(() => {
    const source = this.user()?.name ?? this.auth.currentUser()?.email ?? '?';
    return source.trim().charAt(0).toUpperCase();
  });

  constructor() {
    this.userService.getMe().subscribe({
      next: (user) => this.user.set(user),
      error: () => {},
    });
  }

  toggleCollapsed(): void {
    this.collapsed.update((v) => !v);
    try {
      localStorage.setItem('docintel.sidebarCollapsed', String(this.collapsed()));
    } catch {
      // ignore storage errors
    }
  }

  toggleMobile(): void {
    this.mobileOpen.update((v) => !v);
  }

  closeMobile(): void {
    this.mobileOpen.set(false);
  }

  ngOnInit(): void {
    try {
      this.collapsed.set(localStorage.getItem('docintel.sidebarCollapsed') === 'true');
    } catch {
      // ignore
    }
  }

  goDashboard(): void {
    this.closeMobile();
    void this.router.navigate(['/dashboard']);
  }

  toggleDocuments(): void {
    this.docsExpanded.update((v) => !v);
    if (this.docsExpanded()) {
      this.loadSidebarDocs();
    }
    void this.router.navigate(['/dashboard']);
  }

  loadSidebarDocs(): void {
    this.docsLoading.set(true);
    this.docsError.set(false);
    this.documents.list().subscribe({
      next: (docs) => {
        this.sidebarDocs.set(docs);
        this.docsLoading.set(false);
      },
      error: () => {
        this.docsLoading.set(false);
        this.docsError.set(true);
      },
    });
  }

  openSidebarDoc(id: string): void {
    this.closeMobile();
    void this.router.navigate(['/documents', id]);
  }

  isActiveDoc(id: string): boolean {
    return this.router.url.includes(`/documents/${id}`);
  }

  goNewDocument(): void {
    if (this.creating()) return;
    this.creating.set(true);
    this.documents.create().subscribe({
      next: document => {
        this.creating.set(false);
        this.closeMobile();
        this.metrics.recordDocumentCreated();
        if (this.docsExpanded()) {
          this.loadSidebarDocs();
        }
        void this.router.navigate(['/documents', document.id]);
      },
      error: () => {
        this.creating.set(false);
        this.notifications.error('Could not create a document. Please try again.');
      },
    });
  }

  isActive(path: string): boolean {
    return this.router.url.includes(path);
  }

  async logout(): Promise<void> {
    await this.auth.logout();
    this.notifications.info('You have been signed out.');
    await this.router.navigateByUrl('/auth/login');
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
}
