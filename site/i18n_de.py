"""German text for the website's data pages (site/data_pages.py T()): English text -> German.

Keys are the exact English text, placeholders and all; a translation keeps every %s and %d in the same
order (Python's % can't reorder them) and every %% as %%. Words the addon uses keep the addon's German
(GoldScout/Locale_deDE.lua: Gebiet, Stufe, Fischschwarm, hoch/gut/mittel/niedrig...), and players are
"du", as in the addon. tests/test_site.py fails if a German page looks up text that isn't here.
"""
# The /drop-rates page (data_pages.RATES_BODY), in German.
RATES_BODY = """<h1>So funktionieren die Dropraten von GoldScout</h1>
<p class=summary>Jede Zahl auf dieser Seite stammt von GoldScout-Spielern, die in WoW Forever looten. Nichts ist von Wowhead oder einer anderen Datenbank kopiert.</p>
<h2>Chance</h2>
<p>Die Chance auf einen Gegenstand ist, bei wie vielen Kills er gedroppt ist, geteilt durch die erfassten Kills. Ein Gegner mit 200 erfassten Kills, der einen Gegenstand 50-mal gedroppt hat, zeigt 25%%. Durchschnittlicher Stapel ist, wie viele davon pro Drop kamen. Beim Taschendiebstahl gilt die Chance pro Taschendiebstahl statt pro Kill.</p>
<p>Neben jeder Chance steht der Bereich, in dem die echte Chance mit 95%% Wahrscheinlichkeit liegt, je nach Zahl der Kills dahinter: 25%% aus 200 Kills ist 20&ndash;31%%, aus 20 Kills 11&ndash;47%%. Droppt ein Gegenstand bei mehreren Gegnern, werden sie nach dem unteren Ende dieses Bereichs sortiert, damit ein paar glückliche Kills keinen Gegner überholen, den Hunderte Kills festgenagelt haben.</p>
<p>Alles wird in WoW Forever gezählt. Keine Classic-Era-Zahlen sind eingemischt, die Dropraten von Forever zeigen sich also so, wie sie sind.</p>
<h2>Verlässlichkeit</h2>
<p>Je mehr Kills erfasst sind, desto näher liegt die Chance an der echten. Jeder Gegner zeigt, wie sicher die Zahlen sind:</p>
<ul class=ticks>%s</ul>
<p>Seiten gibt es nur für Gegner mit mindestens %d erfassten Kills. Im Spiel bewertet GoldScout Farmen bei Gegnern mit wenigen Kills vorsichtig, damit eine Glückssträhne keinen Gegner nach oben bringt.</p>
<h2>Damit die Daten ehrlich bleiben</h2>
<ul class=ticks>
<li>Pro Gegner zählen höchstens %s Kills eines einzelnen Spielers, damit kein Spieler allein die Zahlen eines Gegners bestimmt.</li>
<li>Jeder Upload wird geprüft, und ungewöhnliche Dropraten werden geprüft, bevor sie genutzt werden.</li>
<li>Kürschnern, Bergbau und Kräuterkunde an einer Leiche zählen nicht als Kill. Kills, bei denen die Leiche keine Beute hatte, schon.</li>
<li>Graue Gegenstände sind Händlerschrott und werden nicht gezeigt. Ausrüstung, Rezepte und Edelsteine sind seltene Weltdrops und stehen unter den anderen Drops.</li>
</ul>
<h2>Preise und Gold pro Kill</h2>
<p>Preise sind der niedrigste Sofortkaufpreis im Auktionshaus für die Realm-Art und Fraktion, die du wählst, aus Blizzards Auktionsdaten, etwa stündlich aktualisiert. Gold pro Kill zählt für jedes Handwerksmaterial Chance mal durchschnittlicher Stapel mal Preis zusammen. Ausrüstung, Rezepte und Edelsteine (ihre Preise schwanken zu stark) und die Dauer eines Kills sind nicht eingerechnet.</p>
<p>Das GoldScout-Addon macht daraus Gold pro Stunde für deinen Charakter und nutzt deine eigenen Auktionshaus-Scans, wenn sie neuer sind.</p>
<p class=small>%s</p>
"""

