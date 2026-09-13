import { Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/HomePage";
import { ScanPage } from "./pages/ScanPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/scan/:scanId" element={<ScanPage />} />
    </Routes>
  );
}
