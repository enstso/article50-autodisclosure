/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        canvas: "#f8fafc",
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15, 23, 42, 0.06), 0 12px 32px rgba(15, 23, 42, 0.06)",
        hero: "0 2px 4px rgba(15, 23, 42, 0.05), 0 32px 80px rgba(79, 70, 229, 0.14)",
      },
    },
  },
  plugins: [],
};
