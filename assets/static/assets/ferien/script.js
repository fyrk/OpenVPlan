/*
 * GaW-Vertretungsplan
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

const body = document.body
const button = document.createElement("button")
button.id = "ferien-btn"
button.textContent = "🌻"
button.classList.add("btn")
button.addEventListener("click", e => {
    text.hidden = false
    document.documentElement.classList.add("ferien")
    plausible("Ferien")
})

const text = document.createElement("div")
text.id = "ferien-text"
text.innerHTML = "☀️ Schöne Ferien!️<br>🌻"
text.hidden = true

body.appendChild(button)
body.insertBefore(text, body.firstElementChild)
