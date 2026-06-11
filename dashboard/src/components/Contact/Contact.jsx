import { FaWhatsapp } from "react-icons/fa"
import { BsEnvelope, BsGeoAlt } from "react-icons/bs"
import "./Contact.css"

function Contact() {
  return (
    <section id="contact" className="section">
      <p className="section-label">Contact</p>

      <h2 className="section-title">Get in touch</h2>

      <div className="contact-grid">
        <div>
          <p>Questions about HopeMap? We&apos;d love to hear from you.</p>

          <div className="contact-row">
            <BsEnvelope />
            theggirls@hopemap.io
          </div>

          <div className="contact-row">
            <FaWhatsapp />
            Chat on WhatsApp
          </div>

          <div className="contact-row">
            <BsGeoAlt />
            Israel
          </div>
        </div>

        <form className="contact-form">
          <input placeholder="First Name" />
          <input placeholder="Last Name" />
          <input placeholder="Email" />

          <select>
            <option>Parent</option>
            <option>School / Organization</option>
            <option>Gaming Platform</option>
            <option>Other</option>
          </select>

          <textarea placeholder="Message..." />

          <button>Send Message</button>
        </form>
      </div>
    </section>
  )
}

export default Contact
