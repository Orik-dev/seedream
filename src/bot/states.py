from aiogram.fsm.state import StatesGroup, State

class TopupStates(StatesGroup):
    choosing_amount = State()
    choosing_method = State()
    receipt_choice = State()
    waiting_email = State()

class GenStates(StatesGroup):
    selecting_orientation = State()  # 🆕 Новое состояние
    uploading_images = State()
    waiting_prompt = State()
    generating = State()
    final_menu = State()

class CreateStates(StatesGroup):
    waiting_prompt = State()
    generating = State()
    selecting_quality = State()
    selecting_aspect_ratio = State()
    final_menu = State()
    
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
class VoiceStates(StatesGroup):
    confirming_prompt = State()    