from typing import List, Union, Any


class _TelegramAPIObject:
    __required__ = []
    
    def __init__(self, data=None, **kwargs):
        if "result" in data:
            data = data["result"]
        if data:
            self.__dict__.update(data)
        else:
            self.__dict__.update(kwargs)
    
    def __getattr__(self, item):
        if item not in self.__required__ and item in self.__dict__["__annotations__"]:
            self.__dict__[item] = None
            return None
        raise AttributeError
    
    def __setattr__(self, key, value):
        if key in self.__dict__["__annotations__"]:
            self.__dict__[key] = value
        raise AttributeError
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k in self.__dict__["__annotations__"]}


class Update(_TelegramAPIObject):
    __required__ = ["update_id"]
    update_id: int
    message: "Message"
    edited_message: "Message"
    channel_post: "Message"
    edited_channel_post: "Message"
    inline_query: "InlineQuery"
    chosen_inline_result: "ChosenInlineResult"
    callback_query: "CallbackQuery"
    shipping_query: "ShippingQuery"
    pre_checkout_query: "PreCheckoutQuery"
    poll: "Poll"


class User(_TelegramAPIObject):
    __required__ = ["id", "is_bot", "first_name"]
    id: int
    is_bot: bool
    first_name: str
    last_name: str
    username: str
    language_code: str


class Chat(_TelegramAPIObject):
    __required__ = ["id", "type"]
    id: int
    type: str
    title: str
    username: str
    first_name: str
    last_name: str
    photo: "ChatPhoto"
    description: str
    invite_link: str
    pinned_message: "Message"
    permissions: "ChatPermissions"
    sticker_set_name: str
    can_set_sticker_set: bool


class Message(_TelegramAPIObject):
    __required__ = ["message_id", "date", "chat"]
    message_id: int
    date: int
    chat: "Chat"
    from_: "User"
    forward_from: "User"
    forward_from_chat: "Chat"
    forward_from_message_id: int
    forward_signature: str
    forward_sender_name: str
    forward_date: int
    reply_to_message: "Message"
    edit_date: int
    media_group_id: str
    author_signature: str
    text: str
    entities: List["MessageEntity"]
    caption_entities: List["MessageEntity"]
    audio: "Audio"
    document: "Document"
    animation: "Animation"
    game: "Game"
    photo: List["PhotoSize"]
    sticker: "Sticker"
    video: "Video"
    voice: "Voice"
    vodeo_node: "VideoNote"
    caption: str
    contact: "Contact"
    location: "Location"
    venue: "Venue"
    poll: "Poll"
    new_chat_members: List["User"]
    left_chat_member: "User"
    new_chat_title: str
    new_chat_photo: List["PhotoSize"]
    delete_chat_photo: True
    group_chat_created: True
    supergroup_chat_created: True
    channel_chat_created: True
    migrate_to_chat_id: int
    migrate_from_chat_id: int
    pinned_message: "Message"
    invoice: "Invoice"
    successful_payment: "SuccessfulPayment"
    connected_website: str
    passport_data: "PassportData"
    reply_markup: "InlineKeyboardMarkup"


class MessageEntity:
    __required__ = ["type", "offset", "length"]
    type: str
    offset: int
    length: int
    url: str
    user: "User"


class PhotoSize:
    __required__ = ["file_id", "width", "height"]
    file_id: str
    width: int
    height: int
    file_size: int


class Audio(_TelegramAPIObject):
    __required__ = ["file_id", "duration"]
    file_id: str
    duration: int
    performer: str
    title: str
    mime_type: str
    file_size: int
    thumb: "PhotoSize"


class Document(_TelegramAPIObject):
    __required__ = ["file_id"]
    file_id: str
    thumb: "PhotoSize"
    file_name: str
    mime_type: str
    file_size: int


class Video(_TelegramAPIObject):
    __required__ = ["file_id", "width", "height", "duration"]
    file_id: str
    width: int
    height: int
    duration: int
    thumb: "PhotoSize"
    mime_type: str
    file_size: int


class Animation(_TelegramAPIObject):
    __required__ = ["file_id", "width", "height", "duration"]
    file_id: str
    width: int
    height: int
    duration: int
    thumb: "PhotoSize"
    file_name: str
    mime_type: str
    file_size: int


class Voice(_TelegramAPIObject):
    __required__ = ["file_id", "duration"]
    file_id: str
    diration: int
    mime_type: str
    file_size: int


class VideoNote(_TelegramAPIObject):
    __required__ = ["file_id", "length", "duration"]
    file_id: str
    length: int
    duration: int
    thumb: "PhotoSize"
    file_size: int


class Contact(_TelegramAPIObject):
    __required__ = ["phone_number", "first_name"]
    phone_number: str
    first_name: str
    last_name: str
    user_id: int
    vcard: str


class Location(_TelegramAPIObject):
    __required__ = ["longitude", "latitude"]
    longitude: float
    latitude: float


