import { useEffect, useState } from "react";

import { FaDiscord, FaTelegram, FaWhatsapp } from "react-icons/fa";

import { BsCamera } from "react-icons/bs";

import { useTheme } from "../../context/ThemeContext";

import "./InteractiveMap.css";

function InteractiveMap() {
  const { mode, setMode } = useTheme();

  const [matrixChars, setMatrixChars] = useState<string[]>([]);

  useEffect(() => {
    if (mode !== "danger") {
      setMatrixChars([]);
      return;
    }

    const generateMatrix = () => {
      const chars = Array.from({ length: 800 }, () =>
        Math.random() > 0.5 ? "1" : "0",
      );

      setMatrixChars(chars);
    };

    generateMatrix();

    const interval = setInterval(generateMatrix, 700);

    return () => clearInterval(interval);
  }, [mode]);

  return (
    <div className="map-block">
      <div className="map-canvas">
        {/* GRID */}

        <div className="grid-line vertical v1" />
        <div className="grid-line vertical v2" />
        <div className="grid-line vertical v3" />

        <div className="grid-line horizontal h1" />
        <div className="grid-line horizontal h2" />

        {/* MATRIX */}

        {mode === "danger" && (
          <div className="matrix-layer">
            {matrixChars.map((char, index) => (
              <span key={index}>{char}</span>
            ))}
          </div>
        )}

        {/* CONNECTIONS */}

        <svg className="conn-svg" viewBox="0 0 600 310">
          <line x1="300" y1="155" x2="93" y2="48" />

          <line x1="300" y1="155" x2="488" y2="256" />

          <line x1="300" y1="155" x2="448" y2="42" />

          <line x1="300" y1="155" x2="130" y2="248" />
        </svg>

        {/* SAFE ZONE */}

        <div className="safe-blob" />

        <div className="safe-zone">
          <div className="safe-icon">🧒</div>

          <span className="safe-title">Safe Zone</span>

          <span className="safe-apps">Roblox · Fortnite · Minecraft</span>
        </div>

        {/* DANGER APPS */}

        <div className="ext ex1" onMouseEnter={() => setMode("danger")}>
          <FaDiscord size={20} />
          <span>Discord</span>
        </div>

        <div className="ext ex2" onMouseEnter={() => setMode("danger")}>
          <FaTelegram size={20} />
          <span>Telegram</span>
        </div>

        <div className="ext ex3" onMouseEnter={() => setMode("danger")}>
          <FaWhatsapp size={20} />
          <span>WhatsApp</span>
        </div>

        <div className="ext ex4" onMouseEnter={() => setMode("danger")}>
          <BsCamera size={18} />
          <span>Snapchat</span>
        </div>

        {/* EXIT DANGER */}

        {mode === "danger" && (
          <div
            className="danger-overlay"
            onMouseLeave={() => setMode("safe")}
          />
        )}

        {/* ALERT */}

        {mode === "danger" && (
          <div className="warning-badge">⚠ Platform hop detected!</div>
        )}
      </div>

      <p className="map-hint">Hover external apps to simulate a platform hop</p>
    </div>
  );
}

export default InteractiveMap;
