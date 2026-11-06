import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "../services/api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(() => Number(localStorage.getItem("pm_project")) || null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setProjects([]);
  }, []);

  const loadProjects = useCallback(async () => {
    const list = await api.projects();
    setProjects(list);
    setProjectId((cur) => {
      const next = list.find((p) => p.id === cur) ? cur : list[0]?.id ?? null;
      if (next) localStorage.setItem("pm_project", String(next));
      return next;
    });
    return list;
  }, []);

  const refresh = useCallback(async () => {
    const me = await api.me();
    setUser(me);
    if (me.onboarded) await loadProjects();
    return me;
  }, [loadProjects]);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    refresh()
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [logout, refresh]);

  const signIn = async (data, remember) => {
    tokenStore.set(data.access_token, remember);
    setUser(data.user);
    if (data.user.onboarded) await loadProjects();
  };

  const selectProject = (id) => {
    setProjectId(id);
    localStorage.setItem("pm_project", String(id));
  };

  const project = projects.find((p) => p.id === projectId) || null;

  return (
    <AuthContext.Provider value={{ user, setUser, projects, project, projectId, selectProject, loading, signIn, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}
