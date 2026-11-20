import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { ServerStatus } from '../../core/system/server-status';
import {
  CountUp,
  Magnetic,
  RevealOnScroll,
  Shimmer,
  SplitTextDirective,
  Spotlight,
} from '../../shared/motion';

interface KeyFigure {
  readonly value: number;
  readonly prefix: string;
  readonly suffix: string;
  readonly label: string;
}

/** Phase 0 landing: proves the design tokens, the motion system and the generated API client. */
@Component({
  selector: 'pq-hello-page',
  imports: [DatePipe, CountUp, Magnetic, RevealOnScroll, Shimmer, SplitTextDirective, Spotlight],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './hello-page.html',
  styleUrl: './hello-page.css',
})
export class HelloPage {
  protected readonly server = inject(ServerStatus);

  protected readonly figures: readonly KeyFigure[] = [
    {
      value: 5,
      prefix: '< ',
      suffix: ' s',
      label: 'pour pointer, de l’ouverture de l’app à la confirmation',
    },
    { value: 30, prefix: '', suffix: ' s', label: 'durée de vie maximale d’un QR code' },
    { value: 100, prefix: '', suffix: ' %', label: 'des heures fixées par le serveur' },
  ];

  protected readonly statusLabel = computed(() => {
    switch (this.server.state()) {
      case 'online':
        return 'Serveur en ligne';
      case 'degraded':
        return 'Service dégradé';
      case 'offline':
        return 'Serveur injoignable';
      default:
        return 'Connexion…';
    }
  });
}
