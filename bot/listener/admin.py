import datetime
import json
import logging
import math

from bot.db.connector import BaseConnection


class Admin:
    def __init__(self, db_connection: BaseConnection):
        self.connection = db_connection
        self.logger = logging.getLogger()

    def handle_command(self, text):
        try:
            parts = [a for a in text.split(" ") if a]
            if len(parts) == 0:
                result = "No command provided"
            elif parts[0] == "stats":
                result = self._stats(parts[1:])
            elif parts[0] == "log":
                result = self._log(parts[1:])
            elif parts[0] == "db":
                result = self._db(parts[1:])
            else:
                result = f"Unknown command '{parts[0]}'"
            if not result:
                result = "No data available"
            return result
        except Exception as e:
            logging.exception("Exception while processing admin command")
            return str(e)

    def _assert_arg_length(self, args, min_length, max_length=None):
        if max_length:
            if not (min_length <= len(args) <= max_length):
                raise TypeError(f"Expected {min_length} to {max_length} args, but got {len(args)}")
        else:
            if len(args) != min_length:
                raise TypeError(f"Expected {min_length} arguments, but got {len(args)}")

    def _parse_int(self, args, num):
        try:
            return int(args[num])
        except ValueError:
            raise ValueError(f"Expected argument {num} to be int, got '{args[num]}'")

    def _stats(self, args):
        with open("data/stats.json", "r") as f:
            stats = json.load(f)
        self._assert_arg_length(args, 1, math.inf)
        if args[0] == "statuses":
            self._assert_arg_length(args, 1)
            return ", ".join(stats["statuses"])
        if args[0] == "last-sites":
            self._assert_arg_length(args, 1)
            return ", ".join(stats["last-sites"])
        if args[0] == "requests":
            if len(args) == 1:
                time = datetime.datetime.now().strftime("%Y-%m-%d")
                if time not in stats["requests"]:
                    return f"No requests for {args[1]}"
                return "\n".join(user_agent + "\n" + "\n".join(f'  "{path}": {count}'
                                                               for path, count in requests.items())
                                 for user_agent, requests in stats["requests"][time].items())
            self._assert_arg_length(args, 2, math.inf)
            if args[1] == "bots":
                if len(args) >= 3:
                    self._assert_arg_length(args, 3)
                    count = self._parse_int(args, 2)
                else:
                    count = 0
                return "\n".join(" - ".join(r) for r in stats["bot_requests"][-count:])
            raise ValueError(f"Unknown argument '{args[1]}'")

    def _log(self, args):
        ARG_TO_FILENAME = {
            "sender": "log-bot-sender.txt",
            "listener": "log-bot-listener-webhook.txt",
            "listener-students": "log-bot-listener-students.txt",
            "listener-teachers": "log-bot-listener-teachers.txt",
            "website": "log-website.txt",
            "delete-old-msg": "log-delete-old-msg.txt"
        }
        self._assert_arg_length(args, 1, math.inf)
        if args[0] not in ARG_TO_FILENAME:
            raise ValueError(f"Unknown argument {args[0]}")
        if len(args) >= 2:
            self._assert_arg_length(args, 2)
            count = self._parse_int(args, 1)
        else:
            count = 16
        with open("logs/" + ARG_TO_FILENAME[args[0]], "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-count:])

    def _db(self, args):
        def delete(table_name, chat_id):
            self.connection.delete_chat(table_name, chat_id)
            return f"Successfully deleted chat '{chat_id}' from table '{table_name}'"

        COMMAND_TO_FUNC = {
            "chat": self.connection.get_chat,
            "new": self.connection.new_chat,
            "all": lambda table_name: "\n".join(repr(row) for row in self.connection.all_chats(table_name)),
            "delete": delete,
            "set": self.connection.update_chat
        }
        if args[0] == "cmd":
            self.connection.cursor.execute(" ".join(args))
            return
        if args[0] not in COMMAND_TO_FUNC:
            return f"Unknown command '{args[0]}'"
        return COMMAND_TO_FUNC[args[0]](*args[1:])
