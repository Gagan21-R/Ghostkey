'use client';

/**
 * Momentum Rail — adapted for GhostKey's face and voice example cards.
 * Based on "Momentum Rail" by @dorianbaffier, Kokonut UI (MIT): https://kokonutui.com ·
 * https://github.com/kokonut-labs/kokonutui
 * A card rail you can flick with the mouse: the release velocity projects an end point, a spring snaps to the
 * nearest card and the ends rubber-band. Scroll position drives a cover-flow depth, image parallax and the
 * centered card's details with CSS scroll-driven animations.
 * Changes: generic cards via `renderCard`, drags never start on controls (buttons, audio players), clicking a
 * side card centers it, GhostKey dark theme.
 */

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { type ReactNode, type RefObject, useCallback, useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

const RAIL_CSS = `
@keyframes kokonutui-rail-tilt {
  0% { transform: perspective(900px) translateZ(-180px) rotateY(-14deg); }
  50% { transform: perspective(900px) translateZ(0) rotateY(0deg); }
  100% { transform: perspective(900px) translateZ(-180px) rotateY(14deg); }
}
@keyframes kokonutui-rail-parallax {
  from { transform: translate3d(calc(var(--rail-depth) * -1), 0, 0); }
  to { transform: translate3d(var(--rail-depth), 0, 0); }
}
@keyframes kokonutui-rail-details {
  0%, 30% { opacity: 0.12; transform: translate3d(0, 6px, 0); }
  44%, 56% { opacity: 1; transform: translate3d(0, 0, 0); }
  70%, 100% { opacity: 0.12; transform: translate3d(0, 6px, 0); }
}
@keyframes kokonutui-rail-glow {
  0%, 35% { opacity: 0; }
  50% { opacity: 1; }
  65%, 100% { opacity: 0; }
}
@supports (animation-timeline: view()) {
  .kokonutui-rail-card { view-timeline: --kokonutui-rail inline; }
  .kokonutui-rail-details, .kokonutui-rail-glow {
    animation: kokonutui-rail-details linear both;
    animation-timeline: --kokonutui-rail;
  }
  .kokonutui-rail-glow { animation-name: kokonutui-rail-glow; }
  @media (prefers-reduced-motion: no-preference) {
    .kokonutui-rail-tilt {
      animation: kokonutui-rail-tilt linear both;
      animation-timeline: --kokonutui-rail;
    }
    .kokonutui-rail-layer {
      animation: kokonutui-rail-parallax linear both;
      animation-timeline: --kokonutui-rail;
    }
  }
}
`;

/** Wrap an image/visual so it parallaxes inside its card. `depth` is the travel each way as a % of its width. */
export const RailLayer = ({ depth = 8, children }: { depth?: number; children: ReactNode }) => (
  <div className="kokonutui-rail-layer absolute inset-y-0 -left-[15%] w-[130%]" style={{ ['--rail-depth' as string]: `${depth}%` }}>
    {children}
  </div>
);

/** Content that fades in as its card reaches the center. */
export const RailDetails = ({ className, children }: { className?: string; children: ReactNode }) => (
  <div className={cn('kokonutui-rail-details', className)}>{children}</div>
);

/* ------------------------------------------------------------------ */
/* Momentum: drag, project, spring to a card, rubber-band at the ends. */
/* ------------------------------------------------------------------ */

const STIFFNESS = 170;
const DAMPING = 26; // about 2·√170: critically damped, so no bounce at the card
const DECELERATION = 0.997; // UIScrollView's normal rate, per ms
const DRAG_THRESHOLD = 4;
const NO_DRAG = 'button, audio, video, input, select, textarea, a, label, [data-no-drag]';

const rubber = (overshoot: number, size: number) => Math.sign(overshoot) * (1 - 1 / ((Math.abs(overshoot) * 0.55) / size + 1)) * size;
const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

interface RailState {
  mode: 'idle' | 'pressing' | 'dragging' | 'spring';
  pointerId: number;
  startX: number;
  startPos: number;
  pos: number;
  vel: number;
  target: number;
  samples: { t: number; x: number }[];
  raf: number;
  last: number;
  suppressClick: boolean;
}

const maxScroll = (scroller: HTMLElement) => scroller.scrollWidth - scroller.clientWidth;

const snapPoints = (scroller: HTMLElement, track: HTMLUListElement) => {
  const max = maxScroll(scroller);
  return Array.from(track.children, (child) => {
    const card = child as HTMLElement;
    const center = track.offsetLeft + card.offsetLeft + card.offsetWidth / 2;
    return clamp(center - scroller.clientWidth / 2, 0, max);
  });
};

const nearestIndex = (points: number[], pos: number) => {
  let best = 0;
  for (let i = 1; i < points.length; i++) if (Math.abs(points[i] - pos) < Math.abs(points[best] - pos)) best = i;
  return best;
};

// Release velocity in px/ms from the last 100ms of samples; a pause before letting go means no flick.
const releaseVelocity = (samples: RailState['samples'], now: number) => {
  const first = samples[0];
  const last = samples.at(-1) ?? first;
  const dt = last.t - first.t;
  if (dt <= 0 || now - last.t > 60) return 0;
  return -(last.x - first.x) / dt;
};

function useMomentumRail(scrollerRef: RefObject<HTMLElement | null>, trackRef: RefObject<HTMLUListElement | null>, onIndex: (index: number) => void) {
  const state = useRef<RailState>({ mode: 'idle', pointerId: -1, startX: 0, startPos: 0, pos: 0, vel: 0, target: 0, samples: [], raf: 0, last: 0, suppressClick: false });
  const onIndexRef = useRef(onIndex);
  onIndexRef.current = onIndex;

  // Write a virtual position: the in-range part scrolls natively, the rest becomes a damped translate (rubber band).
  const apply = useCallback((pos: number) => {
    const scroller = scrollerRef.current;
    const track = trackRef.current;
    if (!(scroller && track)) return;
    const inRange = clamp(pos, 0, maxScroll(scroller));
    scroller.scrollLeft = inRange;
    const over = pos - inRange;
    track.style.transform = Math.abs(over) > 0.1 ? `translate3d(${(-rubber(over, scroller.clientWidth)).toFixed(2)}px,0,0)` : '';
  }, [scrollerRef, trackRef]);

  // Native scroll snap is off while JS owns the position.
  const setFree = useCallback((free: boolean) => {
    if (scrollerRef.current) scrollerRef.current.dataset.free = String(free);
  }, [scrollerRef]);

  const step = useCallback((now: number) => {
    const s = state.current;
    const dt = Math.min((now - s.last) / 1000, 1 / 30);
    s.last = now;
    const h = dt / 4; // semi-implicit Euler substeps keep the spring stable at any frame rate
    for (let i = 0; i < 4; i++) {
      const accel = -STIFFNESS * (s.pos - s.target) - DAMPING * s.vel;
      s.vel += accel * h;
      s.pos += s.vel * h;
    }
    if (Math.abs(s.pos - s.target) < 0.5 && Math.abs(s.vel) < 8) {
      s.pos = s.target;
      s.vel = 0;
      s.mode = 'idle';
      apply(s.target);
      setFree(false);
      return;
    }
    apply(s.pos);
    s.raf = requestAnimationFrame(step);
  }, [apply, setFree]);

  const springTo = useCallback((target: number, velocity: number) => {
    const s = state.current;
    const scroller = scrollerRef.current;
    if (!scroller) return;
    cancelAnimationFrame(s.raf);
    if (s.mode !== 'spring' && s.mode !== 'dragging') s.pos = scroller.scrollLeft;
    s.target = target;
    s.vel = velocity;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      s.mode = 'idle';
      s.pos = target;
      apply(target);
      setFree(false);
      return;
    }
    s.mode = 'spring';
    setFree(true);
    s.last = performance.now();
    s.raf = requestAnimationFrame(step);
  }, [apply, scrollerRef, setFree, step]);

  const goTo = useCallback((index: number) => {
    const scroller = scrollerRef.current;
    const track = trackRef.current;
    if (!(scroller && track)) return;
    const s = state.current;
    const points = snapPoints(scroller, track);
    springTo(points[clamp(index, 0, points.length - 1)], s.mode === 'spring' ? s.vel : 0);
  }, [scrollerRef, springTo, trackRef]);

  const currentIndex = useCallback(() => {
    const scroller = scrollerRef.current;
    const track = trackRef.current;
    if (!(scroller && track)) return 0;
    const s = state.current;
    return nearestIndex(snapPoints(scroller, track), s.mode === 'spring' ? s.target : scroller.scrollLeft);
  }, [scrollerRef, trackRef]);

  useEffect(() => {
    const scroller = scrollerRef.current;
    const track = trackRef.current;
    if (!(scroller && track)) return;
    const s = state.current;
    let scrollRaf = 0;

    const onScroll = () => {
      cancelAnimationFrame(scrollRaf);
      scrollRaf = requestAnimationFrame(() => onIndexRef.current(nearestIndex(snapPoints(scroller, track), scroller.scrollLeft)));
    };
    const onPointerDown = (e: PointerEvent) => {
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      if ((e.target as Element).closest(NO_DRAG)) return; // controls keep working; drags start on the card body
      cancelAnimationFrame(s.raf);
      s.pos = s.mode === 'spring' ? s.pos : scroller.scrollLeft; // catching a moving rail keeps its position
      s.mode = 'pressing';
      s.pointerId = e.pointerId;
      s.startX = e.clientX;
      s.startPos = s.pos;
      s.samples = [{ t: e.timeStamp, x: e.clientX }];
    };
    const onPointerMove = (e: PointerEvent) => {
      if (e.pointerId !== s.pointerId) return;
      const dx = e.clientX - s.startX;
      if (s.mode === 'pressing' && Math.abs(dx) > DRAG_THRESHOLD) {
        s.mode = 'dragging';
        scroller.setPointerCapture(e.pointerId);
        scroller.dataset.dragging = 'true';
        setFree(true);
      }
      if (s.mode !== 'dragging') return;
      s.pos = s.startPos - dx;
      apply(s.pos);
      s.samples.push({ t: e.timeStamp, x: e.clientX });
      while (s.samples.length > 2 && e.timeStamp - s.samples[0].t > 100) s.samples.shift();
    };
    const onRelease = (e: PointerEvent) => {
      if (e.pointerId !== s.pointerId) return;
      s.pointerId = -1;
      if (s.mode !== 'dragging') {
        s.mode = 'idle';
        setFree(false);
        return;
      }
      scroller.dataset.dragging = 'false';
      s.suppressClick = true;
      setTimeout(() => { s.suppressClick = false; }, 0);
      const v = releaseVelocity(s.samples, e.timeStamp);
      const projected = s.pos + (v * DECELERATION) / (1 - DECELERATION);
      const points = snapPoints(scroller, track);
      springTo(points[nearestIndex(points, projected)], v * 1000);
    };
    // A drag that ends over a card must not click it.
    const onClickCapture = (e: MouseEvent) => {
      if (s.suppressClick) {
        e.preventDefault();
        e.stopPropagation();
        s.suppressClick = false;
      }
    };
    // Wheel or touch takes over from a running spring.
    const onNativeInput = () => {
      if (s.mode !== 'spring') return;
      cancelAnimationFrame(s.raf);
      s.mode = 'idle';
      apply(clamp(s.pos, 0, maxScroll(scroller)));
      setFree(false);
    };
    // Arrow keys step one card; Home and End jump to the ends.
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target !== scroller) return;
      const index = nearestIndex(snapPoints(scroller, track), s.mode === 'spring' ? s.target : scroller.scrollLeft);
      const next = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: track.children.length - 1 }[e.key];
      if (next === undefined) return;
      e.preventDefault();
      goTo(next);
    };

    scroller.addEventListener('keydown', onKeyDown);
    scroller.addEventListener('scroll', onScroll, { passive: true });
    scroller.addEventListener('pointerdown', onPointerDown);
    scroller.addEventListener('pointermove', onPointerMove);
    scroller.addEventListener('pointerup', onRelease);
    scroller.addEventListener('pointercancel', onRelease);
    scroller.addEventListener('lostpointercapture', onRelease);
    scroller.addEventListener('click', onClickCapture, true);
    scroller.addEventListener('wheel', onNativeInput, { passive: true });
    scroller.addEventListener('touchstart', onNativeInput, { passive: true });
    return () => {
      cancelAnimationFrame(scrollRaf);
      cancelAnimationFrame(s.raf);
      scroller.removeEventListener('keydown', onKeyDown);
      scroller.removeEventListener('scroll', onScroll);
      scroller.removeEventListener('pointerdown', onPointerDown);
      scroller.removeEventListener('pointermove', onPointerMove);
      scroller.removeEventListener('pointerup', onRelease);
      scroller.removeEventListener('pointercancel', onRelease);
      scroller.removeEventListener('lostpointercapture', onRelease);
      scroller.removeEventListener('click', onClickCapture, true);
      scroller.removeEventListener('wheel', onNativeInput);
      scroller.removeEventListener('touchstart', onNativeInput);
    };
  }, [apply, goTo, scrollerRef, setFree, springTo, trackRef]);

  return { goTo, currentIndex };
}

