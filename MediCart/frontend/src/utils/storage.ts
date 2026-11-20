import type { User } from "@/types";

const ACCESS = "medicart.access_token";
const REFRESH = "medicart.refresh_token";
const USER = "medicart.user";
const RECENT = "medicart.recently_viewed";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) - session simply won't persist */
  }
}

export const session = {
  getAccessToken: () => read(ACCESS),
  getRefreshToken: () => read(REFRESH),
  getUser(): User | null {
    const raw = read(USER);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  },
  save(access: string, refresh: string, user: User) {
    write(ACCESS, access);
    write(REFRESH, refresh);
    write(USER, JSON.stringify(user));
  },
  setUser(user: User) {
    write(USER, JSON.stringify(user));
  },
  clear() {
    write(ACCESS, null);
    write(REFRESH, null);
    write(USER, null);
  },
};

export const recentlyViewed = {
  get(): number[] {
    const raw = read(RECENT);
    if (!raw) return [];
    try {
      const ids = JSON.parse(raw);
      return Array.isArray(ids) ? ids.filter((n) => typeof n === "number") : [];
    } catch {
      return [];
    }
  },
  push(id: number) {
    const ids = [id, ...recentlyViewed.get().filter((n) => n !== id)].slice(0, 8);
    write(RECENT, JSON.stringify(ids));
  },
};
