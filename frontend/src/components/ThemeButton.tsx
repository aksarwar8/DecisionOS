import { useState } from "react";
import { Moon, Sun } from "lucide-react";

const themeKey = "decisionos-theme";

export function useTheme() {
  const [dark, setDark] = useState(() => localStorage.getItem(themeKey) === "dark");
  function toggle() {
    const next = !dark;
    localStorage.setItem(themeKey, next ? "dark" : "light");
    setDark(next);
  }
  return { dark, toggle };
}

export function ThemeButton({dark,toggle}: {dark:boolean;toggle:()=>void}) {
  return <button className="icon-button" onClick={toggle} aria-label="Toggle color theme" aria-pressed={dark}>{dark ? <Sun size={18}/> : <Moon size={18}/>}</button>;
}
