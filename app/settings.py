#  OpenVPlan
#  Copyright (C) 2019-2021  Florian Rädiker
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import datetime
import json
import logging
import os.path
from pathlib import Path
import sys
import traceback
from typing import Optional, Union, Any, Dict, List, Tuple, TypedDict

from aiohttp import hdrs, http
from pydantic import BaseSettings, Field, validator
from pydantic.env_settings import SettingsSourceCallable, SettingsError


__version__ = "5.0"


class _CrawlerParserDefinition(TypedDict):
    name: str
    options: dict


class SubsPlanDefinition(TypedDict):
    crawler: _CrawlerParserDefinition
    parser: _CrawlerParserDefinition
    template_options: Dict[str, Any]


def config_settings(settings: BaseSettings):
    # merge EnvSettingsSource.__call__ and SecretsSettingsSource.__call__ to allow secrets with a type other than str
    """
    Build fields from files in "/config" directory.
    """
    secrets: Dict[str, Optional[str]] = {}

    secrets_path = Path("/config").expanduser()


    if not secrets_path.exists():
        warnings.warn(f'directory "{secrets_path}" does not exist')
        return secrets

    if not secrets_path.is_dir():
        raise SettingsError(f'secrets_dir must reference a directory, not a {path_type(secrets_path)}')

    for field in settings.__fields__.values():
        if filename := field.field_info.extra.get("filename"):
            path = secrets_path / filename
            if path.is_file():
                val = path.read_text().strip()
                if field.is_complex():
                    try:
                        val = settings.__config__.json_loads(val)  # type: ignore
                    except ValueError as e:
                        raise SettingsError(f'error parsing JSON for "{filename}"') from e
                secrets[field.alias] = val
            elif path.exists():
                warnings.warn(
                    f'attempted to load secret file "{path}" but found a {path_type(path)} instead.',
                    stacklevel=4,
                )

    return secrets


class Settings(BaseSettings):
    class Config:
        secrets_dir = "/config"

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> Tuple[SettingsSourceCallable, ...]:
            return (
                init_settings,
                config_settings,
                env_settings,
                file_secret_settings,
            )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.default_plan_id:
            object.__setattr__(self, "default_plan_id", self.substitution_plans["default"])
            del self.substitution_plans["default"]

        if hdrs.USER_AGENT not in self.request_headers:
            self.request_headers[hdrs.USER_AGENT] = f"Mozilla/5.0 (compatible; OpenVPlanBot/{__version__}; +https://{self.domain}) {http.SERVER_SOFTWARE}"
        
        object.__setattr__(self, "plausible",
                           dict(domain=self.plausible_domain, js=self.plausible_js,
                                endpoint=self.plausible_endpoint))
        
        object.__setattr__(self, "template_options",
                           dict(domain=self.domain, 
                                title=self.title, title_big=self.title_big, title_middle=self.title_middle, title_small=self.title_small,
                                html_head=self.html_head, footer_html=self.footer_html,
                                plans=[{"id": plan_id, "name": config["template_options"]["title"]} for plan_id, config in self.substitution_plans.items()]))

    debug: bool = False

    domain: str = ""

    title: str = "OpenVPlan"
    title_big: str = "OpenVPlan"
    title_middle: str = "OpenVPlan"
    title_small: str = "OpenVPlan"

    meta_description: str = ""
    meta_keywords: str = ""

    public_vapid_key: Optional[str] = None
    private_vapid_key: Optional[str] = None
    vapid_sub: Optional[str] = None
    webpush_content_encoding: str = "aes128gcm"
    send_welcome_push_message: bool = False

    plausible_domain: Optional[str] = None
    plausible_js: str = "https://plausible.io/js/plausible.outbound-links.js"
    plausible_endpoint: Optional[str] = None

    telegram_bot_logger_token: Optional[str] = None
    telegram_bot_logger_chat_id: Optional[Union[int, str]] = None
    telegram_bot_logger_use_fixed_width: bool = False
    telegram_bot_logger_level: int = logging.WARNING

    enable_ferien: bool = False
    ferien_start: datetime.datetime = None
    ferien_end: datetime.datetime = None

    request_headers: Dict[str, str] = {}
    request_timeout: float = 10

    additional_csp_directives: dict = {}

    headers_block_floc: bool = True


    # the following settings are preferably loaded through files in the /config directory because of their size

    default_plan_id: str = None  # can be set through substitution_plans.json with key "default"
    substitution_plans: Dict[str, Union[SubsPlanDefinition, str]] = Field(default_factory=dict, filename="substitution_plans.json")

    news: Optional[Dict[str, str]] = Field(None, filename="news.json")

    html_head: str = Field("", filename="head.html")

    about_html: str = Field("", filename="about.html")

    footer_html: str = Field("", filename="footer.html")

    additional_webmanifest_content: dict = Field(default_factory=dict, filename="additional.webmanifest")

    @validator("substitution_plans")
    def check_default_substitution_plan(cls, v, values):
        for key, value in v.items():
            if key != "default" and type(value) == str:
                raise ValueError(f'Invalid substitution plan definition for "{key}"')
        if values["default_plan_id"] and "default" in v:
            raise ValueError("default_plan_id is present in substitution_plans, but is already defined")
        if not values["default_plan_id"] and "default" not in v:
            print(v)
            raise ValueError("No default_plan_id is specified")
        return v
