"""
Example Custom Plugin for Nexa AI
-----------------------------------
Drop any Python file into the `plugins/` folder to automatically extend Nexa's abilities!

Each custom plugin must define:
1. PLUGIN_SCHEMA: A dict conforming to the Gemini function declaration schema.
2. run(**kwargs): A Python function returning a string or dict result.
"""

import random
import datetime

PLUGIN_SCHEMA = {
    "name": "random_picker_and_dice",
    "description": "Roll dice, flip a coin, or pick a random item from a comma-separated list.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action type: 'dice' (roll a 6-sided die), 'coin' (flip a coin), or 'pick' (choose from list)."
            },
            "options": {
                "type": "STRING",
                "description": "Comma-separated options to choose from if action is 'pick' (e.g. 'Pizza, Burger, Pasta')."
            }
        },
        "required": ["action"]
    }
}

def run(action: str = "dice", options: str = "") -> str:
    """Execute the random picker tool."""
    action = action.lower().strip()
    
    if action == "dice":
        roll = random.randint(1, 6)
        return f"🎲 Rolled a 6-sided die: **{roll}**"
    elif action == "coin":
        flip = random.choice(["Heads", "Tails"])
        return f"🪙 Flipped a coin: **{flip}**"
    elif action == "pick":
        if not options:
            return "Error: No options provided to pick from."
        choices = [opt.strip() for opt in options.split(",") if opt.strip()]
        if not choices:
            return "Error: No valid options found."
        chosen = random.choice(choices)
        return f"✨ Randomly selected: **{chosen}** (from choices: {', '.join(choices)})"
    else:
        return f"Unknown action '{action}'. Choose from 'dice', 'coin', or 'pick'."
