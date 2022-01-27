from abc import ABC, abstractmethod
import dataclasses
import datetime
import random
from typing import List, Union


@dataclasses.dataclass(frozen=True)
class _BaseNews(ABC):
    plan_id: str
    news_id: str
    _htmls: List[str]
    type: str = dataclasses.field(init=False)

    def get_html(self):
        return random.choice(self._htmls)


@dataclasses.dataclass(frozen=True)
class GeneralNews(_BaseNews):
    is_dismissable: bool = True
    type: str = dataclasses.field(default="general", init=False)


@dataclasses.dataclass(frozen=True)
class DayNews(_BaseNews):
    date: datetime.date
    type: str = dataclasses.field(default="day", init=False)


def news_from_setting(news_id: str, news_setting) -> _BaseNews:
    def get_htmls(setting):
        if type(setting) is str:
            return [setting]
        assert type(setting) is list
        return setting
    
    if ":" in news_id:
        plan_id = news_id.split(":", 1)[0]
    else:
        plan_id = "*"

    if type(news_setting) is str or type(news_setting) is list:
        return GeneralNews(plan_id, news_id, get_htmls(news_setting))
    if news_setting.date:
        return DayNews(plan_id, news_id, get_htmls(news_setting.html), news_setting.date)
    return GeneralNews(plan_id, news_id, get_htmls(news_setting.html), news_setting.dismissable)
