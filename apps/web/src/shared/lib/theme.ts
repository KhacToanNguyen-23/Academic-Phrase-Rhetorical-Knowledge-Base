// Theme: mặc định light mỗi lần vào; chỉ nhớ lựa chọn của user trong phiên hiện tại (sessionStorage).
import { useState } from "react";

export type Theme = "light" | "dark";
const KEY = "aw-theme";

function read(): Theme {
  try {
    return sessionStorage.getItem(KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const t = read();
    apply(t);
    return t;
  });
  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    apply(next);
    try {
      if (next === "dark") sessionStorage.setItem(KEY, "dark");
      else sessionStorage.removeItem(KEY);
    } catch {
      // storage bị chặn: vẫn đổi theme, chỉ không nhớ được
    }
    setTheme(next);
  };
  return { theme, toggle };
}