class Venue(_TelegramAPIObject):
    __required__ = ["location", "title", "address"]
    location: "Location"
    title: str
    address: str
    foursquare_id: str
    foursquare_type: str


class PollOption(_TelegramAPIObject):
    __required__ = ["text", "voter_count"]
    text: str
    voter_count: int


class Poll(_TelegramAPIObject):
    __required__ = ["id", "question", "options", "is_closed"]
    id: str
    question: str
    options: List["PollOption"]
    is_closed: bool


class UserProfilePhotos(_TelegramAPIObject):
    __required__ = ["total_count", "photos"]
    total_count: int
    photos: List[List["PhotoSize"]]


class File(_TelegramAPIObject):
    __required__ = ["file_id"]
    file_id: str
    file_size: int
    file_path: str


class ReplyKeyboardMarkup(_TelegramAPIObject):
    __required__ = ["keyboard"]
    keyboard: List[List["KeyboardButton"]]
    resize_keyboard: bool
    one_time_keyboard: bool
    selective: bool


class KeyboardButton(_TelegramAPIObject):
    __required__ = ["text"]
    text: str
    request_contact: bool
    request_location: bool


class ReplyKeyboardRemove(_TelegramAPIObject):
    __required__ = ["remove_keyboard"]
    remove_keyboard: True
    selective: bool


class InlineKeyboardMarkup(_TelegramAPIObject):
    __required__ = ["inline_keyboard"]
    inline_keyboard: List[List["InlineKeyboardButton"]]


class InlineKeyboardButton(_TelegramAPIObject):
    __required__ = ["text"]
    text: str
    url: str
    login_url: "LoginUrl"
    callback_data: str
    switch_inline_query: str
    switch_inline_query_current_chat: str
    callback_game: "CallbackGame"
    pay: bool


class LoginUrl(_TelegramAPIObject):
    __required__ = ["url"]
    url: str
    forward_text: str
    bot_username: str
    request_write_access: str


class CallackQuery(_TelegramAPIObject):
    __required__ = ["id", "from_", "chat_instance"]
    id: str
    from_: "User"
    message: "Message"
    inline_message_id: str
    chat_instance: str
    data: str
    game_short_name: str


class ForceReply(_TelegramAPIObject):
    __required__ = ["force_reply"]
    force_reply: True
    selective: bool


class ChatPhoto(_TelegramAPIObject):
    __required__ = ["small_file_id", "big_file_id"]
    small_file_id: str
    big_file_id: str


class ChatMember(_TelegramAPIObject):
    __required__ = ["user", "status"]
    user: "User"
    status: str
    until_date: int
    can_be_edited: bool
    can_post_messages: bool
    can_edit_messages: bool
    can_delete_messages: bool
    can_restrict_members: bool
    can_promote_members: bool
    can_change_info: bool
    can_invite_users: bool
    can_pin_messages: bool
    is_member: bool
    can_send_messages: bool
    can_send_media_messages: bool
    can_send_polls: bool
    can_send_other_messages: bool
    can_add_web_page_previews: bool


class ChatPermissions(_TelegramAPIObject):
    __required__ = []
    can_send_messages: bool
    can_send_media_messages: bool
    can_send_polls: bool
    can_send_other_messages: bool
    can_add_web_page_previews: bool
    can_change_info: bool
    can_invite_users: bool
    can_pin_messages: bool


class ResponseParameters(_TelegramAPIObject):
    __required__ = []
    migrate_to_chat_id: int
    retry_after: int


class InputMedia(_TelegramAPIObject):
    __required__ = ["type", "media"]
    type: str
    media: str
    parse_mode: str
    caption: str


class InputMediaPhoto(InputMedia):
    type: str("photo")
    # media
    # parse_mode
    # caption


class InputMediaVideo(InputMedia):
    type: str("video")
    # media
    thumb: Union["InputFile", str]
    # caption
    # parse_mode
    width: int
    height: int
    duration: int
    supports_straming: bool


class InputMediaAnimation(InputMedia):
    type: str("animation")
    # media
    thumb: Union["InputFile", str]
    # caption
    # parse_mode
    width: int
    height: int
    duration: int


class InputMediaAudio(InputMedia):
    type: str("audio")
    # media
    thumb: Union["InputFile", str]
    # caption
    # parse_mode
    duration: int
    performer: str
    title: str


class InputMediaDocument(InputMedia):
    type: str("document")
    # media
    thumb: Union["InputFile", str]
    # caption
    # parse_mode


class InputFile(_TelegramAPIObject):
    data: Any


class WebhookInfo(_TelegramAPIObject):
    __required__ = ["url", "has_custom_certificate", "pending_update_count"]
    url: str
    has_custom_certificates: bool
    pending_update_count: int
    last_error_date: int
    last_error_message: str
    max_connections: int
    allowed_updated: List[str]
