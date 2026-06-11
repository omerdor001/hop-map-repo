import "./App.css";

import Navbar from "../src/components/Navbar/Navbar";
import Hero from "../src/components/Hero/Hero";
import InteractiveMap from "../src/components/InteractiveMap/InteractiveMap";
import Features from "../src/components/Features/Features";
import Pricing from "../src/components/Pricing/Pricing";
import Install from "../src/components/Install/Install";
import Contact from "../src/components/Contact/Contact";
import Footer from "../src/components/Footer/Footer";

import { useTheme } from "./context/ThemeContext";

function App() {
  const { mode } = useTheme();

  return (
    <div className={`pg ${mode}`}>
      <Navbar />

      <Hero />

      <InteractiveMap />

      <Features />

      <Pricing />

      <Install />

      <Contact />

      <Footer />
    </div>
  );
}

export default App;