/* ------------------------------------------------------------------ */
/* Rail                                                               */
/* ------------------------------------------------------------------ */

const ARROW_CLASS =
  'grid size-8 cursor-pointer place-items-center rounded-full border-2 border-[var(--ink)] bg-[var(--panel2)] text-[var(--ink)] transition-[background-color,opacity] duration-150 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-sky-400 aria-disabled:cursor-default aria-disabled:opacity-35';

export default function MomentumRail<T>({
  items, getKey, renderCard, title, eyebrow, className,
}: {
  items: T[]; getKey: (item: T) => string; renderCard: (item: T, state: { active: boolean; index: number }) => ReactNode;
  title: string; eyebrow?: string; className?: string;
}) {
  const scrollerRef = useRef<HTMLElement>(null);
  const trackRef = useRef<HTMLUListElement>(null);
  const [active, setActive] = useState(0);
  const { goTo, currentIndex } = useMomentumRail(scrollerRef, trackRef, setActive);
  const step = (delta: number) => goTo(currentIndex() + delta);

  return (
    <section
      aria-label={title}
      aria-roledescription="carousel"
      className={cn('@container/rail w-full [--rail-card:17rem] @md/rail:[--rail-card:19rem] @3xl/rail:[--rail-card:21rem]', className)}
    >
      <div className="mb-1 flex items-end justify-between gap-4 px-1">
        <div className="min-w-0">
          {eyebrow && <p className="text-xs text-[var(--ink2)]">{eyebrow}</p>}
          <h2 className="truncate text-lg font-semibold tracking-tight">{title}</h2>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span aria-live="polite" className="mr-1 text-xs tabular-nums text-[var(--ink2)]">
            <span className="sr-only">Card </span>
            {String(active + 1).padStart(2, '0')}
            <span aria-hidden="true"> / </span>
            <span className="sr-only"> of </span>
            {String(items.length).padStart(2, '0')}
          </span>
          <button aria-disabled={active === 0} aria-label="Previous" className={ARROW_CLASS} onClick={() => step(-1)} type="button">
            <ChevronLeft aria-hidden="true" className="size-4" />
          </button>
          <button aria-disabled={active === items.length - 1} aria-label="Next" className={ARROW_CLASS} onClick={() => step(1)} type="button">
            <ChevronRight aria-hidden="true" className="size-4" />
          </button>
        </div>
      </div>

      <section
        aria-label={`${title}, use arrow keys to move`}
        className="relative snap-x snap-mandatory overflow-x-auto overscroll-x-contain py-6 outline-none [scrollbar-width:none] focus-visible:ring-2 focus-visible:ring-sky-400/60 focus-visible:ring-inset data-[dragging=true]:cursor-grabbing data-[free=true]:snap-none [&::-webkit-scrollbar]:hidden [@media(pointer:fine)]:cursor-grab [@media(pointer:fine)]:select-none"
        ref={scrollerRef}
        tabIndex={0}
        style={{ maskImage: 'linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent)' }}
      >
        <ul className="relative flex w-max gap-5 px-[calc(50cqw-var(--rail-card)/2)]" ref={trackRef}>
          {items.map((item, index) => (
            <li
              className="kokonutui-rail-card w-(--rail-card) flex-none snap-center"
              key={getKey(item)}
              onClick={(e) => { if (index !== active && !(e.target as Element).closest(NO_DRAG)) goTo(index); }}
            >
              <div className="kokonutui-rail-tilt relative h-full">{renderCard(item, { active: index === active, index })}</div>
            </li>
          ))}
        </ul>
      </section>

      <style href="kokonutui-carousel-cards" precedence="default">{RAIL_CSS}</style>
    </section>
  );
}
