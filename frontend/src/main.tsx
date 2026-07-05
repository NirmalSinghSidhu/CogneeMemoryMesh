import { createRoot } from "react-dom/client";
import { setAuthTokenGetter } from "@workspace/api-client-react";
import { getStoredToken } from "@/lib/auth";
import App from "./App";
import "./index.css";

setAuthTokenGetter(() => getStoredToken());

createRoot(document.getElementById("root")!).render(<App />);
