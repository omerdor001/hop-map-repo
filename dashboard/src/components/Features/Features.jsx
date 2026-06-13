import { FaBell, FaLock } from "react-icons/fa"
import { BsEyeSlash, BsGeoAlt } from "react-icons/bs"
import "./Features.css"

function Features() {
  return (
    <section className="feature-strip">
      <div className="feature-item">
        <div className="feature-icon"><BsEyeSlash /></div>
        <div>
          <h3>Catches every hop</h3>
          <p>Spots the moment your child switches apps</p>
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
          <p>Only the hop is saved — nothing else</p>
        </div>
      </div>
    </section>
  )
}

export default Features
