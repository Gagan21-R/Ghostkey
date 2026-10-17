/** Short page transition, re-mounted on every navigation. Pure CSS (.fade-in) so content never waits for JavaScript. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="fade-in">{children}</div>;
}
