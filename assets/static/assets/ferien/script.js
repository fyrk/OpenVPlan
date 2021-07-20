if (new Date() > new Date(2021, 6, 20, 3)) {
    const body = document.body
    const button = document.createElement("button")
    button.id = "ferien-btn"
    button.textContent = "🌻"
    button.classList.add("btn")
    button.addEventListener("click", e => {
        text.hidden = false
        document.documentElement.classList.add("ferien")
        fetch("/api/event", {
            method: "post",
            body: new URLSearchParams({type: "ferien", path: window.location.pathname})
        })
    })

    const text = document.createElement("div")
    text.id = "ferien-text"
    text.innerHTML = "☀️ Schöne Ferien!️<br>🌻"
    text.hidden = true

    body.appendChild(button)
    body.insertBefore(text, body.firstElementChild)
}
