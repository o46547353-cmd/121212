from typing import Tuple

PET_SHOP_ITEMS = {
    "food": {"name": "🍔 Вкусняшка", "price": 10, "effect": "health", "amount": 20},
    "toy": {"name": "🎾 Мячик", "price": 15, "effect": "happiness", "amount": 20},
    "hat": {"name": "👑 Корона", "price": 100, "effect": "cosmetic", "amount": 0},
    "glasses": {"name": "🕶️ Крутые очки", "price": 50, "effect": "cosmetic", "amount": 0}
}

def buy_pet_item(user: 'User', pet: 'Pet', item_id: str) -> Tuple[bool, str]:
    if item_id not in PET_SHOP_ITEMS:
        return False, "Предмет не найден."

    item = PET_SHOP_ITEMS[item_id]
    if user.coins < item["price"]:
        return False, "Недостаточно монет."

    user.coins -= item["price"]

    if item["effect"] == "health":
        pet.health = min(100, pet.health + item["amount"])
        msg = f"Питомец съел {item['name']}! Здоровье: {pet.health}%"
    elif item["effect"] == "happiness":
        pet.happiness = min(100, pet.happiness + item["amount"])
        msg = f"Питомец поиграл с {item['name']}! Счастье: {pet.happiness}%"
    else:
        # Cosmetic items
        inventory = pet.inventory or {}
        inventory[item_id] = item["name"]
        pet.inventory = inventory
        msg = f"Питомец надел {item['name']}! Выглядит стильно."

    return True, msg
