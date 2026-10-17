import { AudioLines, FlaskConical, FileChartColumn, FileHeart, Fingerprint, FolderClock, Landmark, Link, PhoneCall, Radar, ScanFace, SlidersHorizontal } from 'lucide-react';

/** One icon per page, used by the sidebar, the page headers and the dashboard so they always match. */
export const PAGE_ICON = {
  dashboard: Radar,            // command center: scanning for threats
  scenarios: FlaskConical,     // scenario lab: scripted test scenarios
  family: PhoneCall,           // the impersonation call from a "relative"
  exam: ScanFace,              // face verification at the exam camera
  insurance: FileHeart,        // a (health / hospitalisation) claim document
  banking: Landmark,           // the bank
  voice: AudioLines,           // audio deepfake analysis
  speakers: Fingerprint,       // voiceprint
  reports: FileChartColumn,    // test reports
  cases: FolderClock,          // case history
  audit: Link,                 // hash-chained audit log
  settings: SlidersHorizontal, // configuration
} as const;
