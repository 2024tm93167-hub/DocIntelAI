import { Component, inject, output, Signal } from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';

import { Collaborator } from '../../core/models/collaborator.model';
import { RelativeTimePipe } from '../../core/pipes/relative-time.pipe';

export interface ShareDialogData {
  collaborators: Signal<Collaborator[]>;
  loading: Signal<boolean>;
  inviting: Signal<boolean>;
  error: Signal<string | null>;
}

@Component({
  selector: 'app-share-dialog',
  imports: [
    MatButtonModule, MatDialogModule, MatFormFieldModule, MatIconModule,
    MatInputModule, MatProgressSpinnerModule, MatSelectModule, ReactiveFormsModule,
    RelativeTimePipe,
  ],
  templateUrl: './share-dialog.html',
})
export class ShareDialog {
  private readonly dialogRef = inject(MatDialogRef<ShareDialog>);
  private readonly data = inject<ShareDialogData>(MAT_DIALOG_DATA);

  readonly collaborators = this.data.collaborators;
  readonly loading = this.data.loading;
  readonly inviting = this.data.inviting;
  readonly error = this.data.error;

  readonly invite = output<{ email: string; role: 'editor' | 'viewer' }>();
  readonly remove = output<Collaborator>();

  readonly emailControl = new FormControl<string>('', {
    nonNullable: true,
    validators: [Validators.required, Validators.email],
  });
  readonly roleControl = new FormControl<'editor' | 'viewer'>('viewer', { nonNullable: true });

  submitInvite(): void {
    if (this.emailControl.invalid || this.inviting()) return;
    this.invite.emit({ email: this.emailControl.value.trim(), role: this.roleControl.value });
    this.emailControl.reset('');
    this.roleControl.reset('viewer');
  }

  removeCollaborator(collab: Collaborator): void {
    this.remove.emit(collab);
  }

  close(): void {
    this.dialogRef.close();
  }
}
