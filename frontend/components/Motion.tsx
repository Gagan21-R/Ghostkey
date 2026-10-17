'use client';
import { MotionConfig } from 'motion/react';

/** Global motion settings: honour the OS "reduce motion" preference everywhere. */
export default function Motion({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user" transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}>{children}</MotionConfig>;
}
