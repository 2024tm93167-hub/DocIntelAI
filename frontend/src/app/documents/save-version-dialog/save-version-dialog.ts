import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

export interface SaveVersionData {
  label: string;
}

@Component({
  selector: 'app-save-version-dialog',
  imports: [MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule, FormsModule],
  templateUrl: './save-version-dialog.html',
  styleUrl: './save-version-dialog.scss',
})
export class SaveVersionDialog {
  readonly dialogRef = inject(MatDialogRef<SaveVersionDialog, string | null>);
  label = '';

  save(): void {
    const value = this.label.trim() || null;
    this.dialogRef.close(value);
  }

  cancel(): void {
    this.dialogRef.close(null);
  }
}
