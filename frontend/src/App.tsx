import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Conversation from "./pages/Conversation";
import Projects from "./pages/Projects";
import Context from "./pages/Context";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Home />} />
          <Route path="/conversation/:conversationId" element={<Conversation />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/context" element={<Context />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
