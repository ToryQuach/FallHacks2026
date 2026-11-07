from menu import menu

config = menu()
if not config:
  print("User cancelled setup.")
  exit()

print(f"Starting session with goal: {config['goal']}")
print(f"Personality: {config['personality']}")
print(f"Check interval: {config['check_interval_seconds']}s")
print(f"Sprites directory: {config['sprite_folder']}")

# Pass config directly into your desktop pet / Gemini analysis loops