"""Festival calendar (wiki: Festivals). On these days shops/homes are locked (except Night Market etc.),
time stops inside the festival, and leaving returns you to the Farm at 22:00."""
FESTIVALS = {
    ("spring", 13): ("Egg Festival", "Town", 900, 1400),       # Strawberry Seeds 100g at booth
    ("spring", 24): ("Flower Dance", "Forest", 900, 1400),     # Daffodil/Dandelion at booth
    ("summer", 11): ("Luau", "Beach", 900, 1400),
    ("summer", 28): ("Dance of the Moonlight Jellies", "Beach", 2200, 2350),
    ("fall", 16): ("Stardew Valley Fair", "Town", 900, 1500),
    ("fall", 27): ("Spirit's Eve", "Town", 2200, 2350),
    ("winter", 8): ("Festival of Ice", "Forest", 900, 1400),
    ("winter", 25): ("Feast of the Winter Star", "Town", 900, 1400),
}
def today(season, day):
    return FESTIVALS.get((season, day))
