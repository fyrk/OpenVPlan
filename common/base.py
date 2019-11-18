
class BaseSelectionHandler:
    @staticmethod
    def parse(text):
        raise NotImplementedError
    
    @staticmethod
    def parse_db(text):
        raise NotImplementedError
    
    @staticmethod
    def write_db(selection):
        raise NotImplementedError
