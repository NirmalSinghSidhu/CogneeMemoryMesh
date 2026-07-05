import { AppLayout } from "@/components/layout";
import { RequireAuth, RedirectIfAuth } from "@/components/require-auth";
import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/context/auth-context";
import NotFound from "@/pages/not-found";
import Dashboard from "@/pages/dashboard";
import Meetings from "@/pages/meetings";
import MeetingDetail from "@/pages/meeting-detail";
import Graph from "@/pages/graph";
import Search from "@/pages/search";
import Chat from "@/pages/chat";
import Decisions from "@/pages/decisions";
import DecisionEvolution from "@/pages/decision-evolution";
import Timeline from "@/pages/timeline";
import Memory from "@/pages/memory";
import Entities from "@/pages/entities";
import Settings from "@/pages/settings";
import Login from "@/pages/login";
import Register from "@/pages/register";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: false
    }
  }
});

function ProtectedRouter() {
  return (
    <RequireAuth>
      <AppLayout>
        <Switch>
          <Route path="/" component={Dashboard} />
          <Route path="/meetings" component={Meetings} />
          <Route path="/meetings/:id" component={MeetingDetail} />
          <Route path="/graph" component={Graph} />
          <Route path="/search" component={Search} />
          <Route path="/chat" component={Chat} />
          <Route path="/decisions" component={Decisions} />
          <Route path="/decisions/:id/evolution" component={DecisionEvolution} />
          <Route path="/timeline" component={Timeline} />
          <Route path="/memory" component={Memory} />
          <Route path="/entities" component={Entities} />
          <Route path="/settings" component={Settings} />
          <Route component={NotFound} />
        </Switch>
      </AppLayout>
    </RequireAuth>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
            <Switch>
              <Route path="/login">
                <RedirectIfAuth>
                  <Login />
                </RedirectIfAuth>
              </Route>
              <Route path="/register">
                <RedirectIfAuth>
                  <Register />
                </RedirectIfAuth>
              </Route>
              <Route>
                <ProtectedRouter />
              </Route>
            </Switch>
          </WouterRouter>
          <Toaster />
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
