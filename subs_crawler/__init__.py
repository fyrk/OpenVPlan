from subs_crawler.crawlers.dsbmobile import DsbmobileSubstitutionCrawler
from subs_crawler.crawlers.multipage import MultiPageSubstitutionCrawler
from subs_crawler.parsers.untis import UntisSubstitutionParser

__all__ = ["CRAWLERS", "PARSERS"]

CRAWLERS = {
    "multipage": MultiPageSubstitutionCrawler,
    "dsbmobile": DsbmobileSubstitutionCrawler
}

PARSERS = {
    "untis": UntisSubstitutionParser
}
