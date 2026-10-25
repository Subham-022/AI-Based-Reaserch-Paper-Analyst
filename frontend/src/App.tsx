import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import LibraryPage from './pages/LibraryPage';
import ComparePage from './pages/ComparePage';

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
          element={<ComparePage />}
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