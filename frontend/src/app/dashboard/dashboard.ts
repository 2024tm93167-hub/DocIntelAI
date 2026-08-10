import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { AuthService } from '../core/services/auth.service';
import { NotificationService } from '../core/services/notification.service';
import { UserService } from '../core/services/user.service';
import { AppUser } from '../core/models/user.model';

@Component({
  selector: 'app-dashboard',
  imports: [MatButtonModule, MatIconModule, MatMenuModule, MatProgressSpinnerModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly userService = inject(UserService);
  private readonly notifications = inject(NotificationService);
  private readonly router = inject(Router);

  readonly user = signal<AppUser | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.loadProfile();
  }

  loadProfile(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.userService.getMe().subscribe({
      next: (user) => {
        this.user.set(user);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not reach the DocIntel AI backend. Is it running?');
        this.loading.set(false);
      },
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
}
