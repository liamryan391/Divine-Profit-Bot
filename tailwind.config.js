/** @type {import('tailwindcss').Config} */
export default {
  content: ["./frontend/index.html", "./frontend/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        temple: {
          bg: "#07080d",
          surface: "#111827",
          panel: "#172033",
          panelDeep: "#0b1221",
          line: "#26334a",
          text: "#f4f7fb",
          muted: "#9db0c8",
          gold: "#ffc640",
          green: "#14d89c",
          blue: "#4b87ff",
          violet: "#8a5cff",
          red: "#ff6575",
        },
      },
      boxShadow: {
        temple: "0 18px 60px rgba(0, 0, 0, 0.28)",
        glow: "0 0 34px rgba(255, 198, 64, 0.14)",
      },
    },
  },
  plugins: [],
};
