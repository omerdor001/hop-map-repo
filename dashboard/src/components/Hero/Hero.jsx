import "./Hero.css"

function Hero() {
  return (
    <section className="hero">
      <p className="tagline">To give the hop a hope</p>

      <h1 className="hero-title">
        <span className="word-pink">Protect</span> your kids at the{" "}
        <span className="word-critical">critical moment</span>
      </h1>

      <p className="hero-subtitle">
        Every day, children are invited to leave safe gaming platforms for
        unmonitored spaces — Discord, Telegram and WhatsApp. HopeMap catches
        that exact moment and alerts you before danger grows.
      </p>

      <div className="hero-buttons">
        <button className="primary-btn">Start protecting now</button>
        <button className="secondary-btn">See how it works</button>
      </div>
    </section>
  )
}

export default Hero
