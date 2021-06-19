// The contents of themes-html.min.js are copied to _base.html.
// This file contains the original code so that Closure Compiler can minify it.

// Previously, "theme" was named "dark-theme" (Why? I don't know.)
const old = localStorage.getItem("dark-theme");
if(old != null) {
    localStorage.setItem("theme", old);
    localStorage.removeItem("dark-theme");
}

switch (localStorage.getItem("theme")) {
    case "light":
        document.documentElement.classList.add("light");
        break;
    case "dark":
        document.documentElement.classList.add("dark");
}
