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

document.getElementById("themes-block").hidden = false;

const html = document.documentElement;
const systemDefaultRadio = document.getElementById("themes-system-default");
const lightRadio = document.getElementById("themes-light");
const darkRadio = document.getElementById("themes-dark");

function applyThemeSetting(setting) {
    localStorage.setItem("theme", setting);
    switch (setting) {
        case "system-default":
            html.classList.remove("light", "dark");
            break;
        case "light":
            html.classList.add("light");
            html.classList.remove("dark");
            break;
        case "dark":
            html.classList.add("dark");
            html.classList.remove("light");
            break;
    }
}

let theme = localStorage.getItem("theme");

switch (theme) {
    case "light":
        lightRadio.checked = true;
        break;
    case "dark":
        darkRadio.checked = true;
}
systemDefaultRadio.addEventListener("change", () => applyThemeSetting("system-default"));
lightRadio.addEventListener("change", () => applyThemeSetting("light"));
darkRadio.addEventListener("change", () => applyThemeSetting("dark"));
