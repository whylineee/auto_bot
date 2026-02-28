from aiogram.fsm.state import State, StatesGroup


class PostCreationStates(StatesGroup):
    selected_news = State()
    selected_style = State()
    generated_post = State()
