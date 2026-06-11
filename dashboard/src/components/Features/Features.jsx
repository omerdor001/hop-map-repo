import { FaBell, FaLock } from "react-icons/fa"
import { BsEyeSlash, BsGeoAlt } from "react-icons/bs"
import "./Features.css"

function Features() {
  return (
    <section className="feature-strip">
      <div className="feature-item">
        <div className="feature-icon"><BsEyeSlash /></div>
        <div>
          <h3>No message reading</h3>
          <p>Detects patterns, never reads private chats</p>
        </div>
      </div>

      <div className="feature-item">
        <div className="feature-icon"><FaBell /></div>
        <div>
          <h3>Real-time alerts</h3>
          <p>Instant parent notifications</p>
        </div>
      </div>

      <div className="feature-item">
        <div className="feature-icon"><BsGeoAlt /></div>
        <div>
          <h3>Pinpoints the moment</h3>
          <p>Platform, time and risk level</p>
        </div>
      </div>

      <div className="feature-item">
        <div className="feature-icon"><FaLock /></div>
        <div>
          <h3>Privacy-first</h3>
          <p>Data stays on device</p>
        </div>
      </div>
    </section>
  )
}

export default Features
