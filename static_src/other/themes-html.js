/*
 * OpenVPlan
 * Copyright (C) 2019-2021  Florian Rädiker
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

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
