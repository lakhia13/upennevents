import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Header } from "./components/layout/Header";
import { CalendarPage } from "./pages/CalendarPage";
import { ListPage } from "./pages/ListPage";

export function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <div className="brandbar" />
        <Header />
        <Routes>
          <Route path="/" element={<Navigate to="/calendar" replace />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/list" element={<ListPage />} />
          <Route path="*" element={<Navigate to="/calendar" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
