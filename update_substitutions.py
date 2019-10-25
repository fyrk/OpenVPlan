import gawvertretung
from logging_tool import create_logger

gawvertretung.logger = create_logger("update_substitutions")

gawvertretung.get_main_page({})
