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

/*// remove any tracking-related queries  // doesn't currently work since Plausible script is executed afterwards
const url = new URL(window.location);
let change = false;
for (let p of ["ref", "source", "utm_source", "utm_medium", "utm_campaign"]) {
    if (url.searchParams.has(p)) {
        change = true;
        url.searchParams.delete(p);
    }
}
if (change)
    history.replaceState(null, "", url)*/

// send features to Plausible
try {
    let theme = localStorage.getItem("theme");
    if (theme === "system-default" || !theme) {
        theme = "system-" + (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    }

    plausible("Features - " + planId, {
        props: {
            Selection: selection ? (selection.match(/,/g) || []).length + 1 : 0,
            Notifications: localStorage.getItem(planId + "-notification-state-pa") || "unknown",
            Theme: theme,
            Timetables: null,  // TODO
        }
    })
} catch (e) {
    console.error(e);
    reportError(e);
}

// CLICK TRACKING
// copied from https://plausible.io/docs/custom-event-goals

registerAnalyticsEvents(document.querySelectorAll("a[data-pa]"), handleLinkEvent);

// Handle button form events - those that have data-analytics
registerAnalyticsEvents(document.querySelectorAll("button[data-pa]"), handleFormEvent);

// start - added by me
registerAnalyticsEvents([document.getElementById("btn-selection-submit")], event => {
    event.target.setAttribute("data-pa",
        document.getElementById("selectionInput").value.trim() ?
            `"Select",{"${planId}":"Form"}` : `"Select",{"${planId}":"All (Form)"}`);
    handleFormEvent(event);
});
// end - added by me

/**
* Iterate Elements and add event listener
*
* @param {NodeList} elements - Array of elements
* @param {CallableFunction} callback
*/
function registerAnalyticsEvents(elements, callback) {
    for (let e of elements) {
        e.addEventListener("click", callback);
        e.addEventListener("auxclick", callback);
    }
}

/**
* Handle Link Events with plausible
* https://github.com/plausible/analytics/blob/e1bb4368460ebb3a0bb86151b143176797b686cc/tracker/src/plausible.js#L74
*
* @param {Event} event - click
*/
function handleLinkEvent(event) {
    let link = event.target;
    const middle = event.type === "auxclick" && event.which === 2;
    const click = event.type === "click";
    while (link && (typeof link.tagName == "undefined" || link.tagName.toLowerCase() !== "a" || !link.href)) {
        link = link.parentNode;
    }

    if (middle || click)
        registerEvent(link.getAttribute("data-pa"));

    // Delay navigation so that Plausible is notified of the click
    if (!link.target) {
        if (!(event.ctrlKey || event.metaKey || event.shiftKey) && click) {
            setTimeout(function () {
                location.href = link.href;
            }, 150);
            event.preventDefault();
        }
    }
}
/**
* Handle form button submit events with plausible
*
* @param {Event} event - click
*/
function handleFormEvent(event) {
    event.preventDefault();

    registerEvent(event.target.getAttribute("data-pa"));

    setTimeout(function () {
        event.target.form.submit();
    }, 150);
}
/**
* Parse data and call plausible
* Using data attribute in html eg. data-analytics='"Register", {"props":{"plan":"Starter"}}'
*
* @param {string} data - plausible event "Register", {"props":{"plan":"Starter"}}
*/
function registerEvent(data) {
    // break into array
    //let attributes = data.split(/,(.+)/);

    // Parse it to object
    //let events = [JSON.parse(attributes[0]), JSON.parse(attributes[1] || '{}')];

    //plausible(...events);

    // changed by me to:
    const d = data.split(",");
    plausible(JSON.parse(d[0]), d[1] ? {props: JSON.parse(d[1])} : null);
}
