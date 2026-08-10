import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

/** Thin wrapper around MatSnackBar for consistent success/error toasts app-wide. */
@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly snackBar = inject(MatSnackBar);

  success(message: string): void {
    this.snackBar.open(message, 'Dismiss', {
      duration: 3500,
      panelClass: ['docintel-snackbar', 'docintel-snackbar-success'],
    });
  }

  error(message: string): void {
    this.snackBar.open(message, 'Dismiss', {
      duration: 6000,
      panelClass: ['docintel-snackbar', 'docintel-snackbar-error'],
    });
  }

  info(message: string): void {
    this.snackBar.open(message, 'Dismiss', {
      duration: 3500,
      panelClass: ['docintel-snackbar'],
    });
  }
}
