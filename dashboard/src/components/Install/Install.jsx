import { FaWhatsapp, FaDownload } from "react-icons/fa"
import { BsLaptop, BsPlayCircle, BsQrCode } from "react-icons/bs"
import "./Install.css"

function Install() {
  return (
    <section id="install" className="section">
      <p className="section-label">Setup</p>

      <h2 className="section-title">Get running in minutes</h2>

      <p className="section-subtitle">
        Two simple pieces — takes less than 5 minutes.
      </p>

      <div className="install-grid">
        <div className="install-card">
          <div className="install-icon">
            <FaWhatsapp />
          </div>

          <h3>WhatsApp Alert Bot</h3>

          <p>Receive instant notifications.</p>

          <ol>
            <li>Scan QR code</li>
            <li>Send /start</li>
            <li>Link device</li>
          </ol>

          <button className="install-btn">
            <BsQrCode />
            <span>Show QR Code</span>
          </button>
        </div>

        <div className="install-card">
          <div className="install-icon">
            <BsLaptop />
          </div>

          <h3>Desktop Agent</h3>

          <p>Lightweight background monitor.</p>

          <ol>
            <li>Download installer</li>
            <li>Run as admin</li>
            <li>Enter pairing code</li>
          </ol>

          <div className="video-thumb">
            <BsPlayCircle />
            Watch install video
          </div>

          <button className="install-btn">
            <FaDownload />
            <span>Download Windows</span>
          </button>
        </div>
      </div>
    </section>
  )
}

export default Install
