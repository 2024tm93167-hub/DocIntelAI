import {
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  NgZone,
  OnDestroy,
  OnInit,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { TitleCasePipe } from '@angular/common';

import { VersionHistory } from '../version-history/version-history';
import { SuggestionList } from '../suggestion-list/suggestion-list';
import { Editor as TiptapEditor } from '@tiptap/core';
import { Highlight } from '@tiptap/extension-highlight';
import { Image } from '@tiptap/extension-image';
import { TaskItem, TaskList } from '@tiptap/extension-list';
import { Placeholder } from '@tiptap/extension-placeholder';
import { Subscript } from '@tiptap/extension-subscript';
import { Superscript } from '@tiptap/extension-superscript';
import { Table, TableCell, TableHeader, TableRow } from '@tiptap/extension-table';
import { TextAlign } from '@tiptap/extension-text-align';
import { TextStyleKit } from '@tiptap/extension-text-style';
import { StarterKit } from '@tiptap/starter-kit';
import { RemoteCursors } from './remote-cursors.extension';
import { Observable, Subscription, distinctUntilChanged, finalize, map } from 'rxjs';

import { Indent } from './indent-extension';
import { PageBreaks } from './page-breaks';
import { aiOutputToHtml, aiOutputToNodes, docToMarkdown } from './ai-output';

import { DocumentService } from '../../core/services/document.service';
import { NotificationService } from '../../core/services/notification.service';
import { VersionService } from '../../core/services/version.service';
import { AiService } from '../../core/services/ai.service';
import { SuggestionService } from '../../core/services/suggestion.service';
import { SharingService } from '../../core/services/sharing.service';
import { DocumentWsService } from '../../core/services/document-ws.service';
import { AuthService } from '../../core/services/auth.service';
import { MetricsCollector } from '../../core/services/metrics-collector.service';
import { AnalyticsService } from '../../core/services/analytics.service';
import { DocumentAutosaveService } from '../../core/services/document-autosave.service';
import { ConfirmDialog } from '../../shared/confirm-dialog/confirm-dialog';
import { VersionSummary } from '../../core/models/version.model';
import { AiMode, AI_TONES } from '../../core/models/ai.model';
import { DocumentStats, ExportFormat, ReadabilityResult } from '../../core/models/analytics.model';
import { SaveVersionDialog } from '../save-version-dialog/save-version-dialog';
import { ShareDialog } from '../share-dialog/share-dialog';
import { DiffViewer } from '../../shared/diff-viewer/diff-viewer';

interface ToolbarState {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  strike: boolean;
  code: boolean;
  subscript: boolean;
  superscript: boolean;
  heading: number;
  bulletList: boolean;
  orderedList: boolean;
  taskList: boolean;
  blockquote: boolean;
  align: 'left' | 'center' | 'right' | 'justify';
  fontFamily: string;
  fontSize: string;
  color: string;
  highlight: string;
}

@Component({
  selector: 'app-editor',
  providers: [DocumentAutosaveService],
  imports: [
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatMenuModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    ReactiveFormsModule,
    TitleCasePipe,
    VersionHistory,
    SuggestionList,
  ],
  templateUrl: './editor.html',
  styleUrl: './editor.scss',
})
export class Editor implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly documentService = inject(DocumentService);
  private readonly versionService = inject(VersionService);
  private readonly aiService = inject(AiService);
  private readonly suggestionService = inject(SuggestionService);
  private readonly sharingService = inject(SharingService);
  private readonly wsService = inject(DocumentWsService);
  private readonly authService = inject(AuthService);
  private readonly metrics = inject(MetricsCollector);
  readonly presenceUsers = this.wsService.presenceUsers;
  readonly wsConnected = this.wsService.connected;
  readonly metricsEnabled = this.metrics.enabled;
  private readonly analyticsService = inject(AnalyticsService);
  private readonly notifications = inject(NotificationService);
  private readonly dialog = inject(MatDialog);
  private readonly zone = inject(NgZone);
  private readonly destroyRef = inject(DestroyRef);

  readonly editorRef = viewChild<ElementRef<HTMLDivElement>>('editorElement');
  readonly fileInputRef = viewChild<ElementRef<HTMLInputElement>>('fileInput');
  readonly composerInputRef = viewChild<ElementRef<HTMLTextAreaElement>>('composerInput');

  readonly autosave = inject(DocumentAutosaveService);
  readonly document = this.autosave.document;
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly saveStatus = this.autosave.status;
  readonly wordCount = signal(0);
  readonly characterCount = signal(0);
  readonly pageCount = signal(1);
  readonly selectedPreview = signal('');
  readonly zoom = signal(100);
  readonly fitPage = signal(true);
  readonly currentUserId = computed(() => this.authService.currentUser()?.uid ?? '');
  readonly titleOptions = signal<string[]>([]);
  readonly titlesLoading = signal(false);
  readonly analysisPerformed = signal(false);
  readonly analyzing = signal(false);
  readonly applyingSuggestion = signal(false);
  readonly editingLocked = computed(() => this.restoringVersion() || this.applyingSuggestion());
  private analysisSubscription: Subscription | null = null;
  private titleSubscription: Subscription | null = null;
  private titleTarget: { document: TiptapEditor['state']['doc']; title: string } | null = null;
  readonly quickActions: { mode: AiMode; label: string }[] = [
    { mode: 'improve', label: 'Improve writing' }, { mode: 'grammar', label: 'Fix grammar' },
    { mode: 'rewrite', label: 'Rewrite' }, { mode: 'condense', label: 'Shorten' },
    { mode: 'expand', label: 'Expand' }, { mode: 'summarize', label: 'Summarize' },
    { mode: 'continue', label: 'Continue writing' }, { mode: 'outline', label: 'Generate outline' },
    { mode: 'heading', label: 'Generate heading' }, { mode: 'headings', label: 'Section headings' },
  ];
  readonly aiResultLabel = computed(() => this.quickActions.find(a => a.mode === this.aiMode())?.label ?? 'AI draft');
  readonly aiPreviewHtml = computed(() => aiOutputToHtml(this.aiOutput()));

  readonly versions = signal<VersionSummary[]>([]);
  readonly versionsLoading = signal(false);
  readonly savingVersion = signal(false);
  readonly restoringVersion = signal(false);
  readonly versionError = signal<string | null>(null);
  readonly snapshotPreview = signal<string | null>(null);
  private previewSubscription: Subscription | null = null;

  previewVersion(version: VersionSummary): void {
    const doc = this.document();
    if (!doc) return;
    this.previewSubscription?.unsubscribe();
    this.snapshotPreview.set('Loading preview…');
    this.previewSubscription = this.versionService.get(doc.id, version.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: snapshot => {
        const extract = (node: Record<string, unknown>): string => typeof node['text'] === 'string' ? node['text']
          : (Array.isArray(node['content']) ? node['content'].map(extract).join('') : '')
            + (['paragraph', 'heading'].includes(String(node['type'])) ? '\n' : '');
        this.snapshotPreview.set(extract(snapshot.content) || 'Empty document');
      },
      error: () => this.snapshotPreview.set('Could not load this preview. Select the version to retry.'),
    });
  }

  readonly suggestions = signal<import('../../core/models/suggestion.model').Suggestion[]>([]);
  readonly suggestionsLoading = signal(false);
  readonly suggestionsError = signal<string | null>(null);

  readonly collaborators = signal<import('../../core/models/collaborator.model').Collaborator[]>([]);
  readonly shareLoading = signal(false);
  readonly shareInviting = signal(false);
  readonly shareError = signal<string | null>(null);

  readonly sidePanelOpen = signal(window.innerWidth > 1100);
  readonly sidePanelTab = signal<'versions' | 'ai' | 'suggestions' | 'stats'>('ai');
  private readonly viewportWidth = signal(window.innerWidth);
  readonly panelMaxWidth = computed(() => Math.min(360, Math.max(260, this.viewportWidth() - 480)));
  readonly sidePanelWidth = signal(this.readPanelWidth());
  readonly panelResizing = signal(false);
  private panelResizeCleanup: (() => void) | null = null;

  readonly aiMode = signal<AiMode>('improve');
  readonly aiInstruction = new FormControl<string>('', { nonNullable: true });
  readonly aiPrompt = new FormControl<string>('', { nonNullable: true });
  readonly aiMaxWords = new FormControl<number>(100, { nonNullable: true });
  readonly aiTone = new FormControl<string>('professional', { nonNullable: true });
  readonly aiTones = AI_TONES;
  readonly aiOutput = signal<string>('');
  readonly aiSelectionActive = signal(false);
  readonly aiLoading = signal(false);
  readonly aiError = signal<string | null>(null);
  private aiStreamSub: Subscription | null = null;
  private aiTarget: { from: number; to: number; document: TiptapEditor['state']['doc'] } | null = null;

  readonly documentStats = signal<DocumentStats | null>(null);
  readonly readability = signal<ReadabilityResult | null>(null);
  readonly statsLoading = signal(false);

  readonly titleControl = new FormControl<string>('', {
    nonNullable: true,
    validators: [Validators.required, Validators.maxLength(200)],
  });

  readonly toolbar = signal<ToolbarState>({
    bold: false,
    italic: false,
    underline: false,
    strike: false,
    code: false,
    subscript: false,
    superscript: false,
    heading: 0,
    bulletList: false,
    orderedList: false,
    taskList: false,
    blockquote: false,
    align: 'left',
    fontFamily: '',
    fontSize: '',
    color: '',
    highlight: '',
  });

  readonly headingLevels: number[] = [0, 1, 2, 3, 4, 5, 6];

  readonly fontFamilyOptions: { label: string; value: string }[] = [
    { label: 'Default', value: '' },
    { label: 'Arial', value: 'Arial, sans-serif' },
    { label: 'Georgia', value: 'Georgia, serif' },
    { label: 'Times New Roman', value: '"Times New Roman", serif' },
    { label: 'Courier New', value: '"Courier New", monospace' },
    { label: 'Verdana', value: 'Verdana, sans-serif' },
    { label: 'Trebuchet MS', value: '"Trebuchet MS", sans-serif' },
    { label: 'Comic Sans MS', value: '"Comic Sans MS", cursive' },
  ];

  readonly fontSizeOptions: string[] = [
    '12px', '14px', '16px', '18px', '20px', '24px', '28px', '32px', '40px', '48px',
  ];

  readonly lineHeightOptions: { label: string; value: string }[] = [
    { label: 'Single', value: '1' },
    { label: '1.15', value: '1.15' },
    { label: '1.5', value: '1.5' },
    { label: 'Double', value: '2' },
  ];

  readonly textColorPalette: string[] = [
    '#000000', '#434343', '#666666', '#999999', '#b7b7b7', '#ffffff',
    '#980000', '#ff0000', '#ff9900', '#ffff00', '#00ff00', '#00ffff',
    '#4a86e8', '#0000ff', '#9900ff', '#ff00ff',
  ];

  readonly highlightPalette: string[] = [
    '#fff59d', '#ffe082', '#ffab91', '#ef9a9a', '#f48fb1',
    '#ce93d8', '#b39ddb', '#90caf9', '#80deea', '#a5d6a7',
  ];

  private editor: TiptapEditor | null = null;
  private editorReady = false;
  private loadSubscription: Subscription | null = null;
  private hasPendingContent = false;

  private readonly placeholderClass = 'is-empty';

  constructor() {
    effect(() => {
      if (this.loading() || this.loadError() || this.editor || this.editorReady) return;
      const ref = this.editorRef();
      if (!ref) return;
      this.initEditor();
    });

    effect(() => {
      const cursors = this.remoteCursors();
      if (!this.editor || !this.editorReady) return;
      const storage = this.editor.storage as { remoteCursors?: { setCursors: (c: Record<string, unknown>) => void } };
      storage.remoteCursors?.setCursors(cursors);
    });

    effect(() => {
      this.zoom();
      this.fitPage();
      const ed = this.editor;
      if (!ed || !this.editorReady) return;
      requestAnimationFrame(() => {
        const storage = ed.storage as { pageBreaks?: { refresh?: () => void } };
        storage.pageBreaks?.refresh?.();
      });
    });

    this.titleControl.valueChanges
      .pipe(distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.scheduleSave());
  }

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const id = params.get('id');
      if (!id) {
        this.loadError.set('Document id is missing.');
        this.loading.set(false);
        return;
      }
      this.loadDocument(id);
    });
  }

  ngOnDestroy(): void {
    this.autosave.ngOnDestroy();
    this.aiStreamSub?.unsubscribe();
    this.analysisSubscription?.unsubscribe();
    this.titleSubscription?.unsubscribe();
    this.previewSubscription?.unsubscribe();
    this.panelResizeCleanup?.();
    this.wsService.disconnect();
    this.editor?.destroy();
    this.editor = null;
  }

  private clampPanelWidth(width: number): number {
    return Math.min(this.panelMaxWidth(), Math.max(260, Number.isFinite(width) ? width : 320));
  }

  private readPanelWidth(): number {
    try {
      return this.clampPanelWidth(Number(localStorage.getItem('docintel.panelWidth')) || 320);
    } catch {
      return this.clampPanelWidth(320);
    }
  }

  private persistPanelWidth(): void {
    try {
      localStorage.setItem('docintel.panelWidth', String(this.sidePanelWidth()));
    } catch {
      return;
    }
  }

  @HostListener('window:resize')
  resizeViewport(): void {
    this.panelResizeCleanup?.();
    this.viewportWidth.set(window.innerWidth);
    this.sidePanelWidth.update((width) => this.clampPanelWidth(width));
  }

  resizePanelWithKeyboard(event: KeyboardEvent): void {
    const widths: Record<string, number> = {
      ArrowLeft: this.sidePanelWidth() + 20, ArrowRight: this.sidePanelWidth() - 20,
      Home: 260, End: this.panelMaxWidth(),
    };
    if (!(event.key in widths)) return;
    event.preventDefault();
    this.sidePanelWidth.set(this.clampPanelWidth(widths[event.key]));
    this.persistPanelWidth();
  }

  startPanelResize(event: PointerEvent): void {
    if (event.button !== 0 || !event.isPrimary) return;
    event.preventDefault();
    this.panelResizeCleanup?.();
    const startX = event.clientX;
    const startWidth = this.sidePanelWidth();
    const previousSelect = document.body.style.userSelect;
    const previousCursor = document.body.style.cursor;

    const onMove = (e: PointerEvent) => {
      if (e.pointerId !== event.pointerId) return;
      this.zone.run(() => this.sidePanelWidth.set(this.clampPanelWidth(startWidth + startX - e.clientX)));
    };
    const onUp = () => {
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onPointerEnd);
      document.removeEventListener('pointercancel', onPointerEnd);
      window.removeEventListener('blur', onUp);
      document.body.style.userSelect = previousSelect;
      document.body.style.cursor = previousCursor;
      this.zone.run(() => this.panelResizing.set(false));
      this.panelResizeCleanup = null;
      this.persistPanelWidth();
    };
    const onPointerEnd = (e: PointerEvent) => {
      if (e.pointerId === event.pointerId) onUp();
    };

    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onPointerEnd);
    document.addEventListener('pointercancel', onPointerEnd);
    window.addEventListener('blur', onUp);
    this.panelResizing.set(true);
    this.panelResizeCleanup = onUp;
  }

  private loadDocument(id: string): void {
    this.loadSubscription?.unsubscribe();
    this.analysisSubscription?.unsubscribe();
    this.titleSubscription?.unsubscribe();
    this.previewSubscription?.unsubscribe();
    this.titleOptions.set([]);
    this.snapshotPreview.set(null);
    this.suggestions.set([]);
    this.analysisPerformed.set(false);
    this.autosave.ngOnDestroy();
    this.setAiMode(this.aiMode());
    this.destroyEditor();
    this.loading.set(true);
    this.loadError.set(null);
    this.loadSubscription = this.documentService.get(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (doc) => {
        this.autosave.initialize(doc);
        this.titleControl.setValue(doc.title, { emitEvent: false });
        this.wordCount.set(doc.word_count);
        this.loading.set(false);
        this.applyDocumentContent(doc.content);
        this.loadVersions();
        this.connectPresence(doc.id);
        this.metrics.recordDocumentOpened();
      },
      error: (err) => {
        const message = err.status === 404 ? 'Document not found.' : 'Could not load this document.';
        this.loadError.set(message);
        this.loading.set(false);
        this.destroyEditor();
      },
    });
  }

  private connectPresence(documentId: string): void {
    this.authService.getIdToken().then((token) => {
      if (token) this.wsService.connect(documentId, token);
    });
  }

  private applyDocumentContent(content: Record<string, unknown>): void {
    if (!this.editor) {
      this.hasPendingContent = true;
      return;
    }
    this.editor.commands.setContent(content, { emitUpdate: false });
    this.wordCount.set(this.countWords());
  }

  private destroyEditor(): void {
    this.editor?.destroy();
    this.editor = null;
    this.editorReady = false;
  }

  private initEditor(): void {
    const element = this.editorRef()?.nativeElement;
    if (this.editor || !element) return;

    this.editor = new TiptapEditor({
      element,
      extensions: [
        StarterKit.configure({
          heading: { levels: [1, 2, 3, 4, 5, 6] },
          dropcursor: false,
          link: { openOnClick: false },
        }),
        Subscript,
        Superscript,
        Placeholder.configure({
          placeholder: 'Start writing your document here…',
          emptyEditorClass: this.placeholderClass,
        }),
        TextStyleKit,
        TextAlign.configure({ types: ['heading', 'paragraph'] }),
        Highlight.configure({ multicolor: true }),
        Indent,
        Image,
        TaskList,
        TaskItem.configure({ nested: true }),
        Table.configure({ resizable: false }),
        TableRow,
        TableHeader,
        TableCell,
        RemoteCursors.configure({ cursors: {} }),
        PageBreaks.configure({
          onPageCount: (count: number) => this.zone.run(() => this.pageCount.set(count)),
        }),
      ],
      content: { type: 'doc', content: [{ type: 'paragraph' }] },
      autofocus: 'start',
      onCreate: () => {
        this.editorReady = true;
        if (this.hasPendingContent) {
          const doc = this.document();
          if (doc) {
            this.editor?.commands.setContent(doc.content, { emitUpdate: false });
          }
          this.hasPendingContent = false;
        }
        this.wordCount.set(this.countWords());
      },
      onUpdate: ({ editor }) => {
        this.zone.run(() => {
          const count = editor.getText().trim().split(/\s+/).filter(Boolean).length;
          this.wordCount.set(count);
          this.metrics.recordKeystroke();
          this.scheduleSave();
        });
      },
      onSelectionUpdate: ({ editor }) => {
        this.zone.run(() => {
          this.updateToolbarState(editor);
          this.broadcastCursor(editor);
        });
      },
      onTransaction: ({ editor }) => {
        this.zone.run(() => this.updateToolbarState(editor));
      },
    });

  }

  private countWords(): number {
    this.characterCount.set(this.editor?.getText().length ?? 0);
    return this.editor?.getText().trim().split(/\s+/).filter(Boolean).length ?? 0;
  }

  changeZoom(delta: number): void {
    this.fitPage.set(false);
    this.zoom.update(value => Math.min(150, Math.max(50, value + delta)));
  }

  private updateToolbarState(editor: TiptapEditor): void {
    const { from, to } = editor.state.selection;
    this.selectedPreview.set(from === to ? '' : editor.state.doc.textBetween(from, to, ' ').slice(0, 180));
    this.characterCount.set(editor.getText().length);
    this.toolbar.set({
      bold: editor.isActive('bold'),
      italic: editor.isActive('italic'),
      underline: editor.isActive('underline'),
      strike: editor.isActive('strike'),
      code: editor.isActive('code'),
      subscript: editor.isActive('subscript'),
      superscript: editor.isActive('superscript'),
      heading: this.activeHeadingLevel(editor),
      bulletList: editor.isActive('bulletList'),
      orderedList: editor.isActive('orderedList'),
      taskList: editor.isActive('taskList'),
      blockquote: editor.isActive('blockquote'),
      align: this.activeAlign(editor),
      fontFamily: (editor.getAttributes('textStyle')['fontFamily'] as string) ?? '',
      fontSize: (editor.getAttributes('textStyle')['fontSize'] as string) ?? '',
      color: (editor.getAttributes('textStyle')['color'] as string) ?? '',
      highlight: (editor.getAttributes('highlight')['color'] as string) ?? '',
    });
  }

  private broadcastCursor(editor: TiptapEditor): void {
    if (!this.wsConnected()) return;
    const { from, to, empty } = editor.state.selection;
    this.wsService.sendCursor(from, to, empty);
  }

  readonly remoteCursors = this.wsService.remoteCursors;

  private activeHeadingLevel(editor: TiptapEditor): number {
    for (let level = 1; level <= 6; level++) {
      if (editor.isActive('heading', { level })) return level;
    }
    return 0;
  }

  private activeAlign(editor: TiptapEditor): 'left' | 'center' | 'right' | 'justify' {
    if (editor.isActive({ textAlign: 'center' })) return 'center';
    if (editor.isActive({ textAlign: 'right' })) return 'right';
    if (editor.isActive({ textAlign: 'justify' })) return 'justify';
    return 'left';
  }

  private scheduleSave(): void {
    if (!this.editorReady || this.loadError() || !this.editor) return;
    this.autosave.queue({ title: this.titleControl.value.trim(), content: this.editor.getJSON() });
  }

  @HostListener('window:beforeunload', ['$event'])
  protectUnsavedDraft(event: BeforeUnloadEvent): void {
    if (this.autosave.hasUnsavedChanges() || this.editingLocked()) event.preventDefault();
  }

  confirmLeave(): boolean | Observable<boolean> {
    if (this.editingLocked()) {
      this.notifications.info('Please wait for the document update to finish.');
      return false;
    }
    if (!this.autosave.hasUnsavedChanges()) return true;
    return this.dialog.open(ConfirmDialog, {
      data: {
        title: 'Leave with unsaved changes?',
        message: 'Your latest edits have not been saved. Stay to retry saving or download your local draft.',
        confirmText: 'Leave without saving', cancelText: 'Keep editing',
      },
      width: '420px',
    }).afterClosed().pipe(map(Boolean));
  }

  downloadLocalDraft(): void {
    if (!this.editor) return;
    const draft = { title: this.titleControl.value, content: this.editor.getJSON(), text: this.editor.getText() };
    const url = URL.createObjectURL(new Blob([JSON.stringify(draft, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'docintel-local-draft.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  reloadLatestDocument(): void {
    if (this.restoringVersion()) return;
    const id = this.document()?.id;
    if (!id) return;
    this.dialog.open(ConfirmDialog, {
      data: {
        title: 'Load the latest saved document?',
        message: 'This replaces your local draft. Download it first if you want to keep your unsaved changes.',
        confirmText: 'Load latest', cancelText: 'Keep local draft',
      },
      width: '420px',
    }).afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe((confirmed) => {
      if (!confirmed) return;
      this.documentService.get(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: (doc) => {
          this.autosave.initialize(doc);
          this.titleControl.setValue(doc.title, { emitEvent: false });
          this.applyDocumentContent(doc.content);
          this.versionError.set(null);
          this.loadVersions();
        },
        error: () => this.notifications.error('Could not reload. Your local draft has been kept.'),
      });
    });
  }

  // Toolbar actions
  toggleBold(): void {
    this.editor?.chain().focus().toggleBold().run();
  }

  toggleItalic(): void {
    this.editor?.chain().focus().toggleItalic().run();
  }

  toggleUnderline(): void {
    this.editor?.chain().focus().toggleUnderline().run();
  }

  toggleStrike(): void {
    this.editor?.chain().focus().toggleStrike().run();
  }

  toggleCode(): void {
    this.editor?.chain().focus().toggleCode().run();
  }

  setHeadingLevel(level: number): void {
    if (!this.editor) return;
    if (level === 0) {
      this.editor.chain().focus().setParagraph().run();
      return;
    }
    this.editor.chain().focus().setHeading({ level: level as 1 | 2 | 3 | 4 | 5 | 6 }).run();
  }

  toggleSubscript(): void {
    this.editor?.chain().focus().toggleSubscript().run();
  }

  toggleSuperscript(): void {
    this.editor?.chain().focus().toggleSuperscript().run();
  }

  setAlign(align: 'left' | 'center' | 'right' | 'justify'): void {
    this.editor?.chain().focus().setTextAlign(align).run();
  }

  setFontFamily(font: string): void {
    if (!this.editor) return;
    if (!font) {
      this.editor.chain().focus().unsetFontFamily().run();
      return;
    }
    this.editor.chain().focus().setFontFamily(font).run();
  }

  setFontSize(size: string): void {
    this.editor?.chain().focus().setFontSize(size).run();
  }

  resetFontSize(): void {
    this.editor?.chain().focus().unsetFontSize().run();
  }

  setTextColor(color: string): void {
    this.editor?.chain().focus().setColor(color).run();
  }

  resetTextColor(): void {
    this.editor?.chain().focus().unsetColor().run();
  }

  setHighlightColor(color: string): void {
    this.editor?.chain().focus().setHighlight({ color }).run();
  }

  resetHighlight(): void {
    this.editor?.chain().focus().unsetHighlight().run();
  }

  setLineHeight(value: string): void {
    this.editor?.chain().focus().setLineHeight(value).run();
  }

  indentSelection(): void {
    this.editor?.chain().focus().indent().run();
  }

  outdentSelection(): void {
    this.editor?.chain().focus().outdent().run();
  }

  insertHorizontalRule(): void {
    this.editor?.chain().focus().setHorizontalRule().run();
  }

  clearFormatting(): void {
    this.editor?.chain().focus().unsetAllMarks().clearNodes().run();
  }

  triggerImageUpload(): void {
    this.fileInputRef()?.nativeElement.click();
  }

  onImageFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    const target = this.editor;
    const content = target?.state.doc;
    const reader = new FileReader();
    reader.onload = () => {
      if (!target || !content || this.editor !== target || this.restoringVersion() || !target.state.doc.eq(content)) return;
      const src = reader.result as string;
      target.chain().focus().setImage({ src }).run();
    };
    reader.readAsDataURL(file);
    input.value = '';
  }

  insertImageFromUrl(): void {
    const url = window.prompt('Enter an image URL');
    if (!url) return;
    this.editor?.chain().focus().setImage({ src: url }).run();
  }

  toggleTaskList(): void {
    this.editor?.chain().focus().toggleTaskList().run();
  }

  addColumnAfter(): void {
    this.editor?.chain().focus().addColumnAfter().run();
  }

  addRowAfter(): void {
    this.editor?.chain().focus().addRowAfter().run();
  }

  deleteColumn(): void {
    this.editor?.chain().focus().deleteColumn().run();
  }

  deleteRow(): void {
    this.editor?.chain().focus().deleteRow().run();
  }

  deleteTable(): void {
    this.editor?.chain().focus().deleteTable().run();
  }

  headingLabel(level: number): string {
    return level === 0 ? 'Normal text' : `Heading ${level}`;
  }

  alignIcon(align: 'left' | 'center' | 'right' | 'justify'): string {
    switch (align) {
      case 'center':
        return 'format_align_center';
      case 'right':
        return 'format_align_right';
      case 'justify':
        return 'format_align_justify';
      default:
        return 'format_align_left';
    }
  }

  fontFamilyLabel(value: string): string {
    const match = this.fontFamilyOptions.find((option) => option.value === value);
    return match && match.value ? match.label : 'Font';
  }

  fontSizeLabel(value: string): string {
    return value ? value.replace('px', '') : '16';
  }

  toggleBulletList(): void {
    this.editor?.chain().focus().toggleBulletList().run();
  }

  toggleOrderedList(): void {
    this.editor?.chain().focus().toggleOrderedList().run();
  }

  toggleBlockquote(): void {
    this.editor?.chain().focus().toggleBlockquote().run();
  }

  undo(): void {
    this.editor?.chain().focus().undo().run();
  }

  redo(): void {
    this.editor?.chain().focus().redo().run();
  }

  setLink(): void {
    const url = window.prompt('Enter a URL');
    if (!url) {
      this.editor?.chain().focus().unsetLink().run();
      return;
    }
    this.editor?.chain().focus().setLink({ href: url }).run();
  }

  insertTable(): void {
    this.editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
  }

  goBack(): void {
    void this.router.navigate(['/dashboard']);
  }

  // Side panel (versions / AI / stats)
  openSidePanel(tab: 'versions' | 'ai' | 'suggestions' | 'stats'): void {
    this.sidePanelTab.set(tab);
    this.sidePanelOpen.set(true);
    if (tab === 'stats') this.loadDocumentStats();
    if (tab === 'suggestions') this.loadSuggestions();
    if (tab === 'versions') this.loadVersions();
  }

  closeSidePanel(): void {
    this.sidePanelOpen.set(false);
  }

  toggleSidePanel(tab: 'versions' | 'ai' | 'suggestions' | 'stats'): void {
    this.sidePanelTab.update((current) => {
      if (current === tab && this.sidePanelOpen()) {
        this.sidePanelOpen.set(false);
        return current;
      }
      this.sidePanelOpen.set(true);
      if (tab === 'stats') {
        this.loadDocumentStats();
      } else if (tab === 'suggestions') {
        this.loadSuggestions();
      }
      return tab;
    });
  }

  loadVersions(): void {
    const doc = this.document();
    if (!doc) return;
    this.versionsLoading.set(true);
    this.versionService.list(doc.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (versions) => {
        this.versions.set(versions);
        this.versionsLoading.set(false);
      },
      error: () => {
        this.versionsLoading.set(false);
        this.versionError.set('Could not load version history. Please retry.');
        this.notifications.error('Could not load version history.');
      },
    });
  }

  loadSuggestions(): void {
    const doc = this.document();
    if (!doc) return;
    this.suggestionsLoading.set(true);
    this.suggestionsError.set(null);
    this.suggestionService.list(doc.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (suggestions) => {
        this.suggestions.set(suggestions);
        this.suggestionsLoading.set(false);
      },
      error: () => {
        this.suggestionsLoading.set(false);
        this.suggestionsError.set('Could not load suggestions. Please retry.');
      },
    });
  }

  analyzeDocument(): void {
    const doc = this.document();
    if (!doc || this.analyzing() || this.editingLocked() || this.autosave.hasUnsavedChanges()) return;
    this.analyzing.set(true);
    this.suggestionsError.set(null);
    // Analyze only the selected text when a selection exists — this keeps the
    // request under the 10,000-character analysis limit on long documents.
    // Plain textBetween (not Markdown) is sent so quoted passages still match
    // the stored document content when a suggestion is applied.
    const selection = this.editor ? this.editor.state.selection : null;
    const selectedText = selection && selection.from !== selection.to
      ? this.editor!.state.doc.textBetween(selection.from, selection.to, '\n').trim()
      : undefined;
    this.analysisSubscription = this.suggestionService.analyze(doc.id, doc.revision, selectedText).pipe(
      finalize(() => this.analyzing.set(false)), takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: suggestions => {
        if (this.document()?.id !== doc.id) return;
        this.suggestions.set(suggestions);
        this.analysisPerformed.set(true);
      },
      error: (err) => {
        const detail = typeof err?.error?.detail === 'string' ? err.error.detail : '';
        this.suggestionsError.set(detail || (selectedText
          ? 'We could not analyze the selected text. Save your edits and try again (up to 10,000 characters).'
          : 'We could not analyze this document. Save your edits and try again (up to 10,000 characters).'));
      },
    });
  }

  acceptSuggestion(suggestion: import('../../core/models/suggestion.model').Suggestion): void {
    const doc = this.document();
    if (!doc || !this.editor || this.editingLocked() || this.autosave.hasUnsavedChanges()) {
      this.notifications.info('Save your edits before accepting suggestions.');
      return;
    }
    this.applyingSuggestion.set(true);
    this.editor.setEditable(false, false);
    this.titleControl.disable({ emitEvent: false });
    this.suggestionService.apply(doc.id, suggestion.id, doc.revision).pipe(
      finalize(() => {
        this.applyingSuggestion.set(false);
        this.editor?.setEditable(true, false);
        this.titleControl.enable({ emitEvent: false });
      }), takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: result => {
        this.suggestionsError.set(null);
        this.autosave.initialize(result.document);
        this.applyDocumentContent(result.document.content);
        this.suggestions.update(list => list.map(s => s.id === result.suggestion.id ? result.suggestion : s));
        this.loadVersions();
        this.metrics.recordSuggestionAccepted();
        this.notifications.success('Suggestion applied and saved.');
      },
      error: (err) => {
        const stale = err?.status === 409 || err?.status === 404;
        const message = stale
          ? 'This suggestion no longer matches the document text. Run "Analyze document" again to refresh suggestions.'
          : 'Could not apply this suggestion. Your local text is unchanged. Reload if the request was interrupted, or analyze again if the passage changed.';
        this.suggestionsError.set(message);
        this.notifications.error(message);
      },
    });
  }

  rejectSuggestion(suggestion: import('../../core/models/suggestion.model').Suggestion): void {
    const doc = this.document();
    if (!doc) return;
    this.suggestionService.update(doc.id, suggestion.id, { status: 'rejected' })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (updated) => {
          this.suggestions.update((list) => list.map((s) => s.id === updated.id ? updated : s));
          this.metrics.recordSuggestionRejected();
          this.notifications.info('Suggestion rejected.');
        },
        error: () => {
          this.suggestionsError.set('Could not reject this suggestion. Please retry.');
        },
      });
  }

  deleteSuggestion(suggestion: import('../../core/models/suggestion.model').Suggestion): void {
    const doc = this.document();
    if (!doc) return;
    this.suggestionService.delete(doc.id, suggestion.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.suggestions.update((list) => list.filter((s) => s.id !== suggestion.id));
        this.notifications.success('Suggestion deleted.');
      },
      error: () => {
        this.notifications.error('Could not delete suggestion.');
      },
    });
  }

  openShareDialog(): void {
    const doc = this.document();
    if (!doc) return;
    this.shareError.set(null);
    this.shareLoading.set(true);
    this.sharingService.list(doc.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (collabs) => {
        this.collaborators.set(collabs);
        this.shareLoading.set(false);
      },
      error: () => {
        this.shareLoading.set(false);
        this.shareError.set('Could not load collaborators.');
      },
    });
    const dialogRef = this.dialog.open(ShareDialog, {
      width: '420px',
      data: {
        collaborators: this.collaborators,
        loading: this.shareLoading,
        inviting: this.shareInviting,
        error: this.shareError,
      },
    });
    dialogRef.componentInstance.invite.subscribe((body: { email: string; role: 'editor' | 'viewer' }) => {
      this.inviteCollaborator(body);
    });
    dialogRef.componentInstance.remove.subscribe((collab: import('../../core/models/collaborator.model').Collaborator) => {
      this.removeCollaborator(collab);
    });
  }

  private inviteCollaborator(body: { email: string; role: 'editor' | 'viewer' }): void {
    const doc = this.document();
    if (!doc) return;
    this.shareInviting.set(true);
    this.shareError.set(null);
    this.sharingService.invite(doc.id, body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (collab) => {
        this.collaborators.update((list) => {
          const existing = list.findIndex((c) => c.user_id === collab.user_id);
          if (existing >= 0) {
            const updated = [...list];
            updated[existing] = collab;
            return updated;
          }
          return [...list, collab];
        });
        this.shareInviting.set(false);
        this.metrics.recordShareInvited();
        this.notifications.success(`${collab.email || 'Collaborator'} added as ${collab.role}.`);
      },
      error: (err) => {
        this.shareInviting.set(false);
        const detail = err?.error?.detail || 'Could not invite collaborator.';
        this.shareError.set(detail);
      },
    });
  }

  private removeCollaborator(collab: import('../../core/models/collaborator.model').Collaborator): void {
    const doc = this.document();
    if (!doc) return;
    this.sharingService.remove(doc.id, collab.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.collaborators.update((list) => list.filter((c) => c.id !== collab.id));
        this.notifications.success('Access removed.');
      },
      error: () => {
        this.shareError.set('Could not remove collaborator.');
      },
    });
  }

  openSaveVersionDialog(): void {
    const doc = this.document();
    if (!doc) return;

    const dialogRef = this.dialog.open(SaveVersionDialog, { width: '380px' });
    dialogRef.afterClosed().subscribe((label) => {
      if (label === undefined) return;
      if (this.autosave.hasUnsavedChanges() || this.restoringVersion()) {
        this.notifications.info('Wait for your latest edits to save before creating a version.');
        return;
      }
      this.savingVersion.set(true);
      this.versionService.create(doc.id, label).subscribe({
        next: () => {
          this.savingVersion.set(false);
          this.loadVersions();
          this.metrics.recordVersionSaved();
          this.notifications.success('Version saved.');
        },
        error: () => {
          this.savingVersion.set(false);
          this.notifications.error('Could not save version.');
        },
      });
    });
  }

  deleteVersion(version: VersionSummary): void {
    const doc = this.document();
    if (!doc || this.restoringVersion()) return;
    this.dialog.open(ConfirmDialog, {
      data: {
        title: 'Delete this snapshot?',
        message: `This permanently removes "${version.label || version.title}" from history. The current document will not change.`,
        confirmText: 'Delete snapshot', cancelText: 'Keep snapshot',
      }, width: '420px',
    }).afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe((confirmed) => {
      if (!confirmed || this.restoringVersion()) return;
      this.versionService.delete(doc.id, version.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: () => {
          this.versions.update((versions) => versions.filter((v) => v.id !== version.id));
          this.notifications.success('Version deleted.');
        },
        error: () => this.notifications.error('Could not delete version.'),
      });
    });
  }

  restoreVersion(version: VersionSummary): void {
    const doc = this.document();
    if (!doc || this.autosave.hasUnsavedChanges() || this.editingLocked()) return;
    this.dialog.open(ConfirmDialog, {
      data: {
        title: 'Restore this version?',
        message: `Restore "${version.label || version.title}"? Your current saved document will be preserved as a snapshot, and the restoration will be recorded in history.`,
        confirmText: 'Restore version', cancelText: 'Keep current document',
      }, width: '460px',
    }).afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe((confirmed) => {
      const current = this.document();
      if (!confirmed || !current || current.id !== doc.id || this.autosave.hasUnsavedChanges() || this.restoringVersion()) return;
      this.restoringVersion.set(true);
      this.versionError.set(null);
      this.setAiMode(this.aiMode());
      this.editor?.setEditable(false, false);
      this.titleControl.disable({ emitEvent: false });
      this.versionService.restore(current.id, version.id, current.revision).pipe(
        finalize(() => {
          this.restoringVersion.set(false);
          this.editor?.setEditable(true, false);
          this.titleControl.enable({ emitEvent: false });
        }),
        takeUntilDestroyed(this.destroyRef),
      ).subscribe({
        next: (restored) => {
          this.autosave.initialize(restored);
          this.titleControl.setValue(restored.title, { emitEvent: false });
          this.applyDocumentContent(restored.content);
          this.loadVersions();
          this.metrics.recordVersionRestored();
          this.notifications.success('Version restored. Your previous document is preserved in history.');
        },
        error: (error) => {
          this.versionError.set(error.status === 409
            ? 'The document changed elsewhere. Reload the latest document before restoring.'
            : 'Restore could not be confirmed. Your local document is unchanged. Reload to check the saved state before retrying.');
        },
      });
    });
  }

  showDiff(version: VersionSummary, compareTo: string | null = null): void {
    const doc = this.document();
    if (!doc) return;

    this.versionService.diff(doc.id, version.id, compareTo).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (diff) => {
        this.dialog.open(DiffViewer, { data: diff, width: '720px', maxWidth: '95vw' });
      },
      error: () => {
        this.notifications.error('Could not compute diff.');
      },
    });
  }

  // Stats & export
  loadDocumentStats(): void {
    const doc = this.document();
    if (!doc) return;
    this.statsLoading.set(true);
    this.analyticsService.getDocumentStats(doc.id).subscribe({
      next: (stats) => {
        this.documentStats.set(stats);
        this.analyticsService.evaluateDocument(doc.id).subscribe({
          next: (result) => {
            this.readability.set(result);
            this.statsLoading.set(false);
          },
          error: () => {
            this.statsLoading.set(false);
          },
        });
      },
      error: () => {
        this.statsLoading.set(false);
        this.notifications.error('Could not load document stats.');
      },
    });
  }

  exportDocument(format: ExportFormat): void {
    const doc = this.document();
    if (!doc) return;
    this.analyticsService.exportDocument(doc.id, format).subscribe({
      next: (blob) => {
        const extensions: Record<ExportFormat, string> = {
          markdown: 'md', html: 'html', text: 'txt', docx: 'docx', pdf: 'pdf',
        };
        const extension = extensions[format];
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${(doc.title || 'document').replace(/\s+/g, '_')}.${extension}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        this.metrics.recordExport();
        this.notifications.success(`Exported as ${format}.`);
      },
      error: () => {
        this.notifications.error('Could not export document.');
      },
    });
  }

  // AI assistant
  setAiMode(mode: AiMode): void {
    this.aiStreamSub?.unsubscribe();
    this.aiStreamSub = null;
    this.aiLoading.set(false);
    this.aiMode.set(mode);
    this.aiOutput.set('');
    this.aiError.set(null);
    this.aiTarget = null;
  }

  private selectedOrFullText(): string {
    if (!this.editor) return '';
    const { from, to } = this.editor.state.selection;
    const content = from !== to
      ? this.editor.state.doc.slice(from, to).content.toJSON()
      : this.editor.getJSON().content;
    return docToMarkdown(content ?? []).trim();
  }

  /** Returns the text immediately before and after the current selection, trimmed. */
  private surroundingContext(): { before: string; after: string } {
    if (!this.editor) return { before: '', after: '' };
    const { from, to } = this.editor.state.selection;
    const doc = this.editor.state.doc;
    const before = from > 0 ? doc.textBetween(Math.max(0, from - 600), from, ' ') : '';
    const after = to < doc.content.size ? doc.textBetween(to, Math.min(doc.content.size, to + 600), ' ') : '';
    return { before: before.trim(), after: after.trim() };
  }

  readonly composerPlaceholder = computed(() => {
    const mode = this.aiMode();
    if (mode === 'generate') return 'Describe what to write, then press Enter…';
    if (mode === 'outline') return 'Optional topic — press Enter to outline this document…';
    return 'Ask AI to change this, or choose an action above…';
  });

  onComposerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.runCustom();
    }
  }

  private focusComposer(): void {
    setTimeout(() => this.composerInputRef()?.nativeElement.focus());
  }

  runQuickAction(mode: AiMode): void {
    if (this.aiLoading() || this.editingLocked()) return;
    this.setAiMode(mode);
    this.openSidePanel('ai');
    const typed = this.aiInstruction.value.trim();
    if ((mode === 'generate' || mode === 'outline') && typed) {
      this.aiPrompt.setValue(typed);
    }
    if (mode === 'generate' && !this.aiPrompt.value.trim()) {
      this.focusComposer();
      this.notifications.info('Describe what you want to write, then press Enter.');
      return;
    }
    this.runAi();
  }

  runTone(tone: string): void {
    this.aiTone.setValue(tone);
    this.runQuickAction('tone');
  }

  runSimplify(): void {
    this.aiInstruction.setValue('Simplify the wording while preserving meaning');
    this.runQuickAction('custom');
  }

  runCustom(): void {
    const typed = this.aiInstruction.value.trim();
    if (!typed) return;
    const mode = this.aiMode();
    if (mode === 'generate' || mode === 'outline') {
      this.aiPrompt.setValue(typed);
      this.runQuickAction(mode);
    } else if (!this.editor?.getText().trim()) {
      this.aiPrompt.setValue(typed);
      this.runQuickAction('generate');
    } else {
      this.runQuickAction('custom');
    }
  }

  runAi(): void {
    if (this.aiLoading() || this.editingLocked() || !this.editor) return;
    const mode = this.aiMode();
    let text = this.selectedOrFullText();
    if (mode === 'generate' ? !this.aiPrompt.value.trim() : !text && !this.aiPrompt.value.trim()) {
      this.notifications.info('Write some text or enter a topic first.');
      return;
    }
    // Server bound for text-bearing actions — whole-doc text can exceed it on
    // long documents, so ask for a smaller selection instead of hitting a 422.
    if (text.length > 30000) {
      const sel = this.editor.state.selection;
      text = sel.from !== sel.to
        ? docToMarkdown(this.editor.state.doc.slice(sel.from, sel.to).content.toJSON() ?? []).trim()
        : '';
      if (!text || text.length > 30000) {
        this.notifications.info('This document is too long for one action — select a section first.');
        return;
      }
    }
    this.metrics.recordAiAction(mode);
    const { from, to } = this.editor.state.selection;
    this.aiTarget = { from, to, document: this.editor.state.doc };
    this.aiSelectionActive.set(from !== to);
    this.aiError.set(null);
    this.aiLoading.set(true);
    this.aiOutput.set('');
    this.titleOptions.set([]);
    const { before, after } = this.surroundingContext();
    this.aiStreamSub = this.aiService.action({
      action: mode, text, document_title: this.titleControl.value, before, after,
      instruction: this.aiInstruction.value.trim(),
      tone: mode === 'tone' ? this.aiTone.value : undefined,
      max_words: mode === 'summarize' ? this.aiMaxWords.value : undefined,
      prompt: mode === 'generate' || mode === 'outline' ? this.aiPrompt.value.trim() : undefined,
    }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: res => this.handleAiOutput(res.output, true),
      error: () => this.handleAiError(),
    });
  }

  suggestTitle(): void {
    if (!this.editor || this.titlesLoading() || this.editingLocked()) return;
    const text = this.editor.getText().trim();
    if (!text) {
      this.notifications.info('Write a passage first so AI can suggest a relevant title.');
      return;
    }
    this.openSidePanel('ai');
    this.titleOptions.set([]);
    this.aiError.set(null);
    this.titlesLoading.set(true);
    this.titleTarget = { document: this.editor.state.doc, title: this.titleControl.value };
    this.titleSubscription = this.aiService.suggestTitles(text).pipe(
      finalize(() => this.titlesLoading.set(false)), takeUntilDestroyed(this.destroyRef),
    ).subscribe({
      next: result => this.titleOptions.set(result.titles),
      error: () => this.aiError.set('We could not suggest titles. Please try again.'),
    });
  }

  chooseTitle(title: string): void {
    if (!this.editor || !this.titleTarget || this.editingLocked() || !this.titleOptions().includes(title)) return;
    if (!this.editor.state.doc.eq(this.titleTarget.document) || this.titleControl.value !== this.titleTarget.title) {
      this.aiError.set('The document or title changed. Suggest titles again.');
      return;
    }
    this.titleControl.setValue(title);
    this.titleOptions.set([]);
  }

  async copyAiOutput(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.aiOutput());
      this.notifications.success('Copied to clipboard.');
    } catch {
      this.notifications.info('Clipboard unavailable. Select the preview text to copy it.');
    }
  }

  readonly replaceLabel = computed(() => this.aiSelectionActive() ? 'Replace selection' : 'Replace document');

  private defaultInstructionForMode(mode: AiMode): string {
    switch (mode) {
      case 'improve':
        return 'Improve the writing while preserving the meaning.';
      case 'expand':
        return 'Expand this into a more detailed and thorough version.';
      case 'condense':
        return 'Make this shorter and more concise.';
      default:
        return '';
    }
  }

  stopAi(): void {
    this.aiStreamSub?.unsubscribe();
    this.aiStreamSub = null;
    this.aiLoading.set(false);
    this.aiOutput.set('');
    this.aiTarget = null;
    this.notifications.info('Generation stopped. Your document has not changed.');
  }

  private handleAiOutput(output: string, canApply: boolean): void {
    this.aiLoading.set(false);
    output = output.trim().replace(/^```(?:text|markdown)?\s*\n([\s\S]*?)\n```$/, '$1');
    if (!output || /^\s*(?:document title|text before selection|text after selection|selected text|context|previous text|following text|text)\s*:/im.test(output)) {
      this.handleAiError();
      return;
    }
    this.aiOutput.set(output);
    if (canApply && this.aiMode() !== 'summarize') {
      this.notifications.success('AI suggestion ready.');
    } else if (this.aiMode() === 'summarize') {
      this.notifications.success('Summary generated.');
    }
  }

  private handleAiError(): void {
    this.aiLoading.set(false);
    this.aiOutput.set('');
    this.aiError.set('We could not generate a usable suggestion. Your document has not changed. Please try again.');
    this.notifications.error('AI request failed. Please retry.');
  }

  applyAiOutput(): void {
    this.commitAiOutput(true);
  }

  insertAiOutput(): void {
    this.commitAiOutput(false);
  }

  acceptAiOutput(): void {
    this.commitAiOutput(false);
  }

  insertAtCursor(): void {
    this.commitAiOutput(false, true);
  }

  private commitAiOutput(replace: boolean, atCursor = false): void {
    const target = this.aiTarget;
    const output = this.aiOutput().trim();
    if (!this.editor || !target || !output || this.aiLoading() || this.aiError() || this.editingLocked()) return;
    if (!this.editor.state.doc.eq(target.document)) {
      this.aiError.set('The document changed while AI was working. Regenerate the suggestion for the current text.');
      return;
    }
    const headings = ['heading', 'headings'].includes(this.aiMode());
    let content: unknown[];
    if (headings) {
      content = output.split(/\r?\n/).filter(text => text.trim()).map(line => {
        const text = line.replace(/^\s*(?:#{1,6}\s+|[-*]\s+|\d+[.)]\s+)/, '');
        return { type: 'heading', attrs: { level: 2 }, content: text ? [{ type: 'text', text }] : [] };
      });
    } else {
      const nodes = aiOutputToNodes(output);
      const singleParagraph = nodes.length === 1 && nodes[0].type === 'paragraph';
      content = singleParagraph && (atCursor || (replace && target.from !== target.to))
        ? (nodes[0].content ?? [])
        : nodes;
    }
    const resolved = target.document.resolve(target.to);
    const below = resolved.depth > 0 ? resolved.after(1) : target.document.content.size;
    const range = replace
      ? target.from === target.to ? { from: 0, to: target.document.content.size } : { from: target.from, to: target.to }
      : atCursor ? target.to : below;
    this.editor.chain().focus().insertContentAt(range, content).run();
    this.aiOutput.set('');
    this.aiTarget = null;
    this.notifications.success('Writing inserted.');
  }

  rejectAiOutput(): void {
    this.aiOutput.set('');
    this.aiTarget = null;
    this.aiError.set(null);
    this.notifications.info('AI output discarded.');
  }

  async logout(): Promise<void> {
    // Handled by dashboard normally; this is a fallback.
    void this.router.navigate(['/dashboard']);
  }

  toggleMetrics(): void {
    this.metrics.toggle();
    if (this.metrics.enabled()) {
      this.notifications.info('Metrics collection enabled. Your editing activity will be counted for evaluation.');
    } else {
      this.notifications.info('Metrics collection disabled.');
    }
  }

  exportMetrics(): void {
    this.metrics.downloadJson();
    this.notifications.success('Metrics exported as JSON.');
  }
}