DE = {
    # -- words ----------------------------------------------------------------
    "Mob": "Gegner",
    "Mobs": "Gegner",
    "Item": "Gegenstand",
    "Zone": "Gebiet",
    "Level": "Stufe",
    "Levels": "Stufen",
    "Home": "Startseite",
    "Goal": "Ziel",
    "Next": "Nächstes",
    "Solid": "Verlässlich",
    "Community goals": "Gemeinschaftsziele",
    "Players sharing data": "Spieler, die Daten teilen",
    "Kills recorded": "Erfasste Kills",
    "Mobs with solid drop rates (%d+ kills)": "Gegner mit verlässlichen Dropraten (%d+ Kills)",
    "%s of %s": "%s von %s",
    "<b>%s</b> of %s": "<b>%s</b> von %s",
    "<b class=done>%s</b> of %s": "<b class=done>%s</b> von %s",
    "%d day left": "noch %d Tag",
    "%d days left": "noch %d Tage",
    "today": "heute",
    "Goals for everyone sharing data, by %s (%s). Every player who adds the companion and every kill moves them.":
        "Ziele für alle, die Daten teilen, bis zum %s (%s). Jeder Spieler, der GoldScout Companion dazunimmt, "
        "und jeder Kill bringt sie näher.",
    "The goals for %s, and how far everyone got.": "Die Ziele für den %s und wie weit alle gekommen sind.",
    "Every goal for %s reached. Thank you, everyone who shares!":
        "Alle Ziele für den %s erreicht. Danke an alle, die teilen!",
    "Price": "Preis",
    "Kills": "Kills",
    "kills": "Kills",
    "Catch": "Fang",
    "Catches": "Fänge",
    "catches": "Fänge",
    "Pickpockets": "Taschendiebstähle",
    "pickpockets": "Taschendiebstähle",
    "Where": "Wo",
    "Chance": "Chance",
    "Reagent": "Material",
    "Recorded": "Erfasst",
    "Fishing": "Angeln",
    "low": "niedrig",
    "fair": "mittel",
    "good": "gut",
    "high": "hoch",
    " and ": " und ",
    "none yet": "noch keine",
    "nobody yet": "noch niemand",
    "fished up": "geangelt",
    "Complete": "Geschafft",
    "Open water": "Offenes Wasser",
    "Fishing pool": "Fischschwarm",
    "Fishing pool %d": "Fischschwarm %d",
    "Item %d": "Gegenstand %d",
    "Mob %d": "Gegner %d",
    "level %s": "Stufe %s",
    "Level %s": "Stufe %s",
    "Levels %d-%d": "Stufe %d-%d",
    "levels %d-%d": "Stufe %d-%d",
    " level %d": " der Stufe %d",
    " level %d-%d": " der Stufe %d-%d",
    "%d mob": "%d Gegner",
    "%d mobs": "%d Gegner",
    "%d source": "%d Quelle",
    "%d sources": "%d Quellen",
    "%d+ kills": "%d+ Kills",
    "Crafting reagent": "Handwerksmaterial",
    "Rare drop": "Seltener Drop",
    "a crafting reagent": "ein Handwerksmaterial",
    "a rare world drop": "ein seltener Weltdrop",
    "an item": "ein Gegenstand",
    "No German name recorded yet": "Noch kein deutscher Name erfasst",

    # -- headings and table heads ---------------------------------------------
    "By zone": "Nach Gebiet",
    "By level": "Nach Stufe",
    "Zone goal": "Gebietsziel",
    "Zone goals": "Gebietsziele",
    "Avg. stack": "Ø Stapel",
    "Other drops": "Andere Drops",
    "Best source": "Beste Quelle",
    "Dropped by": "Gedroppt von",
    "Pickpocketed from": "Gestohlen von",
    "Other levels": "Andere Stufen",
    "Almost there": "Fast geschafft",
    "Lowest skill": "Niedrigste Fertigkeit",
    "Best catches": "Beste Fänge",
    "Pickpocketing": "Taschendiebstahl",
    "Per kill": "Pro Kill",
    "Per catch": "Pro Fang",
    "Per pickpocket": "Pro Diebstahl",
    "Gold per hour": "Gold pro Stunde",
    "Gold per kill": "Gold pro Kill",
    "Gold per catch": "Gold pro Fang",
    "Gold per pickpocket": "Gold pro Diebstahl",
    "Where it drops": "Wo es droppt",
    "Farms by level": "Farmen nach Stufe",
    "Crafting reagents": "Handwerksmaterialien",
    "Best reagent drops": "Beste Materialdrops",
    "Where on the map": "Wo auf der Karte",
    "Where to find it": "Wo du ihn findest",
    "Fishing for gold": "Angeln für Gold",
    "Fishing elsewhere": "Anderswo angeln",
    "Zones at these levels": "Gebiete auf diesen Stufen",
    "How drop rates work": "So funktionieren Dropraten",
    "How these numbers work": "So entstehen diese Zahlen",
    "Contributor leaderboard": "Bestenliste der Mitwirkenden",
    "Where data is needed": "Wo Daten fehlen",
    "Where GoldScout needs data": "Wo GoldScout Daten braucht",
    "Farm these at the same time": "Gleich mitfarmen",
    "Closest to solid:": "Am nächsten an verlässlich:",
    "Lowest price:": "Niedrigster Preis:",
    "Help fill this in.": "Hilf mit, das zu füllen.",
    "Auction prices for": "Auktionspreise für",
    "Realm type and faction": "Realm-Art und Fraktion",
    "More farms in %s": "Mehr Farmen in %s",
    "Fishing in %s": "Angeln in %s",
    "Farming in %s": "Farmen in %s",
    "Gold farms for %s": "Goldfarmen für %s",
    "Crafting reagents in %s": "Handwerksmaterialien in %s",

    # -- short phrases ----------------------------------------------------------
    "Around %s": "Bei %s",
    "Around %s: looted %s here": "Bei %s: hier %s-mal gelootet",
    "Most around <b>%s</b>.": "Am meisten bei <b>%s</b>.",
    "%s gives %s.": "%s bringt %s.",
    "%s catches %s": "%s Fänge %s",
    "%s on %s of catches": "%s bei %s der Fänge",
    "%d kills recorded": "%d erfasste Kills",
    "%s kills recorded %s": "%s erfasste Kills %s",
    "%d of %d mobs solid": "%d von %d Gegnern verlässlich",
    "%d more mob to %d%%": "noch %d Gegner bis %d%%",
    "%d more mobs to %d%%": "noch %d Gegner bis %d%%",
    "%d kills, <b>%d to go</b>": "%d Kills, <b>noch %d</b>",
    "lowest skill seen %d": "niedrigste Fertigkeit %d",
    "about %s a catch, %s an hour*": "etwa %s pro Fang, %s pro Stunde*",
    "Zone · %d mob": "Gebiet · %d Gegner",
    "Zone · %d mobs": "Gebiet · %d Gegner",
    "Fishing · %s catches": "Angeln · %s Fänge",
    "Farms by level · %d mobs": "Farmen nach Stufe · %d Gegner",
    "All %d farm for %s": "Die %d Farm für %s",
    "All %d farms for %s": "Alle %d Farmen für %s",
    " and %d other mob": " und %d anderen Gegner",
    " and %d other mobs": " und %d anderen Gegnern",
    ", and %d other zone": " und %d weiteren Gebiet",
    ", and %d other zones": " und %d weiteren Gebieten",
    ", dropping %d crafting reagent": ", die %d Handwerksmaterial droppen",
    ", dropping %d crafting reagents": ", die %d Handwerksmaterialien droppen",
    "Its best source, %s,": "Die beste Quelle, %s,",
    "Its best spot, %s in %s,": "Der beste Ort, %s in %s,",
    "95%% likely between these, from %d recorded": "mit 95%% Wahrscheinlichkeit dazwischen, aus %d erfassten",
    "Map of %s: where players found %s": "Karte von %s: wo Spieler %s gefunden haben",
    "Map of %s: where players looted %s": "Karte von %s: wo Spieler %s gelootet haben",
    "Map art &copy; Blizzard Entertainment.": "Kartengrafik &copy; Blizzard Entertainment.",
    "Faint squares on a grid are where players have looted anything else in the zone.":
        "Blasse Felder im Raster zeigen, wo Spieler sonst etwas im Gebiet gelootet haben.",

    # -- sentences ----------------------------------------------------------------
    "No drops recorded yet.": "Noch keine Drops erfasst.",
    "No mobs have enough kills recorded yet.": "Noch hat kein Gegner genug erfasste Kills.",
    "No fishing recorded yet.": "Noch kein Angeln erfasst.",
    "Chance per pickpocket, over %d attempts.": "Chance pro Taschendiebstahl, aus %d Versuchen.",
    "Other items from the same mobs and fishing spots.": "Andere Gegenstände von denselben Gegnern und Angelplätzen.",
    "Turn on JavaScript to see current auction prices.": "Schalte JavaScript ein, um aktuelle Auktionspreise zu sehen.",
    "Auction data from the Blizzard Entertainment Game Data API. GoldScout is not affiliated with or endorsed by "
    "Blizzard.": "Auktionsdaten aus der Game Data API von Blizzard Entertainment. GoldScout ist nicht mit Blizzard "
                 "verbunden und wird nicht von Blizzard unterstützt.",
    "Zone champions: the players with the most kills here.": "Gebietschampions: die Spieler mit den meisten Kills hier.",
    "Named only if they choose it in GoldScout Companion.": "Mit Namen nur, wenn sie das in GoldScout Companion wählen.",
    "Mobs a few kills from solid rates, the closest first.":
        "Gegner, denen nur noch wenige Kills zu verlässlichen Raten fehlen, die nächsten zuerst.",
    "Chance is how often players got the item per kill; the small numbers are the range it is 95% likely to be in, "
    "which narrows as more kills are recorded. Counted in WoW Forever only: no Classic Era data is mixed in.":
        "Die Chance ist, wie oft Spieler den Gegenstand pro Kill bekommen haben; die kleinen Zahlen sind der Bereich, "
        "in dem sie mit 95% Wahrscheinlichkeit liegt, und er wird enger, je mehr Kills erfasst sind. Nur in WoW "
        "Forever gezählt: keine Classic-Era-Daten eingemischt.",
    "Chance is how often players got the item per catch; the small numbers are the range it is 95% likely to be in, "
    "which narrows as more catches are recorded. Counted in WoW Forever only: no Classic Era data is mixed in.":
        "Die Chance ist, wie oft Spieler den Gegenstand pro Fang bekommen haben; die kleinen Zahlen sind der Bereich, "
        "in dem sie mit 95% Wahrscheinlichkeit liegt, und er wird enger, je mehr Fänge erfasst sind. Nur in WoW "
        "Forever gezählt: keine Classic-Era-Daten eingemischt.",
    "Every number here comes from players looting in game. Install <a href=\"%s\">GoldScout</a> and add "
    "<a href=\"%s\">GoldScout Companion</a>: it brings auction prices into the game every hour without "
    "scanning, and shares what you loot automatically. More players, better data for everyone. <a href=\"%s\">See "
    "where data is needed most</a>.":
        "Jede Zahl hier stammt von Spielern, die im Spiel looten. Installiere <a href=\"%s\">GoldScout</a> und dazu "
        "<a href=\"%s\">GoldScout Companion</a>: Es bringt stündlich Auktionspreise ins Spiel, "
        "ohne zu scannen, und teilt deine Beute automatisch. Mehr Spieler, bessere Daten für alle. <a href=\"%s\">Sieh "
        "nach, wo Daten am meisten fehlen</a>.",
    "%s has %s %s recorded so far, so the ranges are wide; %d more and its rates are solid.":
        "%s hat bisher %s erfasste %s, daher sind die Bereiche breit; noch %d, dann sind die Raten verlässlich.",
    "Crafting reagents only, at %d kills an hour. In game, GoldScout works it out for your character, at your own "
    "pace.": "Nur Handwerksmaterialien, bei %d Kills pro Stunde. Im Spiel rechnet GoldScout das für deinen "
             "Charakter aus, in deinem eigenen Tempo.",
    "At %d kills an hour. In game, GoldScout works it out for your character, at your own pace and level.":
        "Bei %d Kills pro Stunde. Im Spiel rechnet GoldScout das für deinen Charakter aus, in deinem Tempo und auf "
        "deiner Stufe.",
    "At %d pickpockets an hour. In game, GoldScout works it out for your character, at your own pace and level.":
        "Bei %d Taschendiebstählen pro Stunde. Im Spiel rechnet GoldScout das für deinen Charakter aus, in deinem "
        "Tempo und auf deiner Stufe.",
    "At %d catches an hour in open water, half that at pools (finding the next one takes time).":
        "Bei %d Fängen pro Stunde im offenen Wasser, halb so viel an Fischschwärmen (den nächsten zu finden dauert).",
    "At %d catches an hour in open water, half that at pools. Gray junk is left out.":
        "Bei %d Fängen pro Stunde im offenen Wasser, halb so viel an Fischschwärmen. Grauer Schrott ist nicht "
        "eingerechnet.",
    "At %d catches an hour in open water, half that at pools. Lowest skill is the lowest Fishing skill a player has "
    "caught there with.": "Bei %d Fängen pro Stunde im offenen Wasser, halb so viel an Fischschwärmen. Niedrigste "
                          "Fertigkeit ist die niedrigste Angelfertigkeit, mit der ein Spieler dort etwas gefangen hat.",
    "Brightest where players loot %s most: around <b>%s</b> in %s. Coordinates match the in-game map.":
        "Am hellsten, wo Spieler %s am häufigsten looten: bei <b>%s</b> in %s. Die Koordinaten passen zur Karte im "
        "Spiel.",
    "Brightest where the most %s turned up: squares where players looted or fished more of it. Coordinates match "
    "the in-game map.": "Am hellsten, wo am meisten %s aufgetaucht ist: Felder, in denen Spieler mehr davon gelootet "
                       "oder geangelt haben. Die Koordinaten passen zur Karte im Spiel.",
    "Fishing here too: see <a href=\"%s\">what players catch in %s</a>.":
        "Angeln kannst du hier auch: sieh dir an, <a href=\"%s\">was Spieler in %s fangen</a>.",
    "Mobs to farm here too: see <a href=\"%s\">farming in %s</a>.":
        "Gegner zum Farmen gibt es hier auch: sieh dir <a href=\"%s\">Farmen in %s</a> an.",
    "<a href=\"%s\">The best fishing spots for gold</a>, by zone.":
        "<a href=\"%s\">Die besten Angelplätze für Gold</a>, nach Gebiet.",

    # -- mob pages --------------------------------------------------------------
    "%s is a level %s mob in %s in WoW Forever.": "%s ist ein Gegner der Stufe %s in %s in WoW Forever.",
    "%s is a level %s mob in WoW Forever.": "%s ist ein Gegner der Stufe %s in WoW Forever.",
    "%s is a mob in %s in WoW Forever.": "%s ist ein Gegner in %s in WoW Forever.",
    "%s is a mob in WoW Forever.": "%s ist ein Gegner in WoW Forever.",
    "GoldScout players have recorded %s kill.": "GoldScout-Spieler haben %s Kill erfasst.",
    "GoldScout players have recorded %s kills.": "GoldScout-Spieler haben %s Kills erfasst.",
    "Its most common crafting reagent is %s (%s of kills).":
        "Sein häufigstes Handwerksmaterial ist %s (bei %s der Kills).",
    "Its most common drop is %s (%s of kills).": "Sein häufigster Drop ist %s (bei %s der Kills).",
    "Its crafting reagents are worth about <b data-value=\"%s\">%s</b> per kill at current prices.":
        "Seine Handwerksmaterialien sind zu aktuellen Preisen etwa <b data-value=\"%s\">%s</b> pro Kill wert.",
    "Its drops are worth about <b data-value=\"%s\">%s</b> per kill at current prices.":
        "Seine Drops sind zu aktuellen Preisen etwa <b data-value=\"%s\">%s</b> pro Kill wert.",
    "%s drops and drop rates (WoW Forever)": "%s: Drops und Dropraten (WoW Forever)",
    "%s drop rates in WoW Forever: %s, from %d kills recorded by GoldScout players.":
        "Dropraten von %s in WoW Forever: %s, aus %d von GoldScout-Spielern erfassten Kills.",
    "What %s drops in WoW Forever, with drop rates from %d kills recorded by GoldScout players.":
        "Was %s in WoW Forever droppt, mit Dropraten aus %d von GoldScout-Spielern erfassten Kills.",

    # -- item pages ---------------------------------------------------------------
    "%s is %s in WoW Forever.": "%s ist %s in WoW Forever.",
    "GoldScout players have looted it from %d mob;": "GoldScout-Spieler haben es bei %d Gegner gelootet;",
    "GoldScout players have looted it from %d mobs;": "GoldScout-Spieler haben es bei %d Gegnern gelootet;",
    "GoldScout players have pickpocketed it from %d mob;": "GoldScout-Spieler haben es %d Gegner gestohlen;",
    "GoldScout players have pickpocketed it from %d mobs;": "GoldScout-Spieler haben es %d Gegnern gestohlen;",
    "GoldScout players have fished it up in %d zone;": "GoldScout-Spieler haben es in %d Gebiet geangelt;",
    "GoldScout players have fished it up in %d zones;": "GoldScout-Spieler haben es in %d Gebieten geangelt;",
    "the best source is %s%s, which gave it on %s of %s kills.":
        "die beste Quelle ist %s%s, mit dem Gegenstand bei %s von %s Kills.",
    "the best source is %s%s, which gave it on %s of %s pickpockets.":
        "die beste Quelle ist %s%s, mit dem Gegenstand bei %s von %s Taschendiebstählen.",
    "the best spot is %s in %s, which gave it on %s of %s catches.":
        "der beste Ort ist %s in %s, mit dem Gegenstand bei %s von %s Fängen.",
    "It's also fished up in %d zone.": "Geangelt wird es außerdem in %d Gebiet.",
    "It's also fished up in %d zones.": "Geangelt wird es außerdem in %d Gebieten.",
    "%s drops from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot.":
        "%s droppt bei %s (%s)%s in WoW Forever. Dropraten aus der Beute von GoldScout-Spielern gezählt.",
    "%s is pickpocketed from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot.":
        "%s wird %s (%s)%s in WoW Forever gestohlen. Dropraten aus der Beute von GoldScout-Spielern gezählt.",
    "Where to fish %s in WoW Forever: %s in %s (%s of catches)%s. Counted from GoldScout players' catches.":
        "Wo du %s in WoW Forever angelst: %s in %s (%s der Fänge)%s. Aus den Fängen von GoldScout-Spielern gezählt.",
    "Where to farm %s (WoW Forever)": "Wo du %s farmst (WoW Forever)",
    "Where to fish %s (WoW Forever)": "Wo du %s angelst (WoW Forever)",

    # -- zone pages and goals ---------------------------------------------------
    "GoldScout players have recorded %d%s mob in %s with enough kills for reliable drop rates":
        "GoldScout-Spieler haben %d Gegner%s in %s mit genug Kills für belastbare Dropraten erfasst",
    "GoldScout players have recorded %d%s mobs in %s with enough kills for reliable drop rates":
        "GoldScout-Spieler haben %d Gegner%s in %s mit genug Kills für belastbare Dropraten erfasst",
    "Where to farm gold in %s (WoW Forever)": "Wo du in %s Gold farmst (WoW Forever)",
    "Mobs to farm in %s, WoW Forever, and the crafting reagents they drop, from GoldScout players' loot.":
        "Gegner zum Farmen in %s, WoW Forever, und die Handwerksmaterialien, die sie droppen, aus der Beute von "
        "GoldScout-Spielern.",
    "<b>Goal reached:</b> every mob players have recorded in %s has solid drop rates. New mobs recorded here join "
    "the goal.": "<b>Ziel erreicht:</b> Jeder in %s erfasste Gegner hat verlässliche Dropraten. Neu erfasste Gegner "
                 "kommen zum Ziel dazu.",
    "Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far, past %d%%. Next milestone: %s.":
        "Jeder Gegner hier mit verlässlichen Dropraten (%d+ Kills): bisher <b>%d von %d</b>, über %d%%. Nächster "
        "Meilenstein: %s.",
    "Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far. Next milestone: %s.":
        "Jeder Gegner hier mit verlässlichen Dropraten (%d+ Kills): bisher <b>%d von %d</b>. Nächster Meilenstein: "
        "%s.",

    # -- level ranges and farms ---------------------------------------------------
    "Gold farms by level (WoW Forever)": "Goldfarmen nach Stufe (WoW Forever)",
    "The best WoW Forever gold farms for every level range, ranked by gold per hour at current auction prices, from "
    "GoldScout players' loot.": "Die besten Goldfarmen in WoW Forever für jede Stufe, nach Gold pro Stunde zu "
                               "aktuellen Auktionspreisen sortiert, aus der Beute von GoldScout-Spielern.",
    "Mobs GoldScout players have recorded at least %d kills of, with the crafting reagents they drop most often, "
    "ranked by gold per hour at current auction prices. Open a level range for every farm in it, a mob for every "
    "drop, or an item for everywhere it drops.":
        "Gegner, von denen GoldScout-Spieler mindestens %d Kills erfasst haben, mit den Handwerksmaterialien, die sie "
        "am häufigsten droppen, nach Gold pro Stunde zu aktuellen Auktionspreisen sortiert. Öffne eine Stufe für "
        "jede Farm darin, einen Gegner für jeden Drop oder einen Gegenstand für jeden Ort, an dem er droppt.",
    "Best gold farms for %s (WoW Forever)": "Die besten Goldfarmen für %s (WoW Forever)",
    "%d mobs at %s that GoldScout players have recorded, from %s kills, ranked by what their crafting reagents are "
    "worth an hour at current auction prices. Pick your realm type and faction for your prices.":
        "%d Gegner auf %s, die GoldScout-Spieler erfasst haben, aus %s Kills, sortiert nach dem Wert ihrer "
        "Handwerksmaterialien pro Stunde zu aktuellen Auktionspreisen. Wähle deine Realm-Art und Fraktion für deine "
        "Preise.",
    "The WoW Forever mobs worth farming at %s, ranked by gold per hour at current auction prices, from %s kills "
    "recorded by GoldScout players.":
        "Die Gegner in WoW Forever, die sich auf %s zu farmen lohnen, nach Gold pro Stunde zu aktuellen "
        "Auktionspreisen sortiert, aus %s von GoldScout-Spielern erfassten Kills.",

    # -- fishing ------------------------------------------------------------------------
    "GoldScout players have recorded %s catches fishing in %s, WoW Forever.":
        "GoldScout-Spieler haben %s Fänge beim Angeln in %s, WoW Forever, erfasst.",
    "The lowest Fishing skill seen catching here is %d.": "Die niedrigste Angelfertigkeit, mit der hier gefangen wurde, "
                                                          "ist %d.",
    "Fishing in %s: catches and gold per hour (WoW Forever)": "Angeln in %s: Fänge und Gold pro Stunde (WoW Forever)",
    "What you catch fishing in %s, WoW Forever%s, from %s catches recorded by GoldScout players.":
        "Was du beim Angeln in %s, WoW Forever, fängst%s, aus %s von GoldScout-Spielern erfassten Fängen.",
    "Best fishing spots for gold (WoW Forever)": "Die besten Angelplätze für Gold (WoW Forever)",
    "Where to fish for gold in WoW Forever: every zone ranked by gold per hour at current auction prices, from %s "
    "catches recorded by GoldScout players.":
        "Wo du in WoW Forever für Gold angelst: jedes Gebiet nach Gold pro Stunde zu aktuellen Auktionspreisen "
        "sortiert, aus %s von GoldScout-Spielern erfassten Fängen.",
    "Every zone GoldScout players have fished in WoW Forever, from %s catches, ranked by what the catch is worth an "
    "hour at current auction prices. Pick your realm type and faction for your prices.":
        "Jedes Gebiet, in dem GoldScout-Spieler in WoW Forever geangelt haben, aus %s Fängen, sortiert nach dem Wert "
        "des Fangs pro Stunde zu aktuellen Auktionspreisen. Wähle deine Realm-Art und Fraktion für deine Preise.",

    # -- drop rates page ----------------------------------------------------------------
    "How GoldScout drop rates work": "So funktionieren die Dropraten von GoldScout",
    "Where GoldScout's WoW Forever drop rates come from, what the chance and confidence mean, and how the data is "
    "checked.": "Woher die Dropraten von GoldScout für WoW Forever kommen, was Chance und Verlässlichkeit bedeuten "
                "und wie die Daten geprüft werden.",
    "fewer than 5 kills. A first look; expect it to change.": "unter 5 Kills. Ein erster Eindruck; das ändert sich "
                                                              "noch.",
    "5 to 14 kills. Common drops are roughly right.": "5 bis 14 Kills. Häufige Drops stimmen ungefähr.",
    "15 to 49 kills. Good for most drops.": "15 bis 49 Kills. Gut für die meisten Drops.",
    "50 kills or more. Reliable, even for uncommon drops.": "50 Kills oder mehr. Verlässlich, auch für seltenere Drops.",

    # -- data wanted ------------------------------------------------------------------------
    "Where GoldScout needs drop data (WoW Forever)": "Wo GoldScout Dropdaten braucht (WoW Forever)",
    "The WoW Forever level ranges, zones and mobs with the least drop data recorded by GoldScout players, and how to "
    "help fill them in.": "Die Stufen, Gebiete und Gegner in WoW Forever, für die GoldScout-Spieler die wenigsten "
                         "Dropdaten erfasst haben, und wie du hilfst, sie zu füllen.",
    "Every drop rate on this site comes from GoldScout players' loot: %s kills so far, %d mobs with drop rates, "
    "%d of them with the %d+ kills that make a rate solid. Here's where it's thin. Farming any of these with GoldScout and the "
    "companion running fills it in for everyone.":
        "Jede Droprate auf dieser Seite stammt aus der Beute von GoldScout-Spielern: bisher %s Kills, %d Gegner mit "
        "Dropraten, %d davon mit den %d+ Kills, die eine Rate verlässlich machen. Hier ist es noch dünn. Wer hier mit GoldScout "
        "und laufendem Companion farmt, füllt das für alle.",
    "The bar shows the share of mobs with %d+ kills (rated good); the brighter part has %d+ (rated high: solid).":
        "Der Balken zeigt den Anteil der Gegner mit %d+ Kills (gut); der hellere Teil hat %d+ (hoch: verlässlich).",
    "Each zone's goal: every mob players have recorded there with solid drop rates (%d+ kills), with milestones at "
    "10%%, 25%%, 50%% and 75%%. %d of %d zones complete, %d past a milestone. Least recorded first; zones nobody has "
    "looted in yet aren't listed.":
        "Das Ziel jedes Gebiets: jeder dort erfasste Gegner mit verlässlichen Dropraten (%d+ Kills), mit "
        "Meilensteinen bei 10%%, 25%%, 50%% und 75%%. %d von %d Gebieten geschafft, %d über einem Meilenstein. Am "
        "wenigsten erfasste zuerst; Gebiete, in denen noch niemand gelootet hat, fehlen.",
}
