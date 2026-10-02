import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import QuickView from "./components/QuickView";
import { isQuickWindow } from "./lib/api";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {isQuickWindow() ? <QuickView /> : <App />}
  </React.StrictMode>
);
