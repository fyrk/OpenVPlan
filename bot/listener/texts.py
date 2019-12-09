import logging
import random
import re

random.seed()

logger = logging.getLogger()


class BaseBotText:
    def get(self):
        raise NotImplementedError


class AllBotText:
    def __init__(self, content):
        self.content = content

    def get(self):
        return self.content


class StringBotText(BaseBotText):
    def __init__(self, text):
        self.text = text

    def get(self):
        return self.text


class RandomBotText(BaseBotText):
    def __init__(self, data: dict):
        self.choices = []
        self.weights = []
        for choice, weight in data.items():
            if choice != "_random":
                self.choices.append(choice)
                self.weights.append(weight)

    def get(self):
        return random.choices(self.choices, self.weights)[0]


class BotTexts:
    def __init__(self, data: dict, type_: str):
        self._texts_unknown = [(re.compile(e["text"], re.IGNORECASE | re.MULTILINE),
                                self._parse_bot_text(e["response"])) for e in data["unknown"]]
        texts = data["common"]
        texts.update(data[type_])
        self._texts = {key: self._parse_bot_text(value) for key, value in texts.items()}

    def _parse_bot_text(self, value):
        if type(value) == list:
            return StringBotText("\n".join(value))
        elif type(value) == dict and value.get("_random", False):
            return RandomBotText(value)
        else:
            return AllBotText(value)

    def get_response_for_unknown(self, text):
        for regex, response in self._texts_unknown:
            if regex.fullmatch(text):
                return response.get()
        return "..."

    def __getitem__(self, item):
        return self._texts[item].get()
