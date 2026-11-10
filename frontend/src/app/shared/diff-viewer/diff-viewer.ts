import { Component, Inject, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';

import { DiffOut } from '../../core/models/version.model';

@Component({
  selector: 'app-diff-viewer',
  imports: [MatButtonModule, MatDialogModule, MatIconModule],
  templateUrl: './diff-viewer.html',
  styleUrl: './diff-viewer.scss',
})
export class DiffViewer {
  readonly dialogRef = inject(MatDialogRef<DiffViewer>);

  constructor(@Inject(MAT_DIALOG_DATA) public readonly data: DiffOut) {}

  close(): void {
    this.dialogRef.close();
  }
}
