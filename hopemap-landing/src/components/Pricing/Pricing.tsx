import "./Pricing.css";

function Pricing() {
  return (
    <section id="pricing" className="section">
      <p className="section-label">Plans</p>

      <h2 className="section-title">Choose your protection level</h2>

      <p className="section-subtitle">
        Start free, upgrade when you need more.
      </p>

      <div className="pricing-grid">
        <div className="pricing-card featured">
          <div className="badge">Most popular</div>

          <p className="plan-label">Plan</p>

          <h3 className="plan-name">Premium</h3>

          <div className="plan-price">
            ₪19
            <span>/ month</span>
          </div>

          <p className="plan-note">Cancel anytime</p>

          <div className="plan-divider" />

          <ul className="features-list">
            <li>✓ Unlimited children monitored</li>
            <li>✓ Unlimited alerts to parent</li>
            <li>✓ Real-time alerts</li>
            <li>✓ Monthly activity summary</li>
            <li>✓ Priority support</li>
          </ul>

          <button className="premium-btn">Start Premium trial</button>
        </div>

        <div className="pricing-card">
          <p className="plan-label">Plan</p>

          <h3 className="plan-name">Basic</h3>

          <div className="plan-price">
            Free
            <span> forever</span>
          </div>

          <p className="plan-note">No cost, no credit card</p>

          <div className="plan-divider" />

          <ul className="features-list">
            <li>✓ 1 child monitored</li>
            <li>✓ Up to 10 alerts</li>
            <li>✓ Real-time alerts</li>

            <li className="disabled">✕ Monthly summary</li>

            <li className="disabled">✕ Additional children</li>
          </ul>

          <button className="basic-btn">Get started free</button>
        </div>
      </div>
    </section>
  );
}

export default Pricing;
