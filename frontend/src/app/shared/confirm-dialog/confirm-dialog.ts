import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogActions, MatDialogClose, MatDialogContent, MatDialogRef, MatDialogTitle } from '@angular/material/dialog';

import { ConfirmDialogData } from '../../core/models/confirm-dialog-data.model';

@Component({
  selector: 'app-confirm-dialog',
  imports: [MatButtonModule, MatDialogActions, MatDialogClose, MatDialogContent, MatDialogTitle],
  templateUrl: './confirm-dialog.html',
  styleUrl: './confirm-dialog.scss',
})
export class ConfirmDialog {
  readonly data = inject<ConfirmDialogData>(MAT_DIALOG_DATA);
  readonly dialogRef = inject(MatDialogRef<ConfirmDialog, boolean>);
}
