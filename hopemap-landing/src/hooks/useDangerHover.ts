import { useTheme } from "../context/ThemeContext";

export function useDangerHover() {
  const { setMode } = useTheme();

  return {
    onMouseEnter: () => setMode("danger"),

    onMouseLeave: () => setMode("safe"),
  };
}
