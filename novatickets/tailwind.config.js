/** Tailwind CSS — thème NovaTickets : blanc et vert. */
module.exports = {
  content: ["./templates/**/*.html", "./*/templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"] },
      colors: {
        brand: {
          50: "#f0fdf4", 100: "#dcfce7", 200: "#bbf7d0", 300: "#86efac", 400: "#4ade80",
          500: "#22c55e", 600: "#16a34a", 700: "#15803d", 800: "#166534", 900: "#14532d", 950: "#052e16",
        },
        nova: { navy: "#14284b", orange: "#f28c28" },
      },
      boxShadow: {
        soft: "0 1px 2px rgba(16,24,40,.04), 0 8px 24px -8px rgba(22,101,52,.12)",
        lift: "0 2px 4px rgba(16,24,40,.05), 0 16px 40px -12px rgba(22,101,52,.22)",
      },
    },
  },
  plugins: [],
};
