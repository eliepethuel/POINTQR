import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { CountUp } from './count-up';
import { MotionService } from './motion-service';
import { easeOutExpo } from './motion-tokens';

@Component({
  imports: [CountUp],
  template: `<span [pqCountUp]="value()" [countDecimals]="decimals" countSuffix=" %"></span>`,
})
class Host {
  readonly value = signal(1234.5);
  decimals = 1;
}

describe('CountUp', () => {
  it('renders the final value immediately when motion is reduced', async () => {
    TestBed.inject(MotionService).setPreference('reduced');
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    // fr-FR uses a narrow no-break space as thousands separator and a comma for decimals.
    expect(text.replace(/\s/g, ' ')).toBe('1 234,5 %');
  });
});

describe('easeOutExpo', () => {
  it('starts at 0, ends at 1 and is monotonic', () => {
    expect(easeOutExpo(0)).toBe(0);
    expect(easeOutExpo(1)).toBe(1);
    expect(easeOutExpo(0.5)).toBeGreaterThan(easeOutExpo(0.25));
  });
});
