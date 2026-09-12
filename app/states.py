from aiogram.fsm.state import State, StatesGroup
class MovieAddStates(StatesGroup):
    waiting_name=State()
    waiting_genre=State()
    waiting_country=State()
    waiting_year=State()
    waiting_description=State()
    confirm=State()

class SearchStates(StatesGroup):
    waiting_query=State()

class BanStates(StatesGroup):
    waiting_user=State()
    waiting_reason=State()

class BroadcastStates(StatesGroup):
    waiting_message=State()
    waiting_schedule=State()
