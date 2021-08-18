const d = new Date()
if (d > new Date(2021, 6, 20, 3) && d < new Date(2021, 9, 2, 0, 0)) {
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
}
