module.exports = {
  content: [
    "./core/templates/core/index.html",
    "./core/templates/core/header.html",
    "./core/templates/core/footer.html"
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#f425c0",
        "background-light": "#f8f5f8",
        "background-dark": "#000000",
        secondary: "#00f0ff"
      },
      fontFamily: {
        display: ["Montserrat", "sans-serif"]
      },
      borderRadius: {
        DEFAULT: "0px",
        sm: "0px",
        md: "0px",
        lg: "0px",
        xl: "0px",
        "2xl": "0px",
        "3xl": "0px",
        full: "9999px"
      },
      backgroundImage: {
        "neon-gradient": "linear-gradient(to right, #f425c0, #7b2cbf, #00f0ff)"
      }
    }
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/container-queries")
  ]
};
