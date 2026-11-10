import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { of } from 'rxjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from './app-shell';
import { AuthService } from '../core/services/auth.service';
import { UserService } from '../core/services/user.service';
import { NotificationService } from '../core/services/notification.service';
import { DocumentService } from '../core/services/document.service';

@Component({ template: '' })
class StubComponent {}

const mockUser = { uid: 'u1', name: 'Alice', email: 'a@e.com' };

const mockDocs = [
  { id: 'd1', title: 'Doc One', word_count: 120, owner_id: 'u1' },
];

describe('AppShell', () => {
  let component: AppShell;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [AppShell],
      providers: [
        provideRouter([
          { path: 'dashboard', component: StubComponent },
          { path: 'documents/:id', component: StubComponent },
        ]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { currentUser: vi.fn(() => ({ email: 'a@e.com' })), logout: vi.fn().mockResolvedValue(undefined) } },
        { provide: UserService, useValue: { getMe: vi.fn().mockReturnValue({ subscribe: (obs: any) => { obs.next?.(mockUser); return { unsubscribe: () => {} }; } }) } },
        { provide: NotificationService, useValue: { success: vi.fn(), error: vi.fn(), info: vi.fn() } },
        { provide: DocumentService, useValue: { list: vi.fn().mockReturnValue(of(mockDocs)), create: vi.fn() } },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(AppShell);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('loads user', () => {
    expect(component.user()?.name).toBe('Alice');
  });

  it('computes initials from user name', () => {
    expect(component.initials()).toBe('A');
  });

  it('toggles collapsed state', () => {
    expect(component.collapsed()).toBe(false);
    component.toggleCollapsed();
    expect(component.collapsed()).toBe(true);
    component.toggleCollapsed();
    expect(component.collapsed()).toBe(false);
  });

  it('persists collapsed state to localStorage', () => {
    component.toggleCollapsed();
    expect(localStorage.getItem('docintel.sidebarCollapsed')).toBe('true');
  });

  it('restores collapsed state from localStorage on init', () => {
    localStorage.setItem('docintel.sidebarCollapsed', 'true');
    component.ngOnInit();
    expect(component.collapsed()).toBe(true);
  });

  it('toggles metrics collection', () => {
    expect(component.metricsEnabled()).toBe(false);
    component.toggleMetrics();
    expect(component.metricsEnabled()).toBe(true);
    component.toggleMetrics();
    expect(component.metricsEnabled()).toBe(false);
  });

  it('exports metrics without error', () => {
    component.toggleMetrics();
    // downloadJson creates a blob and link; just verify it doesn't throw
    expect(() => component.exportMetrics()).not.toThrow();
    component.toggleMetrics(); // disable
  });

  it('expands documents section and loads sidebar docs', () => {
    expect(component.docsExpanded()).toBe(false);
    component.toggleDocuments();
    expect(component.docsExpanded()).toBe(true);
    expect(component.sidebarDocs().length).toBe(1);
    expect(component.sidebarDocs()[0].title).toBe('Doc One');
    component.toggleDocuments();
    expect(component.docsExpanded()).toBe(false);
  });

  it('toggles mobile sidebar open state', () => {
    expect(component.mobileOpen()).toBe(false);
    component.toggleMobile();
    expect(component.mobileOpen()).toBe(true);
    component.closeMobile();
    expect(component.mobileOpen()).toBe(false);
  });
});
