import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/home-page";
import { PeopleRoutePage } from "./pages/people-page";
import { TemplateRoutePage } from "./pages/template-page";
import { UploadPage } from "./pages/upload-page";
import "./styles/app.css";

export function App() {
  return <BrowserRouter><Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/tasks/new/upload" element={<UploadPage />} />
    <Route path="/tasks/:id/people" element={<PeopleRoutePage />} />
    <Route path="/tasks/:id/template" element={<TemplateRoutePage />} />
  </Routes></BrowserRouter>;
}
