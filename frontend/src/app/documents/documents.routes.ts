import { Routes } from '@angular/router';
import type { Editor } from './editor/editor';

export const DOCUMENTS_ROUTES: Routes = [
  {
    path: ':id',
    canDeactivate: [(component: Editor) => component.confirmLeave()],
    loadComponent: () => import('./editor/editor').then((m) => m.Editor),
  },
];
