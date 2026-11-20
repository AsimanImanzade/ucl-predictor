import { Component, Suspense, useEffect, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router';
import { SiteFooter, SiteHeader, Sky } from './Frame';
import './Layout.css';

const NAV: { to: string; label: string; end?: boolean; more?: string }[] = [
  { to: '/', label: 'Table', end: true },
  { to: '/matches', label: 'Matches' },
  { to: '/what-if', label: 'What-if' },
  { to: '/knockout', label: 'Knockout', more: ' odds' },
  { to: '/methodology', label: 'Methodology' },
];

class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidUpdate(prev: { resetKey: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }
  render() {
    if (this.state.error) {
      return (
        <div className="page page-state" role="alert">
          <h1>This page could not load</h1>
          <p>{this.state.error.message} Check your connection and reload the page.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

export function Loading() {
  return (
    <div className="page page-state" aria-busy="true">
      <p>Loading forecasts…</p>
    </div>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    // Block body: newer browsers return a Promise from scrollTo, which is not a valid effect cleanup.
    window.scrollTo(0, 0);
  }, [pathname]);
  return (
    <>
      <Sky />
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader
        nav={
          <nav className="main-nav" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}>
                {n.label}
                {n.more && <span className="wide-only">{n.more}</span>}
              </NavLink>
            ))}
          </nav>
        }
      />
      <main id="main">
        <ErrorBoundary resetKey={pathname}>
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </main>
      <SiteFooter />
    </>
  );
}
