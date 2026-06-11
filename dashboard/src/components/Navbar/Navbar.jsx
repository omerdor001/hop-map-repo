import { Link } from "react-router-dom"
import logo from "../../assets/hopemap_logo_v3.svg"
import "./Navbar.css"

function Navbar() {
  return (
    <nav className="nav">
      <div className="logo-row">
        <img src={logo} alt="HopeMap" width={140} />
      </div>

      <ul className="nav-links">
        <li><a href="#how">How it works</a></li>
        <li><a href="#pricing">Pricing</a></li>
        <li><a href="#install">Install</a></li>
        <li><a href="#contact">Contact</a></li>
      </ul>

      <Link to="/login" className="nav-cta">Get started free</Link>
    </nav>
  )
}

export default Navbar
