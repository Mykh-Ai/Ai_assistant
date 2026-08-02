from bot.handlers.invoice import _explicit_reply_context


def _message(*, same_chat: bool = True, author_is_bot: bool = True, author_id: int = 999):
    chat = type('Chat', (), {'id': 77})()
    replied_chat = chat if same_chat else type('Chat', (), {'id': 88})()
    author = type('Author', (), {'id': author_id, 'is_bot': author_is_bot})()
    button = type('Button', (), {'text': 'Hlavné menu'})()
    markup = type('Markup', (), {'inline_keyboard': [[button]]})()
    replied = type(
        'Reply',
        (),
        {
            'chat': replied_chat,
            'from_user': author,
            'text': 'Aktívny business profil nie je dostupný alebo nie je vybraný.',
            'message_id': 42,
            'reply_markup': markup,
        },
    )()
    return type(
        'Message',
        (),
        {
            'chat': chat,
            'reply_to_message': replied,
            'bot': type('Bot', (), {'id': 999})(),
        },
    )()


def test_same_chat_reply_to_our_bot_is_included_independent_of_ttl() -> None:
    context = _explicit_reply_context(_message())
    assert context == {
        'replied_to_bot_text': 'Aktívny business profil nie je dostupný alebo nie je vybraný.',
        'replied_to_visible_button_labels': ['Hlavné menu'],
        'replied_to_message_id': 42,
        'replied_to_is_our_bot': True,
    }


def test_other_chat_user_or_other_bot_quote_is_excluded() -> None:
    assert _explicit_reply_context(_message(same_chat=False)) is None
    assert _explicit_reply_context(_message(author_is_bot=False)) is None
    assert _explicit_reply_context(_message(author_id=123)) is None
