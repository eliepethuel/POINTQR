import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  effect,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import type * as Leaflet from 'leaflet';

export interface MapSite {
  readonly id: string;
  readonly name: string;
  readonly latitude: number;
  readonly longitude: number;
  readonly radius_m: number;
}

/**
 * OpenStreetMap view of the sites with their geofence. Leaflet is loaded lazily.
 * Changing the radius of the selected site sends a ripple across the circle.
 */
@Component({
  selector: 'pq-site-map',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="map" role="application" aria-label="Carte des sites"></div>`,
  styles: `
    .map {
      width: 100%;
      height: 100%;
      min-height: 360px;
      border-radius: var(--pq-radius-lg);
      overflow: hidden;
      background: var(--pq-surface-2);
    }
    :host ::ng-deep .pq-pin {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--pq-accent);
      border: 3px solid #fff;
      box-shadow: 0 0 0 0 rgb(124 92 255 / 0.6);
      animation: pin-pulse 2s ease-out infinite;
    }
    :host ::ng-deep .pq-ripple {
      border-radius: 50%;
      border: 2px solid var(--pq-highlight);
      animation: ripple 900ms var(--pq-ease-out-expo) forwards;
      pointer-events: none;
    }
    @keyframes ripple {
      from {
        transform: scale(0.2);
        opacity: 1;
      }
      to {
        transform: scale(1);
        opacity: 0;
      }
    }
    @keyframes pin-pulse {
      70% {
        box-shadow: 0 0 0 14px rgb(124 92 255 / 0);
      }
      100% {
        box-shadow: 0 0 0 0 rgb(124 92 255 / 0);
      }
    }
  `,
})
export class SiteMap {
  readonly sites = input<readonly MapSite[]>([]);
  readonly selectedId = input<string | null>(null);
  /** Click on the map: proposes coordinates for a new or edited site. */
  readonly picked = output<{ latitude: number; longitude: number }>();

  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private L?: typeof Leaflet;
  private map?: Leaflet.Map;
  private layer?: Leaflet.LayerGroup;
  private lastRadius = new Map<string, number>();

  constructor() {
    const destroyRef = inject(DestroyRef);
    afterNextRender(async () => {
      this.L = await import('leaflet');
      const L = this.L;
      this.map = L.map(this.host().nativeElement, { zoomControl: true }).setView([5.33, -4.03], 12);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap',
      }).addTo(this.map);
      this.layer = L.layerGroup().addTo(this.map);
      this.map.on('click', (e: Leaflet.LeafletMouseEvent) =>
        this.picked.emit({
          latitude: +e.latlng.lat.toFixed(6),
          longitude: +e.latlng.lng.toFixed(6),
        }),
      );
      this.render();
    });
    effect(() => {
      this.sites();
      this.selectedId();
      this.render();
    });
    destroyRef.onDestroy(() => this.map?.remove());
  }

  private render(): void {
    const L = this.L;
    if (!L || !this.map || !this.layer) return;
    this.layer.clearLayers();
    const bounds: Leaflet.LatLngExpression[] = [];
    for (const site of this.sites()) {
      const center: Leaflet.LatLngExpression = [site.latitude, site.longitude];
      bounds.push(center);
      const selected = site.id === this.selectedId();
      L.circle(center, {
        radius: site.radius_m,
        color: selected ? '#D4FF3A' : '#7C5CFF',
        weight: selected ? 2 : 1,
        fillOpacity: 0.12,
      }).addTo(this.layer);
      L.marker(center, {
        icon: L.divIcon({ className: '', html: '<div class="pq-pin"></div>', iconSize: [18, 18] }),
        title: site.name,
      })
        .bindTooltip(site.name)
        .addTo(this.layer);
      const previous = this.lastRadius.get(site.id);
      if (selected && previous !== undefined && previous !== site.radius_m)
        this.ripple(center, site.radius_m);
      this.lastRadius.set(site.id, site.radius_m);
    }
    const selected = this.sites().find((s) => s.id === this.selectedId());
    if (selected)
      this.map.setView([selected.latitude, selected.longitude], Math.max(this.map.getZoom(), 15));
    else if (bounds.length)
      this.map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 15 });
  }

  /** Wave from the centre to the new geofence edge (transform/opacity only). */
  private ripple(center: Leaflet.LatLngExpression, radiusM: number): void {
    const L = this.L;
    if (!L || !this.map || !this.layer) return;
    const point = this.map.latLngToContainerPoint(center);
    const edge = this.map.latLngToContainerPoint(
      L.latLng(L.latLng(center).lat, L.latLng(center).lng + radiusM / 111_320),
    );
    const px = Math.max(24, Math.abs(edge.x - point.x) * 2);
    const marker = L.marker(center, {
      interactive: false,
      icon: L.divIcon({
        className: '',
        html: `<div class="pq-ripple" style="width:${px}px;height:${px}px"></div>`,
        iconSize: [px, px],
      }),
    }).addTo(this.layer);
    setTimeout(() => marker.remove(), 950);
  }
}
