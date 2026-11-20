import { BrowserRouter, Link, Route, Routes } from 'react-router';
import { Layout } from './components/Layout';
import { KnockoutPage } from './pages/KnockoutPage';
import { MatchesPage } from './pages/MatchesPage';
import { MatchPage } from './pages/MatchPage';
import { MethodologyPage } from './pages/MethodologyPage';
import { TablePage } from './pages/TablePage';
import { TeamPage } from './pages/TeamPage';
import { WhatIfPage } from './pages/WhatIfPage';

function NotFound() {
  return (
    <div className="page page-state">
      <h1>Page not found</h1>
      <p>
        That address does not match a page. <Link to="/">Go to the table</Link>.
      </p>
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<TablePage />} />
          <Route path="matches" element={<MatchesPage />} />
          <Route path="match/:id" element={<MatchPage />} />
          <Route path="team/:id" element={<TeamPage />} />
          <Route path="what-if" element={<WhatIfPage />} />
          <Route path="knockout" element={<KnockoutPage />} />
          <Route path="methodology" element={<MethodologyPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
