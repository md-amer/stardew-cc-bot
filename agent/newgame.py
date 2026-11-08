"""Create the bot's fresh save from the title screen: farmer "Claude", farm "Claude", standard farm, skip intro.
The mod only accepts input for this farmer/farm name (save guard), so the names are fixed.
Advanced option: YearOneCompletable (guarantees a Red Cabbage source in Year 1, a vanilla checkbox)."""
import time, sv

def _wait_menu(name, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        try:
            if sv.widgets().get("menu") == name: return True
        except Exception: pass
        time.sleep(0.5)
    raise TimeoutError(f"menu {name} did not open")

def _type_into(field, text):
    sv.click_widget(field=field)
    time.sleep(0.3)
    sv.call("type", text=text)
    time.sleep(0.3)

def main():
    for _ in range(90):
        try:
            if sv.state().get("title"): break
        except Exception: pass
        time.sleep(1)
    time.sleep(4)                        # the title ignores clicks until the logo settles
    sv.call("tap", key="Escape")         # skip the logo animation if still running
    time.sleep(2)
    for _ in range(10):
        try:
            sv.click_widget(field="buttons", name="New"); break
        except LookupError:
            time.sleep(1)
    _wait_menu("CharacterCustomization")
    time.sleep(1.5)
    _type_into("nameBoxCC", "Claude")
    _type_into("farmnameBoxCC", "Claude")
    _type_into("favThingBoxCC", "Junimos")
    print(sv.call("newgame_option", key="YearOneCompletable", value=True))
    sv.click_widget(field="skipIntroButton")
    time.sleep(0.5)
    sv.click_widget(field="okButton")
    s = sv.wait(lambda s: s.get("world_ready"), timeout=120, every=1)
    print("new game started:", s.get("season"), s.get("day"), s.get("year"))

if __name__ == "__main__":
    main()
