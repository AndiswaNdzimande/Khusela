import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import NewCheckPage from "./pages/NewCheckPage";
import NotFoundPage from "./pages/NotFoundPage";
import ResultPage from "./pages/ResultPage";

function ProtectedLayout() {
  const { session } = useAuth();
  const location = useLocation();

  if (!session) {
    const from = location.pathname.startsWith("/result/")
      ? undefined
      : location.pathname;
    return <Navigate to="/login" replace state={from ? { from } : undefined} />;
  }

  return <Layout />;
}

function LoginRoute() {
  const { session } = useAuth();
  return session ? <Navigate to="/check" replace /> : <LoginPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<Navigate to="/check" replace />} />
        <Route path="/check" element={<NewCheckPage />} />
        <Route path="/result/:checkId" element={<ResultPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
