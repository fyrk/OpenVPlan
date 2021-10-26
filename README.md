# OpenVPlan
OpenVPlan is a server that parses an Untis substitution plan and displays it properly on a modern website.

For an example, see [gaw-vertretung.de](https://gaw-vertretung.de).

# Features
 * Neatly display substitutions from Untis subst_???.htm plans ([example](https://gaw-verden.de/images/vertretung/klassen/subst_001.htm))
 * Groups (class, teacher etc.) can be selected
 * Send browser push notifications on new substitutions
 * Works offline
 * Installable as a [Progressive Web App](https://en.wikipedia.org/wiki/Progressive_web_application)
 * Users can provide timetables, and relevant substitutions will be highlighted. Timetables are stored in the browser and are never sent to the server.
 * Light and dark theme
 * Supports privacy-friendly web analytics with [Plausible](https://plausible.io)

# Usage
The server runs within a [Docker](https://docker.com) container. 

Unfortunately, images are not yet published to the [Docker Hub](https://hub.docker.com), so you'll have to build an image yourself.
Clone this repository, `cd` into `OpenVPlan` and run:
```
$ docker build --tag openvplan .
```

An example configuration for [Docker Compose](https://docs.docker.com/compose/) is provided in `docker-compose.prod.example.yml`. Start the server with the following command:
```
$ docker-compose -f docker-compose.prod.example.yml up -d
```

This will start OpenVPlan as well as nginx listening on localhost:80. For the nginx configuration, see `nginx-openvplan.conf`. Nginx passes requests to the OpenVPlan container and serves static files (provided by OpenVPlan through the `openvplan_static` volume). The website is now available at http://localhost.

Note that for most features to work, the site *must* be served over HTTPS. The nginx configuration should be changed accordingly (listen on port 443, redirect non-HTTPS traffic). (HTTP on localhost is usually treated as secure by browsers.)

## Configuration
Simple settings can be changed through environment variables in the docker-compose file.
More complex settings (e.g., the substitution plans to parse) are changed through files in the container's `/config` directory.

### Environment variables
The following environment variables are available. Some are already present in `docker-compose.prod.example.yml`.

#### General
| Name | Default | Description |
| ---- | ------- | ----------- |
| DEBUG  | 0 | Must be 0 in production. If 1, various development features are enabled, like serving static files directly. |
| DOMAIN | example.org | The website's domain, *without* the protocol or path |

#### HTML
| Name | Default | Description |
| ---- | ------- | ----------- |
| TITLE<br>TITLE_BIG<br>TITLE_MIDDLE<br>TITLE_SMALL | OpenVPlan | TITLE: used in `<title>`<br>TITLE_BIG: used in header for screen widths ≥768px<br>TITLE_MIDDLE: used in header for screen widths ≥380px and <768px<br>TITLE_SMALL: used in header for screen widths <380px |
| META_DESCRIPTION | "" | Text for `<meta name="description" content="...">` |
| META_KEYWORDS | "" | Text for `<meta name="keywords" content="...">` |

#### Push Notifications
| Name | Default | Description |
| ---- | ------- | ----------- |
| PUBLIC_VAPID_KEY<br>PRIVATE_VAPID_KEY<br>VAPID_SUB | null | These settings are required for push notifications. For information on how to generate PUBLIC_VAPID_KEY and PRIVATE_VAPID_KEY, see for example [here](https://stackoverflow.com/a/62872791/13365167). VAPID_SUB is an email address in the form `mailto:hello@example.org`. |
| WEBPUSH_CONTENT_ENCODING | aes128gcm | Content encoding to use for push notifications. See [pywebpush's documentation](https://github.com/web-push-libs/pywebpush#sending-data-using-webpush-one-call). |
| SEND_WELCOME_PUSH_MESSAGE | 0 | Wheather to send a push message when a user subscribed. |

#### Plausible
| Name | Default | Description |
| ---- | ------- | ----------- |
| PLAUSIBLE_DOMAIN | null | The domain you specified in Plausible ([`data-domain` attribute on the `<script>` tag](https://plausible.io/docs/plausible-script)). |
| PLAUSIBLE_JS | https://plausible\.io/js/plausible.outbound-links.js | The tracking script to use. Useful if you are self-hosting Plausible or if you want to use different [script extensions](https://plausible.io/docs/script-extensions). |
| PLAUSIBLE_ENDPOINT | null | Change the API endpoint. (`data-api` attribute on the `<script>` tag). |

#### Telegram Bot Logger
The server can send you messages whenever an error is logged via a Telegram Bot.

| Name | Default | Description |
| ---- | ------- | ----------- |
| TELEGRAM_BOT_LOGGER_TOKEN | null | The Bot token. |
| TELEGRAM_BOT_LOGGER_CHAT_ID | null | Chat id to send messages to. |
| TELEGRAM_BOT_LOGGER_USE_FIXED_WIDTH | 0 | 1 if a fixed-width font should be used in messages. |
| TELEGRAM_BOT_LOGGER_LEVEL | 30 | Minimum level (Python's logging module) for messages. The default is `logging.WARNING` (30). |

### Configuration files
Configuration files are placed in the container's `/config` directory via volumes. Example configuration files are provided in this repository's `config/` directory. These files are already placed in the container's `/config` directory in `docker-compose.prod.example.yml`.

#### substitution_plans.json
This is where all substitution plans are defined. For an example, see config/substitution_plans.json.

The following is a commented excerpt (note that comments are not supported in the real file).

```json5
{
  // the plan id of the default plan:
  "default": "students",

  // configuration for a plan with id 'students':
  "students": {

    // How to parse the original plan. Currently, there is only one crawler (named "multipage") and one parser (named "untis").
    "crawler": {
      "name": "multipage",
      "options": {
        // the URL of the original plan, with '{:03}' instead of the three digits:
        "url": "https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm"
      }
    },
    "parser": {
      "name": "untis",
      "options": {
        // encoding of the subst_???.htm files:
        "encoding": "iso-8859-1"
      }
    },

    "template_options": {
      "title": "Schüler*innen",
      "description": "Schüler*innen-Vertretungsplan für das Gymnasium am Wall Verden",
      "keywords": "Gymnasium am Wall, GaW Verden, Vertretung, Vertretungsplan, Schule, Schüler, Klassen, Schüler*innen",
      // wheather to show the timetables section on the website:
      "supports_timetables": true,
      "table_headers": [
        "Kla",
        "Lehrer",
        "Vertr",
        "Stunde",
        "Fach",
        "Raum",
        "Vertr von",
        "Hinweis"
      ],
      "original_data_link": "https://gaw-verden.de/images/vertretung/klassen/subst_001.htm",
      "texts": {
        "select_heading": "Klassen auswählen",
        "select_text": "Einzelne Klassen können mit dem Lesezeichen-Symbol ausgewählt werden.<br>Mehrere Klassen oder Klassen, für die es gerade keine Vertretungen gibt, können hier ausgewählt werden:",
        "selection_help_text": "Mehrere Klassen durch Kommata trennen",
        "selection_all": "Alle Klassen",
        "notifications_info_all": "Du wirst für alle Klassen benachrichtigt. Wähle Klassen aus, um nur für bestimmte Klassen benachrichtigt zu werden."
      }
    }
  }
}
```

#### head.html
Add HTML to the website's `<head>`.

#### footer.html
Add HTML to the website's footer.

#### about.html
HTML to display on the about page (/about, "Impressum & Datenschutzerklärung").

#### news.json
Contains news to display on the website. For example:
````json
{
    "some-unique-news-id": "Hey, some important news: blah blah blah"
}
````

If news should be displayed on only one substitution plan, start the id with `<plan-id>:`. For example:
````json
{
    "students:some-unique-news-id": "Hey, this will only be visible on the student's substitution plan!"
}
````

#### additional.webmanifest
To make the website installable as a PWA, each substitution plan has a [Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest) located at `example.org/<plan-id>/app.webmanifest`.
The `additional.webmanifest` file may contain additional JSON to include in the manifest.


# License
```
OpenVPlan
Copyright (C) 2019-2021  Florian Rädiker

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
DO NOT modify the attribution part in the footer, leave it as it is.
