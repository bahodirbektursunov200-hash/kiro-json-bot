from aiogram.fsm.state import State, StatesGroup

class SellStates(StatesGroup):
    waiting_json = State()

class WithdrawStates(StatesGroup):
    waiting_amount = State()
    waiting_method = State()
    waiting_card = State()
    waiting_recipient = State()

class CardStates(StatesGroup):
    waiting_number = State()
    waiting_name = State()

class AdminStates(StatesGroup):
    reject_json = State()
    reject_withdrawal = State()
    add_plan_name = State()
    add_plan_price = State()
    edit_plan_price = State()
    add_payment_name = State()
    add_payment_details = State()
    add_payment_note = State()
    edit_payment_details = State()
    edit_payment_note = State()
    set_value = State()
    balance_user = State()
    balance_amount = State()
    balance_note = State()
