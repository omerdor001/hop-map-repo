import { useTheme } from "../context/useTheme"
import "../App.css"
import Navbar from "../components/Navbar/Navbar"
import Hero from "../components/Hero/Hero"
import InteractiveMap from "../components/InteractiveMap/InteractiveMap"
import Features from "../components/Features/Features"
import Pricing from "../components/Pricing/Pricing"
import Contact from "../components/Contact/Contact"
import Footer from "../components/Footer/Footer"

export default function LandingPage() {
  const { mode } = useTheme()
  return (
    <div className={`pg ${mode}`}>
      <Navbar />
      <Hero />
      <InteractiveMap />
      <Features />
      <Pricing />
      <Contact />
      <Footer />
    </div>
  )
}
