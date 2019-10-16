import asyncio
import traceback
from typing import List, Iterator, Iterable, Union

import aiohttp

from asynctelebot.types import *

API_URL = "https://api.telegram.org/bot{token}/{method}"

ParseModeStr = Union[str("html"), str("markdown")]
ReplyMarkup = Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply]
FileLocation = Union[InputFile, str]


class BotAPIException(Exception):
    pass


class Bot:
    def __init__(self, token):
        self._token = token
        self._session_ = None
        self.loop = asyncio.get_event_loop()
        self._running = False
        
        self._offset = 0
    
    def __del__(self):
        if self._session_:
            self._session_.close()
    
    @property
    def _session(self):
        if not self._session_ or self._session_.closed:
            self._session_ = aiohttp.ClientSession()
        return self._session_
    
    async def call_method(self, method, **params):
        print("call method", method)
        async with self._session.post(API_URL.format(token=self._token, method=method), data=params) as response:
            response_data = await response.json(encoding="utf-8")
            if response.status == 200 and response_data["ok"]:
                return response_data
            else:
                raise BotAPIException("Request {} with params {} failed: {} {}: {}".format(method, params,
                                                                                           response.status,
                                                                                           response.reason,
                                                                                           response_data))
    
    ###########
    # METHODS #
    ###########
    
    async def get_updates(self, limit: int = None, timeout: int = None,
                          allowed_updates: List[str] = None) -> Iterator[Update]:
        data = {}
        if limit is not None:
            data["limit"] = limit
        if timeout is not None:
            data["timeout"] = timeout
        if allowed_updates is not None:
            data["allowed_updates"] = allowed_updates
        data = await self.call_method("getUpdates", **data)
        return (Update(u) for u in data["result"])
    
    def set_webhook(self, url: str,
                    certificate: InputFile = None, max_connections: int = None,
                    allowed_updates: List[str] = None):
        data = {"url": url}
        if certificate is not None:
            data["certificate"] = certificate
        if max_connections is not None:
            data["max_connections"] = max_connections
        if allowed_updates is not None:
            data["allowed_updates"] = allowed_updates
        return self.call_method("setWebhook", **data)
    
    def delete_webhook(self):
        return self.call_method("deleteWebhook")
    
    async def get_webhook_info(self) -> WebhookInfo:
        return WebhookInfo(await self.call_method("getWebhookInfo"))
    
    async def get_me(self) -> User:
        return User(await self.call_method("getMe"))
    
    async def send_message(self, chat_id: Union[int, str], text: str,
                           parse_mode: ParseModeStr = None, disable_web_page_preview: bool = None,
                           disable_notification: bool = None, reply_to_message_id: int = None,
                           reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "text": text}
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        if disable_web_page_preview is not None:
            data["disable_web_page_preview"] = disable_web_page_preview
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendMessage", **data))
    
    async def forward_message(self, chat_id: Union[int, str], from_chat_id: Union[int, str], message_id: int,
                              disable_notification: bool = None) -> Message:
        data = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        return Message(await self.call_method("forwardMessage", **data))
    
    async def send_photo(self, chat_id: Union[int, str], photo: FileLocation,
                         caption: str = None, parse_mode: ParseModeStr = None, disable_notification: bool = None,
                         reply_to_message_id: int = None, reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "photo": photo if type(photo) == str else photo.to_dict()}
        if caption is not None:
            data["caption"] = caption
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendPhoto", **data))
    
    async def send_audio(self, chat_id: Union[int, str], audio: FileLocation,
                         caption: str = None, parse_mode: ParseModeStr = None, duration: int = None,
                         performer: str = None, title: str = None, thumb: FileLocation = None,
                         disable_notification: bool = None, reply_to_message_id: int = None,
                         reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "audio": audio if type(audio) == str else audio.to_dict()}
        if caption is not None:
            data["caption"] = caption
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        if duration is not None:
            data["duration"] = duration
        if performer is not None:
            data["performer"] = performer
        if title is not None:
            data["title"] = title
        if thumb is not None:
            data["thumb"] = thumb if type(thumb) == str else thumb.to_dict()
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendAudio", **data))
    
    async def send_document(self, chat_id: Union[int, str], document: FileLocation,
                            thumb: FileLocation = None, caption: str = None, parse_mode: ParseModeStr = None,
                            disable_notification: bool = None, reply_to_message_id: int = None,
                            reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "document": document if type(document) == str else document.to_dict()}
        if thumb is not None:
            data["thumb"] = thumb if type(thumb) == str else thumb.to_dict()
        if caption is not None:
            data["caption"] = caption
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendDocument", **data))
    
    async def send_video(self, chat_id: Union[int, str], video: FileLocation,
                         duration: int = None, width: int = None, height: int = None, thumb: FileLocation = None,
                         caption: str = None, parse_mode: ParseModeStr = None, supports_streaming: bool = None,
                         disable_notification: bool = None, reply_to_message_id: int = None,
                         reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "video": video if type(video) == str else video.to_dict()}
        if duration is not None:
            data["duration"] = duration
        if width is not None:
            data["width"] = width
        if height is not None:
            data["height"] = height
        if thumb is not None:
            data["thumb"] = thumb if type(thumb) == str else thumb.to_dict()
        if caption is not None:
            data["caption"] = caption
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        if supports_streaming is not None:
            data["supports_streaming"] = supports_streaming
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendVideo", **data))
    
    async def send_animation(self, chat_id: Union[int, str], animation: FileLocation,
                             duration: int = None, width: int = None, height: int = None, thumb: FileLocation = None,
                             caption: str = None, parse_mode: ParseModeStr = None, disable_notification: bool = None,
                             reply_to_message_id: int = None, reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "video": animation if type(animation) == str else animation.to_dict()}
        if duration is not None:
            data["duration"] = duration
        if width is not None:
            data["width"] = width
        if height is not None:
            data["height"] = height
        if thumb is not None:
            data["thumb"] = thumb if type(thumb) == str else thumb.to_dict()
        if caption is not None:
            data["caption"] = caption
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendAnimation", **data))
    
    async def send_voice(self, chat_id: Union[int, str], voice: FileLocation,
                        caption: str = None, parse_mode: ParseModeStr = None, duration: int = None,
                        disable_notification: bool = None, reply_to_message_id: int = None,
                        reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "voice": voice if type(voice) == str else voice.to_dict()}
        if caption is not None:
            data["caption"] = caption
        if parse_mode is not None:
            data["parse_mode"] = parse_mode
        if duration is not None:
            data["duration"] = duration
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendVoice", **data))
    
    async def send_video_note(self, chat_id: Union[int, str], video_note: FileLocation,
                              duration: int = None, length: int = None, thumb: FileLocation = None,
                              disable_notification: bool = None, reply_to_message_id: int = None,
                              reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "video_note": video_note if type(video_note) == str else video_note.to_dict()}
        if duration is not None:
            data["duration"] = duration
        if length is not None:
            data["length"] = length
        if thumb is not None:
            data["thumb"] = thumb if type(thumb) == str else thumb.to_dict()
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendVideoNote", **data))
    
    async def send_media_group(self, chat_id: Union[int, str], media: List[Union[InputMediaPhoto, InputMediaVideo]],
                               disable_notification: bool = None, reply_to_message_id: int = None) -> Message:
        data = {"chat_id": chat_id, "media": [m.to_dict() for m in media]}
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        return Message(await self.call_method("sendMediaGroup", **data))
    
    async def send_location(self, chat_id: Union[int, str], latitude: float, longitude: float,
                            live_period: int = None, disable_notification: bool = None, reply_to_message_id: int = None,
                            reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
        if live_period is not None:
            data["live_period"] = live_period
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup
        return Message(await self.call_method("sendLocation", **data))
    
    async def edit_message_live_location(self, latitude: float, longitude: float,
                                      chat_id: Union[int, str] = None, message_id: int = None,
                                      inline_message_id: str = None, reply_markup: InlineKeyboardMarkup = None) -> Message:
        data = {"latitude": latitude, "longitude": longitude}
        if inline_message_id is not None:
            if chat_id is not None or message_id is not None:
                raise ValueError("Pass either 'inline_message_id' or 'chat_id' and 'message_id'")
            data["inline_message_id"] = inline_message_id
        else:
            if chat_id is not None and message_id is not None:
                data["chat_id"] = chat_id
                data["message_id"] = message_id
            else:
                raise ValueError("Param 'inline_message_id' is None, expected 'chat_id' and 'message_id' to be not "
                                 "'None'")
        if reply_markup is not None:
            data["reply_markup"] = reply_markup
        return Message(await self.call_method("editMessageLiveLocation", **data))
    
    async def stop_message_live_location(self, chat_id: Union[int, str] = None, message_id: int = None,
                                         inline_message_id: str = None, reply_markup: InlineKeyboardMarkup = None) -> Message:
        data = {}
        if inline_message_id is not None:
            if chat_id is not None or message_id is not None:
                raise ValueError("Pass either 'inline_message_id' or 'chat_id' and 'message_id'")
            data["inline_message_id"] = inline_message_id
        else:
            if chat_id is not None and message_id is not None:
                data["chat_id"] = chat_id
                data["message_id"] = message_id
            else:
                raise ValueError("Param 'inline_message_id' is None, expected 'chat_id' and 'message_id' to be not "
                                 "'None'")
        if reply_markup is not None:
            data["reply_markup"] = reply_markup
        return Message(await self.call_method("stopMessageLiveLocation", **data))
    
    async def send_venue(self, chat_id: Union[int, str], latitude: float, longitude: float, title: str, address: str,
                         foursquare_id: str = None, foursquare_type: str = None, disable_notification: bool = None,
                         reply_to_message_id: int = None, reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude, "title": title, "address": address}
        if foursquare_id is not None:
            data["foursquare_id"] = foursquare_id
        if foursquare_type is not None:
            data["foursquare_type"] = foursquare_type
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendVenue", **data))
    
    async def send_contact(self, chat_id: Union[int, str], phone_number: str, first_name: str,
                           last_name: str = None, vcard: str = None, disable_notification: bool = None,
                           reply_to_message_id: int = None, reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "phone_number": phone_number, "first_name": first_name}
        if last_name is not None:
            data["last_name"] = last_name
        if vcard is not None:
            data["vcard"] = vcard
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendContact", **data))
    
    async def send_poll(self, chat_id: Union[int, str], question: str, options: List[str],
                        disable_notification: bool = None, reply_to_message_id: int = None,
                        reply_markup: ReplyMarkup = None) -> Message:
        data = {"chat_id": chat_id, "question": question, "options": options}
        if disable_notification is not None:
            data["disable_notification"] = disable_notification
        if reply_to_message_id is not None:
            data["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            data["reply_markup"] = reply_markup.to_dict()
        return Message(await self.call_method("sendPoll", **data))
    
    def send_chat_action(self, chat_id: Union[int, str], action: str):
        return self.call_method("sendChatAction", chat_id=chat_id, action=action)
    
    async def get_user_profile_photos(self, user_id: int,
                                      offset: int = None, limit: int = None) -> UserProfilePhotos:
        data = {"user_id": user_id}
        if offset is not None:
            data["offset"] = offset
        if limit is not None:
            data["limit"] = limit
        return UserProfilePhotos(await self.call_method("getUserProfilePhotos", **data))
    
    async def get_file(self, file_id: str):
        return File(await self.call_method("getFile", file_id=file_id))
    
    def kick_chat_member(self, chat_id: Union[int, str], user_id: int,
                               until_date: int = None):
        data = {"chat_id": chat_id, "user_id": user_id}
        if until_date is not None:
            data["until_date"] = until_date
        return self.call_method("kickChatMember", **data)
    
    def unban_chat_member(self, chat_id: Union[int, str], user_id: int):
        return self.call_method("unbanChatMember", chat_id=chat_id, user_id=user_id)
    
    def restrict_chat_member(self, chat_id: Union[int, str], user_id: int, permissions: ChatPermissions,
                             until_date: int = None):
        data = {"chat_id": chat_id, "user_id": user_id, "permissions": permissions.to_dict()}
        if until_date is not None:
            data["until_date"] = until_date
        return self.call_method("restrictChatMember", **data)

    ###########
    # POLLING #
    ###########
    
    def process_updates(self, updates: Iterable[Update]):
        for update in updates:
            if update["update_id"] > self._offset:
                self._offset = update["update_id"]
            print("UPDATE", update)
    
    async def _polling_loop(self, timeout, infinite):
        self._running = True
        try:
            while self._running:
                try:
                    self.process_updates(await self.get_updates(timeout=timeout))
                except Exception as e:
                    if not infinite:
                        raise e
                    else:
                        traceback.print_exc()
        except KeyboardInterrupt:
            self.stop_polling()
    
    def polling(self, timeout=20, infinite=False):
        self.loop.run_until_complete(self._polling_loop(timeout, infinite))
    
    def stop_polling(self):
        self._running = False
