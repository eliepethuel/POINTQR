import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { ServerStatus } from '../../core/system/server-status';
import {
  CountUp,
  loadScrollTrigger,
  Magnetic,
  MotionService,
  RevealOnScroll,
  Spotlight,
  Tilt3d,
} from '../../shared/motion';
import { QrCanvas } from '../../kiosk/qr-canvas';

interface Fraud {
  readonly fraud: string;
  readonly parade: string;
}

/**
 * Public landing page (content of the presentation): problem, solution, 4-step journey,
 * anti-fraud, modes A–D, ARTCI "zero biometrics", figures, architecture, demo CTA.
 */
@Component({
  selector: 'pq-landing-page',
  imports: [RouterLink, CountUp, Magnetic, RevealOnScroll, Spotlight, Tilt3d, QrCanvas],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './landing-page.html',
  styleUrl: './landing-page.css',
})
export class LandingPage {
  protected readonly server = inject(ServerStatus);
  private readonly motion = inject(MotionService);
  private readonly timeline = viewChild<ElementRef<HTMLElement>>('timeline');
  private readonly architecture = viewChild<ElementRef<HTMLElement>>('architecture');

  protected readonly titleWords = ['Le', 'pointage', 'qui', 'ne', 'ment', 'pas.'];
  /** The hero QR recomposes itself every few seconds (pixel morphing). */
  protected readonly heroQr = signal('PQR1.pointqr.demo.0');
  protected readonly flipped = signal<ReadonlySet<number>>(new Set());
  protected readonly clock = computed(() => {
    const t = this.server.serverTime();
    return t
      ? new Intl.DateTimeFormat('fr-FR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZone: 'Africa/Abidjan',
        }).format(t)
      : '--:--:--';
  });

  protected readonly steps = [
    {
      n: '01',
      title: 'La borne affiche un QR',
      text: 'Renouvelé toutes les 30 secondes, signé par une clé propre à la borne.',
    },
    {
      n: '02',
      title: "L'agent le scanne",
      text: "Avec l'application, en deux gestes. Sa position n'est lue qu'à cet instant.",
    },
    {
      n: '03',
      title: 'Le serveur contrôle',
      text: 'QR valide, non rejoué, téléphone lié, position dans la zone, pas de doublon.',
    },
    {
      n: '04',
      title: "L'heure du serveur fait foi",
      text: 'Statut immédiat : « À l’heure » ou « Retard de 22 min ». Jamais d’heure saisie.',
    },
  ];

  protected readonly frauds: readonly Fraud[] = [
    {
      fraud: 'Photo du QR envoyée à un collègue',
      parade: 'QR expiré après 30 s + position hors zone',
    },
    {
      fraud: "Pointer avec le téléphone d'un autre",
      parade: 'Un téléphone = un agent ; changement validé par le RH',
    },
    { fraud: "Avancer l'heure du téléphone", parade: "Seule l'heure du serveur compte" },
    {
      fraud: 'Appli « fake GPS »',
      parade: 'Détection de position simulée + Wi-Fi de l’entreprise',
    },
    { fraud: 'Rejouer une requête', parade: 'Jeton signé à usage unique, HTTPS' },
    { fraud: 'Borne volée ou déplacée', parade: 'Révocable à distance, nouvelle clé en un clic' },
  ];

  protected readonly modes = [
    {
      letter: 'A',
      title: 'Borne + téléphone',
      text: "La borne affiche le QR, l'agent le scanne. Le mode principal.",
      trust: 'Confiance élevée',
    },
    {
      letter: 'B',
      title: 'QR personnel',
      text: "L'app affiche le QR de l'agent, la borne le scanne. Utile hors-ligne.",
      trust: 'Confiance élevée',
    },
    {
      letter: 'C',
      title: 'Badge imprimé',
      text: 'Carte QR pour les agents sans smartphone, scannée par la borne.',
      trust: 'Confiance moyenne',
    },
    {
      letter: 'D',
      title: 'QR affiché seul',
      text: 'Petites structures sans borne : position et téléphone lié font le contrôle.',
      trust: 'Confiance moyenne',
    },
  ];

  constructor() {
    const destroyRef = inject(DestroyRef);
    let n = 0;
    const timer = setInterval(() => this.heroQr.set(`PQR1.pointqr.demo.${++n}`), 3500);
    destroyRef.onDestroy(() => clearInterval(timer));
    afterNextRender(() => void this.scrollScenes(destroyRef));
  }

  protected flip(i: number): void {
    this.flipped.update((set) => {
      const next = new Set(set);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  /** Scroll-driven scenes (GSAP ScrollTrigger, loaded lazily, killed on destroy). */
  private async scrollScenes(destroyRef: DestroyRef): Promise<void> {
    if (this.motion.reduced()) return;
    const { gsap } = await loadScrollTrigger();
    const ctx = gsap.context(() => {
      const timeline = this.timeline()?.nativeElement;
      if (timeline) {
        gsap
          .timeline({
            scrollTrigger: { trigger: timeline, start: 'top 70%', end: 'bottom 60%', scrub: 0.6 },
          })
          .fromTo(timeline.querySelector('.track-fill'), { scaleX: 0 }, { scaleX: 1, ease: 'none' })
          .fromTo(
            timeline.querySelectorAll('.tick'),
            { y: 12, opacity: 0 },
            { y: 0, opacity: 1, stagger: 0.15 },
            0,
          )
          .fromTo(
            timeline.querySelector('.verdict'),
            { scale: 0.6, opacity: 0 },
            { scale: 1, opacity: 1, ease: 'back.out(2)' },
            '>-0.1',
          );
      }
      const architecture = this.architecture()?.nativeElement;
      if (architecture) {
        gsap.fromTo(
          architecture.querySelectorAll('.wire'),
          { strokeDashoffset: 300 },
          {
            strokeDashoffset: 0,
            duration: 1.4,
            ease: 'power2.out',
            stagger: 0.12,
            scrollTrigger: { trigger: architecture, start: 'top 75%' },
          },
        );
      }
    });
    destroyRef.onDestroy(() => ctx.revert());
  }
}
