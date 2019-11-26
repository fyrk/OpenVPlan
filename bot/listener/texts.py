import logging
import random

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
    def __init__(self, data: dict):
        self._texts = {}
        for key, value in data.items():
            if type(value) == list:
                self._texts[key] = StringBotText("\n".join(value))
            elif type(value) == dict and value.get("_random", False):
                self._texts[key] = RandomBotText(value)
            else:
                self._texts[key] = AllBotText(value)

    def __getitem__(self, item):
        return self._texts[item].get()
