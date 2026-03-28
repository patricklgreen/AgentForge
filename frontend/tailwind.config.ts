/** @type {import('tailwindcss').Config} */
export default {
    content: [
      "./index.html",
      "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
      extend: {
        fontFamily: {
          mono: [
            "JetBrains Mono",
            "Fira Code",
            "Cascadia Code",
            "Consolas",
            "ui-monospace",
            "monospace",
          ],
        },
        colors: {
          gray: {
            950: "#0a0a0f",
          },
        },
        animation: {
          "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        },
      },
    },
    plugins: [],
  };
  