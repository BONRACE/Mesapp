/* Salubre Cité — Plateforme multi-rôles de gestion des déchets, routage GPS PostGIS, QR codes signés HMAC-SHA256 et bourse de matières recyclées.
   Design plan : Typographie Khand 700 (titres pochoir urbain) + Hind (corps) + IBM Plex Mono (jetons QR, SQL PostGIS, OTP).
   Palette : Lagune Profonde #054544, Teal Collecte #178f92 (#005f62 sur fond clair), Ocre Latérite #ae8548, Terre #4e3910, Craie #f7fafa. */
import { useState } from "react";
import "./styles.css";
import Nav from "./components/Nav";
import Home, { Hero } from "./components/Home";
import AuthOtp from "./components/AuthOtp";
import Dashboard from "./components/Dashboard";
import QrStudio from "./components/QrStudio";
import Marketplace from "./components/Marketplace";
import BackendExplorer from "./components/BackendExplorer";

export default function App() {
  const [page, setPage] = useState("home");
  const [activeRole, setActiveRole] = useState("collecteur");
  const [user, setUser] = useState(null);
  const [selectedBin, setSelectedBin] = useState(null);

  const go = (nextPage) => {
    setPage(nextPage);
    window.scrollTo({ top: 0 });
  };

  const navProps = { page, go, user, activeRole, setActiveRole };

  return (
    <div className="min-h-screen flex flex-col">
      {page === "home" ? (
        <>
          <Hero go={go} setActiveRole={setActiveRole}>
            <Nav {...navProps} dark />
          </Hero>
          <main className="flex-1">
            <Home go={go} setActiveRole={setActiveRole} />
          </main>
        </>
      ) : (
        <>
          <Nav {...navProps} />
          <main className="flex-1">
            {page === "auth" && (
              <AuthOtp
                initialRole={activeRole}
                go={go}
                onSuccess={(u) => {
                  setUser(u);
                  setActiveRole(u.role);
                }}
              />
            )}
            {page === "dashboard" && (
              <Dashboard
                activeRole={activeRole}
                setActiveRole={setActiveRole}
                user={user}
                go={go}
                onScanBin={(bin) => setSelectedBin(bin)}
              />
            )}
            {page === "qr" && (
              <QrStudio
                selectedBin={selectedBin}
                onAwardPoints={(pts) =>
                  setUser((u) =>
                    u ? { ...u, ecoPoints: u.ecoPoints + pts } : { name: "Kossi Collecteur", role: activeRole, ecoPoints: 340 + pts }
                  )
                }
              />
            )}
            {page === "market" && <Marketplace />}
            {page === "backend" && <BackendExplorer />}
          </main>
        </>
      )}
      <footer className="bg-[var(--deep)] px-6 py-7 text-center text-[14px] text-[#cae5e4]">
        Salubre Cité · Architecture FastAPI + PostgreSQL / PostGIS (SRID 4326) · Auth Téléphone OTP · QR HMAC-SHA256 · Bourse Matières Recyclées
      </footer>
    </div>
  );
}
