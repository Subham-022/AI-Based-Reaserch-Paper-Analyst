import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import LibraryPage from './pages/LibraryPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/library" replace />}
        />

        <Route
          path="/library"
          element={<LibraryPage />}
        />

        <Route
          path="/compare"
          element={
            <main className="min-h-screen bg-slate-50 p-8">
              <h1 className="text-2xl font-semibold text-slate-900">
                Compare Papers
              </h1>
            </main>
          }
        />

        <Route
          path="*"
          element={<Navigate to="/library" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;