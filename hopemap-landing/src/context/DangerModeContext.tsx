import { createContext, useContext, useState, type ReactNode } from "react";

type DangerModeContextType = {
  dangerMode: boolean;

  enableDanger: () => void;

  disableDanger: () => void;
};

const DangerModeContext = createContext<DangerModeContextType | null>(null);

type Props = {
  children: ReactNode;
};

export function DangerModeProvider({ children }: Props) {
  const [dangerMode, setDangerMode] = useState(false);

  return (
    <DangerModeContext.Provider
      value={{
        dangerMode,

        enableDanger: () => setDangerMode(true),

        disableDanger: () => setDangerMode(false),
      }}
    >
      {children}
    </DangerModeContext.Provider>
  );
}

export function useDangerMode() {
  const context = useContext(DangerModeContext);

  if (!context) {
    throw new Error("useDangerMode must be used inside DangerModeProvider");
  }

  return context;
}
