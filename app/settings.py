import datetime
import logging
from typing import Optional, Union, Any, Dict

from aiohttp import hdrs, http
from pydantic import BaseSettings

__version__ = "5.0"


class Settings(BaseSettings):
    debug: bool = False
    static_path: str = "static"
    telegram_bot_logger_token: Optional[str] = None
    telegram_bot_logger_chat_id: Optional[Union[int, str]] = None
    telegram_bot_logger_use_fixed_width: bool = False
    telegram_bot_logger_level: int = logging.WARNING

    plausible_domain: Optional[str] = None
    plausible_js: str = "https://plausible.io/js/plausible.js"
    plausible_endpoint: Optional[str] = None
    plausible_embed_link: str = ""

    enable_ferien: bool = True
    ferien_start: datetime.datetime = None
    ferien_end: datetime.datetime = None

    public_vapid_key: Optional[str] = None
    private_vapid_key: Optional[str] = None
    vapid_sub: Optional[str] = None
    webpush_content_encoding: str = "aes128gcm"
    send_welcome_push_message: bool = False

    request_headers: dict = {
        hdrs.USER_AGENT: f"Mozilla/5.0 (compatible; GaWVertretungBot/{__version__}; "
                         f"+https://gawvertretung.florian-raediker.de) {http.SERVER_SOFTWARE}"
    }

    additional_csp_directives: dict = {}

    headers_block_floc: bool = True

    default_plan_id: Optional[str] = None

    substitution_plans: Dict[str, Dict[str, Dict[str, Any]]] = None

    about_html: str = ""

    _plausible = None

    @property
    def plausible(self):
        if not self._plausible:
            object.__setattr__(self, "_plausible",
                               dict(domain=self.plausible_domain, js=self.plausible_js,
                                    endpoint=self.plausible_endpoint, embed_link=self.plausible_embed_link))
        return self._plausible
