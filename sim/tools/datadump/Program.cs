using System; using System.IO; using System.Collections.Generic; using Microsoft.Xna.Framework.Content; using Newtonsoft.Json;
using StardewValley.GameData.Crops; using StardewValley.GameData.Objects; using StardewValley.GameData.Shops;
using StardewValley.GameData.Locations; using StardewValley.GameData.Machines; using StardewValley.GameData.Buildings;
using StardewValley.GameData.FarmAnimals; using StardewValley.GameData.LocationContexts; using StardewValley.GameData.FruitTrees;
using StardewValley.GameData.Tools; using StardewValley.GameData.Weapons; using StardewValley.GameData.BigCraftables; using StardewValley.GameData.GarbageCans; using StardewValley.GameData.SpecialOrders; using StardewValley.GameData.Museum; using StardewValley.GameData;
class SP : IServiceProvider { public object GetService(Type t) => null; }
class P {
  static ContentManager cm; static string outDir;
  static void D<T>(string asset) {
    try { var v = cm.Load<T>(asset);
      var s = JsonConvert.SerializeObject(v, Formatting.Indented, new JsonSerializerSettings{ReferenceLoopHandling=ReferenceLoopHandling.Ignore, NullValueHandling=NullValueHandling.Ignore, DefaultValueHandling=DefaultValueHandling.Ignore});
      var f = Path.Combine(outDir, asset.Replace("/", "_") + ".json"); File.WriteAllText(f, s); Console.WriteLine($"ok {asset} {s.Length}");
    } catch (Exception e) { Console.WriteLine($"FAIL {asset}: {e.GetType().Name} {e.Message}"); }
  }
  static void Main(string[] a) {
    cm = new ContentManager(new SP(), a[0]); outDir = a[1]; Directory.CreateDirectory(outDir);
    D<Dictionary<string, CropData>>("Data/Crops");
    D<Dictionary<string, ObjectData>>("Data/Objects");
    D<Dictionary<string, BigCraftableData>>("Data/BigCraftables");
    D<Dictionary<string, ShopData>>("Data/Shops");
    D<Dictionary<string, LocationData>>("Data/Locations");
    D<Dictionary<string, MachineData>>("Data/Machines");
    D<Dictionary<string, BuildingData>>("Data/Buildings");
    D<Dictionary<string, FarmAnimalData>>("Data/FarmAnimals");
    D<Dictionary<string, LocationContextData>>("Data/LocationContexts");
    D<Dictionary<string, FruitTreeData>>("Data/FruitTrees");
    D<Dictionary<string, ToolData>>("Data/Tools");
    D<Dictionary<string, WeaponData>>("Data/Weapons");
    D<GarbageCanData>("Data/GarbageCans");
    D<Dictionary<string, SpecialOrderData>>("Data/SpecialOrders");
    D<Dictionary<string, MuseumRewards>>("Data/MuseumRewards");
    D<List<TriggerActionData>>("Data/TriggerActions");
    foreach (var s in new[]{"Data/mail","Data/MonsterSlayerQuests","Data/Events/AbandonedJojaMart","Data/Events/AnimalShop","Data/Events/ArchaeologyHouse","Data/Events/Backwoods","Data/Events/Beach","Data/Events/BusStop","Data/Events/CommunityCenter","Data/Events/FarmHouse","Data/Events/Farm","Data/Events/FishShop","Data/Events/Forest","Data/Events/HaleyHouse","Data/Events/Hospital","Data/Events/JoshHouse","Data/Events/LeahHouse","Data/Events/ManorHouse","Data/Events/Mine","Data/Events/Mountain","Data/Events/Railroad","Data/Events/Saloon","Data/Events/SamHouse","Data/Events/ScienceHouse","Data/Events/SeedShop","Data/Events/Sewer","Data/Events/Town","Data/Events/Trailer","Data/Events/WizardHouse","Data/Events/Woods","Data/Events/Tent","Data/Events/ElliottHouse","Data/Events/SebastianRoom","Data/Events/HarveyRoom","Data/Events/SandyHouse"})
      D<Dictionary<string, string>>(s);
    foreach (var s in new[]{"Data/Fish","Data/Bundles","Data/CraftingRecipes","Data/CookingRecipes","Data/Festivals/FestivalDates","Data/Mail","Data/Quests","Data/SecretNotes","Data/NPCGiftTastes","Data/Monsters","Data/TV/CookingChannel","Data/ClothingInformation"})
      D<Dictionary<string, string>>(s);
  }
}
