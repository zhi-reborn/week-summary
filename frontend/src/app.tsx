import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/home-page";
import { AnalysisRoutePage } from "./pages/analysis-page";
import { PeopleRoutePage } from "./pages/people-page";
import { ReviewRoutePage } from "./pages/review-page";
import { SettingsPage } from "./pages/settings-page";
import { TemplateRoutePage } from "./pages/template-page";
import { UploadPage } from "./pages/upload-page";
import "./styles/app.css";

export function App() {
  return <BrowserRouter><Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/settings" element={<SettingsPage />} />
    <Route path="/tasks/new/upload" element={<UploadPage />} />
    <Route path="/tasks/:id/people" element={<PeopleRoutePage />} />
    <Route path="/tasks/:id/template" element={<TemplateRoutePage />} />
    <Route path="/tasks/:id/analysis" element={<AnalysisRoutePage />} />
    <Route path="/tasks/:id/review" element={<ReviewRoutePage />} />
  </Routes></BrowserRouter>;
}
