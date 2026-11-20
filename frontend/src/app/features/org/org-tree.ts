import { ChangeDetectionStrategy, Component, input, signal } from '@angular/core';

import type { OrgTreeNode } from '../../api/models/org-tree-node';

/** Recursive, collapsible organisation tree; branches unfold with a staggered cascade. */
@Component({
  selector: 'pq-org-tree',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ul class="tree" [class.root]="depth() === 0">
      @for (node of nodes(); track node.id; let i = $index) {
        <li [style.animation-delay.ms]="i * 70">
          <div class="node" [attr.data-kind]="node.kind">
            @if (hasChildren(node)) {
              <button
                type="button"
                class="toggle"
                (click)="toggle(node.id)"
                [attr.aria-expanded]="!isClosed(node.id)"
                [attr.aria-label]="isClosed(node.id) ? 'Déplier' : 'Replier'"
              >
                <span [class.closed]="isClosed(node.id)">▾</span>
              </button>
            } @else {
              <span class="toggle-space"></span>
            }
            <span class="kind">{{ kindLabel[node.kind] ?? node.kind }}</span>
            <strong>{{ node.name }}</strong>
            <span class="pq-badge">{{ node.agent_count }} agents</span>
            @if (node.manager_name) {
              <span class="manager">Responsable : {{ node.manager_name }}</span>
            }
          </div>
          @if (hasChildren(node) && !isClosed(node.id)) {
            <pq-org-tree [nodes]="children(node)" [depth]="depth() + 1" />
          }
        </li>
      }
    </ul>
  `,
  styles: `
    .tree {
      list-style: none;
      margin: 0;
      padding-left: 22px;
      border-left: 1px dashed var(--pq-border);
    }
    .tree.root {
      padding-left: 0;
      border-left: 0;
    }
    li {
      animation: branch 520ms var(--pq-ease-out-expo) both;
    }
    .node {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin: 6px 0;
      padding: 10px 12px;
      border-radius: 12px;
      background: var(--pq-surface-2);
    }
    .node[data-kind='direction'] {
      border-left: 3px solid var(--pq-accent);
    }
    .node[data-kind='team'] {
      border-left: 3px solid var(--pq-success);
    }
    .kind {
      font: 500 0.6875rem var(--pq-font-mono);
      text-transform: uppercase;
      color: var(--pq-text-muted);
    }
    .manager {
      font-size: 0.8125rem;
      color: var(--pq-text-muted);
    }
    .toggle {
      width: 24px;
      height: 24px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--pq-text);
      cursor: pointer;
    }
    .toggle span {
      display: inline-block;
      transition: transform var(--pq-dur-base) var(--pq-ease-out-back);
    }
    .toggle span.closed {
      transform: rotate(-90deg);
    }
    .toggle-space {
      width: 24px;
    }
    @keyframes branch {
      from {
        opacity: 0;
        transform: translateX(-10px);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      li {
        animation: none;
      }
    }
  `,
})
export class OrgTree {
  readonly nodes = input.required<readonly OrgTreeNode[]>();
  readonly depth = input(0);
  private readonly closed = signal<ReadonlySet<string>>(new Set());
  protected readonly kindLabel: Record<string, string> = {
    direction: 'Direction',
    service: 'Service',
    team: 'Équipe',
  };

  protected hasChildren(node: OrgTreeNode): boolean {
    return (node.children?.length ?? 0) > 0;
  }

  protected children(node: OrgTreeNode): OrgTreeNode[] {
    return (node.children ?? []) as unknown as OrgTreeNode[];
  }

  protected isClosed(id: string): boolean {
    return this.closed().has(id);
  }

  protected toggle(id: string): void {
    this.closed.update((set) => {
      const next = new Set(set);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
}
