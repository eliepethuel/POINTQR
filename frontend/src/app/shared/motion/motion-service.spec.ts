import { TestBed } from '@angular/core/testing';

import { MotionService } from './motion-service';

describe('MotionService', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-motion');
  });

  function create(): MotionService {
    TestBed.resetTestingModule();
    return TestBed.inject(MotionService);
  }

  it('follows the system preference by default', () => {
    const motion = create();
    expect(motion.preference()).toBe('system');
  });

  it('reduces motion when the user asks for it and flags the document', () => {
    const motion = create();
    motion.setPreference('reduced');
    TestBed.tick();
    expect(motion.reduced()).toBe(true);
    expect(motion.duration('slow')).toBe(0);
    expect(document.documentElement.getAttribute('data-motion')).toBe('reduced');
  });

  it('keeps full durations when the user forces full motion', () => {
    const motion = create();
    motion.setPreference('full');
    expect(motion.reduced()).toBe(false);
    expect(motion.duration('slow')).toBe(600);
  });

  it('remembers the preference across sessions', () => {
    create().setPreference('reduced');
    expect(create().preference()).toBe('reduced');
  });
});
