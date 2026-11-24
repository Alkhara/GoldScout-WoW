"""Spanish text for the website's data pages (site/data_pages.py T()): English text -> Spanish.

Keys are the exact English text, placeholders and all; a translation keeps every %s and %d in the same
order (Python's % can't reorder them) and every %% as %%. Words the addon uses keep the addon's Spanish
(GoldScout/Locale_esES.lua: enemigo, zona, nivel, banco de peces, alta/buena/media/baja...), and players
are "tú", as in the addon. tests/test_site.py fails if a Spanish page looks up text that isn't here.
"""
# The /drop-rates page (data_pages.RATES_BODY), in Spanish.
RATES_BODY = """<h1>Cómo funcionan las tasas de botín de GoldScout</h1>
<p class=summary>Cada cifra de esta página viene de jugadores de GoldScout que despojan en WoW Forever. Nada está copiado de Wowhead ni de ninguna otra base de datos.</p>
<h2>Probabilidad</h2>
<p>La probabilidad de un objeto es en cuántas muertes cayó, dividido entre las muertes registradas. Un enemigo con 200 muertes registradas que soltó un objeto 50 veces muestra un 25%%. La pila media es cuántos salieron por cada vez que cayó. Al robar, la probabilidad es por robo en lugar de por muerte.</p>
<p>Junto a cada probabilidad está el intervalo en el que la probabilidad real está con un 95%% de seguridad, según cuántas muertes la respaldan: un 25%% de 200 muertes es 20&ndash;31%%; de 20 muertes, 11&ndash;47%%. Cuando un objeto cae de varios enemigos, se ordenan por el extremo inferior de ese intervalo, para que unas pocas muertes con suerte no superen a un enemigo que cientos de muertes han fijado.</p>
<p>Todo se cuenta en WoW Forever. No se mezclan cifras de Classic Era, así que las tasas de botín de Forever se ven tal como son.</p>
<h2>Fiabilidad</h2>
<p>Cuantas más muertes registradas, más se acerca la probabilidad a la real. Cada enemigo muestra lo seguras que son sus cifras:</p>
<ul class=ticks>%s</ul>
<p>Solo hay páginas para enemigos con al menos %d muertes registradas. En el juego, GoldScout valora con prudencia las zonas de enemigos con pocas muertes, para que una racha de suerte no suba a un enemigo a lo más alto.</p>
<h2>Para que los datos sean honestos</h2>
<ul class=ticks>
<li>De cada enemigo cuentan como mucho %s muertes de un mismo jugador, para que ningún jugador decida solo las cifras de un enemigo.</li>
<li>Cada envío se valida, y las tasas de botín inusuales se revisan antes de usarse.</li>
<li>Desollar, minar o recoger hierbas de un cadáver no cuenta como muerte. Las muertes cuyo cadáver no tenía botín, sí.</li>
<li>Los objetos grises son chatarra y no se muestran. El equipo, las recetas y las gemas son botines raros del mundo y aparecen bajo los demás botines.</li>
</ul>
<h2>Precios y oro por muerte</h2>
<p>Los precios son la compra inmediata más baja de la casa de subastas para el tipo de reino y la facción que elijas, de los datos de subastas de Blizzard, actualizados más o menos cada hora. El oro por muerte suma, para cada componente de fabricación, la probabilidad por la pila media por el precio. No se incluyen el equipo, las recetas ni las gemas (sus precios varían demasiado), ni lo que tarda una muerte.</p>
<p>El accesorio GoldScout convierte esto en oro por hora para tu personaje, y usa tus propios escaneos de la casa de subastas cuando son más recientes.</p>
<p class=small>%s</p>
"""

ES = {
    # -- words ----------------------------------------------------------------
    "Mob": "Enemigo",
    "Mobs": "Enemigos",
    "Item": "Objeto",
    "Zone": "Zona",
    "Level": "Nivel",
    "Levels": "Niveles",
    "Home": "Inicio",
    "Goal": "Meta",
    "Next": "Siguiente",
    "Solid": "Fiable",
    "Community goals": "Metas de la comunidad",
    "Players sharing data": "Jugadores que comparten datos",
    "Kills recorded": "Muertes registradas",
    "Mobs with solid drop rates (%d+ kills)": "Enemigos con tasas de botín fiables (%d+ muertes)",
    "%s of %s": "%s de %s",
    "<b>%s</b> of %s": "<b>%s</b> de %s",
    "<b class=done>%s</b> of %s": "<b class=done>%s</b> de %s",
    "%d day left": "queda %d día",
    "%d days left": "quedan %d días",
    "today": "hoy",
    "Goals for everyone sharing data, by %s (%s). Every player who adds the companion and every kill moves them.":
        "Metas para todos los que comparten datos, hasta el %s (%s). Cada jugador que añade GoldScout Companion y "
        "cada muerte las acercan.",
    "The goals for %s, and how far everyone got.": "Las metas para el %s y hasta dónde llegamos todos.",
    "Every goal for %s reached. Thank you, everyone who shares!":
        "Todas las metas para el %s alcanzadas. ¡Gracias a todos los que comparten!",
    "Price": "Precio",
    "Kills": "Muertes",
    "kills": "muertes",
    "Catch": "Captura",
    "Catches": "Capturas",
    "catches": "capturas",
    "Pickpockets": "Robos",
    "pickpockets": "robos",
    "Where": "Dónde",
    "Chance": "Probabilidad",
    "Reagent": "Componente",
    "Recorded": "Registradas",
    "Fishing": "Pesca",
    "low": "baja",
    "fair": "media",
    "good": "buena",
    "high": "alta",
    " and ": " y ",
    "none yet": "aún ninguno",
    "nobody yet": "aún nadie",
    "fished up": "pescado",
    "Complete": "Completada",
    "Open water": "Aguas abiertas",
    "Fishing pool": "Banco de peces",
    "Fishing pool %d": "Banco de peces %d",
    "Item %d": "Objeto %d",
    "Mob %d": "Enemigo %d",
    "level %s": "nivel %s",
    "Level %s": "Nivel %s",
    "Levels %d-%d": "Niveles %d-%d",
    "levels %d-%d": "niveles %d-%d",
    " level %d": " de nivel %d",
    " level %d-%d": " de nivel %d-%d",
    "%d mob": "%d enemigo",
    "%d mobs": "%d enemigos",
    "%d source": "%d origen",
    "%d sources": "%d orígenes",
    "%d+ kills": "%d+ muertes",
    "Crafting reagent": "Componente de fabricación",
    "Rare drop": "Botín raro",
    "a crafting reagent": "un componente de fabricación",
    "a rare world drop": "un botín raro del mundo",
    "an item": "un objeto",
    "No name recorded in this language yet": "Aún no hay nombre en español registrado",

    # -- headings and table heads ---------------------------------------------
    "By zone": "Por zona",
    "By level": "Por nivel",
    "Zone goal": "Meta de la zona",
    "Zone goals": "Metas de las zonas",
    "Avg. stack": "Pila media",
    "Other drops": "Otros botines",
    "Best source": "Mejor origen",
    "Dropped by": "Lo sueltan",
    "Pickpocketed from": "Se roba a",
    "Other levels": "Otros niveles",
    "Almost there": "Casi",
    "Lowest skill": "Habilidad mínima",
    "Best catches": "Mejores capturas",
    "Pickpocketing": "Robo",
    "Per kill": "Por muerte",
    "Per catch": "Por captura",
    "Per pickpocket": "Por robo",
    "Gold per hour": "Oro por hora",
    "Gold per kill": "Oro por muerte",
    "Gold per catch": "Oro por captura",
    "Gold per pickpocket": "Oro por robo",
    "Where it drops": "Dónde cae",
    "Farms by level": "Farmeo por nivel",
    "Crafting reagents": "Componentes de fabricación",
    "Best reagent drops": "Mejores componentes",
    "Where on the map": "Dónde en el mapa",
    "Where to find it": "Dónde encontrarlo",
    "Fishing for gold": "Pescar por oro",
    "Fishing elsewhere": "Pescar en otros sitios",
    "Zones at these levels": "Zonas de estos niveles",
    "How drop rates work": "Cómo funcionan las tasas de botín",
    "How these numbers work": "De dónde salen estas cifras",
    "Contributor leaderboard": "Clasificación de colaboradores",
    "Where data is needed": "Dónde faltan datos",
    "Where GoldScout needs data": "Dónde GoldScout necesita datos",
    "Farm these at the same time": "Farméalos a la vez",
    "Closest to solid:": "Más cerca de ser fiable:",
    "Lowest price:": "Precio más bajo:",
    "Help fill this in.": "Ayuda a completarlo.",
    "Auction prices for": "Precios de subasta para",
    "Realm type and faction": "Tipo de reino y facción",
    "More farms in %s": "Más zonas de farmeo en %s",
    "Fishing in %s": "Pesca en %s",
    "Farming in %s": "Farmeo en %s",
    "Gold farms for %s": "Farmeo de oro para %s",
    "Crafting reagents in %s": "Componentes de fabricación en %s",

    # -- short phrases ----------------------------------------------------------
    "Around %s": "Cerca de %s",
    "Around %s: looted %s here": "Cerca de %s: despojado %s veces aquí",
    "Most around <b>%s</b>.": "Sobre todo cerca de <b>%s</b>.",
    "%s gives %s.": "%s da %s.",
    "%s catches %s": "%s capturas %s",
    "%s on %s of catches": "%s en el %s de las capturas",
    "%d kills recorded": "%d muertes registradas",
    "%s kills recorded %s": "%s muertes registradas %s",
    "%d of %d mobs solid": "%d de %d enemigos fiables",
    "%d more mob to %d%%": "%d enemigo más para el %d%%",
    "%d more mobs to %d%%": "%d enemigos más para el %d%%",
    "%d kills, <b>%d to go</b>": "%d muertes, <b>faltan %d</b>",
    "lowest skill seen %d": "habilidad mínima vista %d",
    "about %s a catch, %s an hour*": "unos %s por captura, %s por hora*",
    "Zone · %d mob": "Zona · %d enemigo",
    "Zone · %d mobs": "Zona · %d enemigos",
    "Fishing · %s catches": "Pesca · %s capturas",
    "Farms by level · %d mobs": "Farmeo por nivel · %d enemigos",
    "All %d farm for %s": "La %d zona de farmeo para %s",
    "All %d farms for %s": "Las %d zonas de farmeo para %s",
    " and %d other mob": " y %d enemigo más",
    " and %d other mobs": " y %d enemigos más",
    ", and %d other zone": " y %d zona más",
    ", and %d other zones": " y %d zonas más",
    ", dropping %d crafting reagent": ", que sueltan %d componente de fabricación",
    ", dropping %d crafting reagents": ", que sueltan %d componentes de fabricación",
    "Its best source, %s,": "Su mejor origen, %s,",
    "Its best spot, %s in %s,": "Su mejor lugar, %s en %s,",
    "95%% likely between these, from %d recorded": "con un 95%% de seguridad entre estos, de %d registradas",
    "Map of %s: where players found %s": "Mapa de %s: dónde encontraron los jugadores %s",
    "Map of %s: where players looted %s": "Mapa de %s: dónde despojaron los jugadores %s",
    "Map art &copy; Blizzard Entertainment.": "Ilustración del mapa &copy; Blizzard Entertainment.",
    "Faint squares on a grid are where players have looted anything else in the zone.":
        "Los cuadros tenues de la cuadrícula muestran dónde han despojado los jugadores cualquier otra cosa en la zona.",

    # -- sentences ----------------------------------------------------------------
    "No drops recorded yet.": "Aún no hay botines registrados.",
    "No mobs have enough kills recorded yet.": "Aún ningún enemigo tiene suficientes muertes registradas.",
    "No fishing recorded yet.": "Aún no hay pesca registrada.",
    "Chance per pickpocket, over %d attempts.": "Probabilidad por robo, sobre %d intentos.",
    "Other items from the same mobs and fishing spots.": "Otros objetos de los mismos enemigos y lugares de pesca.",
    "Turn on JavaScript to see current auction prices.": "Activa JavaScript para ver los precios de subasta actuales.",
    "Auction data from the Blizzard Entertainment Game Data API. GoldScout is not affiliated with or endorsed by "
    "Blizzard.": "Datos de subastas de la Game Data API de Blizzard Entertainment. GoldScout no está afiliado a "
                 "Blizzard ni respaldado por Blizzard.",
    "Zone champions: the players with the most kills here.":
        "Campeones de la zona: los jugadores con más muertes aquí.",
    "Named only if they choose it in GoldScout Companion.": "Con nombre solo si lo eligen en GoldScout Companion.",
    "Mobs a few kills from solid rates, the closest first.":
        "Enemigos a pocas muertes de tener tasas fiables, primero los más cercanos.",
    "Chance is how often players got the item per kill; the small numbers are the range it is 95% likely to be in, "
    "which narrows as more kills are recorded. Counted in WoW Forever only: no Classic Era data is mixed in.":
        "La probabilidad es con qué frecuencia los jugadores obtuvieron el objeto por muerte; los números pequeños son "
        "el intervalo en el que está con una seguridad del 95%, que se estrecha a medida que se registran más muertes. "
        "Contado solo en WoW Forever: no se mezclan datos de Classic Era.",
    "Chance is how often players got the item per catch; the small numbers are the range it is 95% likely to be in, "
    "which narrows as more catches are recorded. Counted in WoW Forever only: no Classic Era data is mixed in.":
        "La probabilidad es con qué frecuencia los jugadores obtuvieron el objeto por captura; los números pequeños "
        "son el intervalo en el que está con una seguridad del 95%, que se estrecha a medida que se registran más "
        "capturas. Contado solo en WoW Forever: no se mezclan datos de Classic Era.",
    "Every number here comes from players looting in game. Install <a href=\"%s\">GoldScout</a> and add "
    "<a href=\"%s\">GoldScout Companion</a>: it brings auction prices into the game every hour without "
    "scanning, and shares what you loot automatically. More players, better data for everyone. <a href=\"%s\">See "
    "where data is needed most</a>.":
        "Cada cifra de aquí viene de jugadores que despojan en el juego. Instala <a href=\"%s\">GoldScout</a> y añade "
        "<a href=\"%s\">GoldScout Companion</a>: trae cada hora los precios de subasta al juego sin escanear y "
        "comparte tu botín automáticamente. Más jugadores, mejores datos para todos. <a href=\"%s\">Mira dónde "
        "faltan más datos</a>.",
    "%s has %s %s recorded so far, so the ranges are wide; %d more and its rates are solid.":
        "%s tiene hasta ahora %s %s registradas, así que los intervalos son amplios; con %d más, sus tasas serán "
        "fiables.",
    'Crafting reagents only, at how fast GoldScout players kill each mob, or %d kills an hour until enough kills are timed. In game, GoldScout works it out for your character.':
        'Solo componentes de fabricación, al ritmo al que los jugadores de GoldScout matan a cada enemigo, o a %d muertes por hora hasta que haya suficientes muertes cronometradas. En el juego, GoldScout lo calcula para tu personaje.',
    'At how fast GoldScout players kill each mob, or %d kills an hour until enough kills are timed. In game, GoldScout works it out for your character and level.':
        'Al ritmo al que los jugadores de GoldScout matan a cada enemigo, o a %d muertes por hora hasta que haya suficientes muertes cronometradas. En el juego, GoldScout lo calcula para tu personaje y tu nivel.',
    "At %d pickpockets an hour. In game, GoldScout works it out for your character, at your own pace and level.":
        "A %d robos por hora. En el juego, GoldScout lo calcula para tu personaje, a tu ritmo y a tu nivel.",
    "At %d catches an hour in open water, half that at pools (finding the next one takes time).":
        "A %d capturas por hora en aguas abiertas, la mitad en bancos de peces (encontrar el siguiente lleva tiempo).",
    "At %d catches an hour in open water, half that at pools. Gray junk is left out.":
        "A %d capturas por hora en aguas abiertas, la mitad en bancos de peces. La chatarra gris no se cuenta.",
    "At %d catches an hour in open water, half that at pools. Lowest skill is the lowest Fishing skill a player has "
    "caught there with.": "A %d capturas por hora en aguas abiertas, la mitad en bancos de peces. Habilidad mínima es "
                          "la habilidad de pesca más baja con la que un jugador ha pescado allí.",
    "Brightest where players loot %s most: around <b>%s</b> in %s. Coordinates match the in-game map.":
        "Más brillante donde los jugadores más despojan %s: cerca de <b>%s</b> en %s. Las coordenadas coinciden con "
        "el mapa del juego.",
    "Brightest where the most %s turned up: squares where players looted or fished more of it. Coordinates match "
    "the in-game map.": "Más brillante donde más %s apareció: cuadros donde los jugadores despojaron o pescaron más. "
                       "Las coordenadas coinciden con el mapa del juego.",
    "Fishing here too: see <a href=\"%s\">what players catch in %s</a>.":
        "Aquí también se pesca: mira <a href=\"%s\">qué pescan los jugadores en %s</a>.",
    "Mobs to farm here too: see <a href=\"%s\">farming in %s</a>.":
        "Aquí también hay enemigos que farmear: mira <a href=\"%s\">el farmeo en %s</a>.",
    "<a href=\"%s\">The best fishing spots for gold</a>, by zone.":
        "<a href=\"%s\">Los mejores lugares de pesca por oro</a>, por zona.",

    # -- mob pages --------------------------------------------------------------
    "%s is a level %s mob in %s in WoW Forever.": "%s es un enemigo de nivel %s en %s en WoW Forever.",
    "%s is a level %s mob in WoW Forever.": "%s es un enemigo de nivel %s en WoW Forever.",
    "%s is a mob in %s in WoW Forever.": "%s es un enemigo en %s en WoW Forever.",
    "%s is a mob in WoW Forever.": "%s es un enemigo en WoW Forever.",
    "GoldScout players have recorded %s kill.": "Los jugadores de GoldScout han registrado %s muerte.",
    "GoldScout players have recorded %s kills.": "Los jugadores de GoldScout han registrado %s muertes.",
    "Its most common crafting reagent is %s (%s of kills).":
        "Su componente de fabricación más común es %s (en el %s de las muertes).",
    "Its most common drop is %s (%s of kills).": "Su botín más común es %s (en el %s de las muertes).",
    "Its crafting reagents are worth about <b data-value=\"%s\">%s</b> per kill at current prices.":
        "Sus componentes de fabricación valen unos <b data-value=\"%s\">%s</b> por muerte a los precios actuales.",
    "Its drops are worth about <b data-value=\"%s\">%s</b> per kill at current prices.":
        "Su botín vale unos <b data-value=\"%s\">%s</b> por muerte a los precios actuales.",
    "%s drops and drop rates (WoW Forever)": "%s: botín y tasas de botín (WoW Forever)",
    "%s drop rates in WoW Forever: %s, from %d kills recorded by GoldScout players.":
        "Tasas de botín de %s en WoW Forever: %s, de %d muertes registradas por jugadores de GoldScout.",
    "What %s drops in WoW Forever, with drop rates from %d kills recorded by GoldScout players.":
        "Qué suelta %s en WoW Forever, con tasas de botín de %d muertes registradas por jugadores de GoldScout.",

    # -- item pages ---------------------------------------------------------------
    "%s is %s in WoW Forever.": "%s es %s en WoW Forever.",
    "GoldScout players have looted it from %d mob;": "Los jugadores de GoldScout lo han despojado de %d enemigo;",
    "GoldScout players have looted it from %d mobs;": "Los jugadores de GoldScout lo han despojado de %d enemigos;",
    "GoldScout players have pickpocketed it from %d mob;": "Los jugadores de GoldScout se lo han robado a %d enemigo;",
    "GoldScout players have pickpocketed it from %d mobs;":
        "Los jugadores de GoldScout se lo han robado a %d enemigos;",
    "GoldScout players have fished it up in %d zone;": "Los jugadores de GoldScout lo han pescado en %d zona;",
    "GoldScout players have fished it up in %d zones;": "Los jugadores de GoldScout lo han pescado en %d zonas;",
    "the best source is %s%s, which gave it on %s of %s kills.":
        "el mejor origen es %s%s, que lo dio en %s de %s muertes.",
    "the best source is %s%s, which gave it on %s of %s pickpockets.":
        "el mejor origen es %s%s, que lo dio en %s de %s robos.",
    "the best spot is %s in %s, which gave it on %s of %s catches.":
        "el mejor lugar es %s en %s, que lo dio en %s de %s capturas.",
    "It's also fished up in %d zone.": "También se pesca en %d zona.",
    "It's also fished up in %d zones.": "También se pesca en %d zonas.",
    "%s drops from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot.":
        "%s cae de %s (%s)%s en WoW Forever. Tasas de botín contadas a partir del botín de jugadores de GoldScout.",
    "%s is pickpocketed from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot.":
        "%s se roba a %s (%s)%s en WoW Forever. Tasas de botín contadas a partir del botín de jugadores de GoldScout.",
    "Where to fish %s in WoW Forever: %s in %s (%s of catches)%s. Counted from GoldScout players' catches.":
        "Dónde pescar %s en WoW Forever: %s en %s (%s de las capturas)%s. Contado a partir de las capturas de "
        "jugadores de GoldScout.",
    "Where to farm %s (WoW Forever)": "Dónde farmear %s (WoW Forever)",
    "Where to fish %s (WoW Forever)": "Dónde pescar %s (WoW Forever)",

    # -- zone pages and goals ---------------------------------------------------
    "GoldScout players have recorded %d%s mob in %s with enough kills for reliable drop rates":
        "Los jugadores de GoldScout han registrado %d enemigo%s en %s con suficientes muertes para tasas de botín "
        "fiables",
    "GoldScout players have recorded %d%s mobs in %s with enough kills for reliable drop rates":
        "Los jugadores de GoldScout han registrado %d enemigos%s en %s con suficientes muertes para tasas de botín "
        "fiables",
    "Where to farm gold in %s (WoW Forever)": "Dónde farmear oro en %s (WoW Forever)",
    "Mobs to farm in %s, WoW Forever, and the crafting reagents they drop, from GoldScout players' loot.":
        "Enemigos que farmear en %s, WoW Forever, y los componentes de fabricación que sueltan, según el botín de "
        "jugadores de GoldScout.",
    "<b>Goal reached:</b> every mob players have recorded in %s has solid drop rates. New mobs recorded here join "
    "the goal.": "<b>Meta alcanzada:</b> cada enemigo registrado en %s tiene tasas de botín fiables. Los enemigos "
                 "nuevos que se registren aquí se suman a la meta.",
    "Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far, past %d%%. Next milestone: %s.":
        "Cada enemigo de aquí con tasas de botín fiables (%d+ muertes): <b>%d de %d</b> hasta ahora, más del %d%%. "
        "Siguiente hito: %s.",
    "Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far. Next milestone: %s.":
        "Cada enemigo de aquí con tasas de botín fiables (%d+ muertes): <b>%d de %d</b> hasta ahora. Siguiente hito: "
        "%s.",

    # -- level ranges and farms ---------------------------------------------------
    "Gold farms by level (WoW Forever)": "Farmeo de oro por nivel (WoW Forever)",
    "The best WoW Forever gold farms for every level range, ranked by gold per hour at current auction prices, from "
    "GoldScout players' loot.": "Las mejores zonas para farmear oro en WoW Forever para cada rango de niveles, por oro "
                               "por hora a los precios de subasta actuales, según el botín de jugadores de GoldScout.",
    "Mobs GoldScout players have recorded at least %d kills of, with the crafting reagents they drop most often, "
    "ranked by gold per hour at current auction prices. Open a level range for every farm in it, a mob for every "
    "drop, or an item for everywhere it drops.":
        "Enemigos de los que los jugadores de GoldScout han registrado al menos %d muertes, con los componentes de "
        "fabricación que sueltan más a menudo, por oro por hora a los precios de subasta actuales. Abre un rango de "
        "niveles para ver cada zona de farmeo, un enemigo para cada botín o un objeto para todos los sitios donde cae.",
    "Best gold farms for %s (WoW Forever)": "Las mejores zonas para farmear oro para %s (WoW Forever)",
    "%d mobs at %s that GoldScout players have recorded, from %s kills, ranked by what their crafting reagents are "
    "worth an hour at current auction prices. Pick your realm type and faction for your prices.":
        "%d enemigos de %s que han registrado los jugadores de GoldScout, de %s muertes, ordenados por lo que valen "
        "sus componentes de fabricación por hora a los precios de subasta actuales. Elige tu tipo de reino y tu "
        "facción para ver tus precios.",
    "The WoW Forever mobs worth farming at %s, ranked by gold per hour at current auction prices, from %s kills "
    "recorded by GoldScout players.":
        "Los enemigos de WoW Forever que vale la pena farmear en %s, por oro por hora a los precios de subasta "
        "actuales, de %s muertes registradas por jugadores de GoldScout.",

    # -- fishing ------------------------------------------------------------------------
    "GoldScout players have recorded %s catches fishing in %s, WoW Forever.":
        "Los jugadores de GoldScout han registrado %s capturas pescando en %s, WoW Forever.",
    "The lowest Fishing skill seen catching here is %d.": "La habilidad de pesca más baja vista pescando aquí es %d.",
    "Fishing in %s: catches and gold per hour (WoW Forever)": "Pesca en %s: capturas y oro por hora (WoW Forever)",
    "What you catch fishing in %s, WoW Forever%s, from %s catches recorded by GoldScout players.":
        "Qué pescas en %s, WoW Forever%s, de %s capturas registradas por jugadores de GoldScout.",
    "Best fishing spots for gold (WoW Forever)": "Los mejores lugares de pesca por oro (WoW Forever)",
    "Where to fish for gold in WoW Forever: every zone ranked by gold per hour at current auction prices, from %s "
    "catches recorded by GoldScout players.":
        "Dónde pescar por oro en WoW Forever: cada zona por oro por hora a los precios de subasta actuales, de %s "
        "capturas registradas por jugadores de GoldScout.",
    "Every zone GoldScout players have fished in WoW Forever, from %s catches, ranked by what the catch is worth an "
    "hour at current auction prices. Pick your realm type and faction for your prices.":
        "Cada zona en la que los jugadores de GoldScout han pescado en WoW Forever, de %s capturas, ordenada por lo "
        "que vale la pesca por hora a los precios de subasta actuales. Elige tu tipo de reino y tu facción para ver "
        "tus precios.",

    # -- drop rates page ----------------------------------------------------------------
    "How GoldScout drop rates work": "Cómo funcionan las tasas de botín de GoldScout",
    "Where GoldScout's WoW Forever drop rates come from, what the chance and confidence mean, and how the data is "
    "checked.": "De dónde salen las tasas de botín de GoldScout para WoW Forever, qué significan la probabilidad y la "
                "fiabilidad, y cómo se comprueban los datos.",
    "fewer than 5 kills. A first look; expect it to change.": "menos de 5 muertes. Un primer vistazo; cambiará.",
    "5 to 14 kills. Common drops are roughly right.": "de 5 a 14 muertes. Los botines comunes son más o menos correctos.",
    "15 to 49 kills. Good for most drops.": "de 15 a 49 muertes. Buena para la mayoría de los botines.",
    "50 kills or more. Reliable, even for uncommon drops.": "50 muertes o más. Fiable, incluso para botines poco comunes.",

    # -- data wanted ------------------------------------------------------------------------
    "Where GoldScout needs drop data (WoW Forever)": "Dónde GoldScout necesita datos de botín (WoW Forever)",
    "The WoW Forever level ranges, zones and mobs with the least drop data recorded by GoldScout players, and how to "
    "help fill them in.": "Los rangos de niveles, zonas y enemigos de WoW Forever con menos datos de botín registrados "
                         "por jugadores de GoldScout, y cómo ayudar a completarlos.",
    "Every drop rate on this site comes from GoldScout players' loot: %s kills so far, %d mobs with drop rates, "
    "%d of them with the %d+ kills that make a rate solid. Here's where it's thin. Farming any of these with GoldScout and the "
    "companion running fills it in for everyone.":
        "Cada tasa de botín de este sitio viene del botín de jugadores de GoldScout: %s muertes hasta ahora, %d "
        "enemigos con tasas de botín, %d de ellos con las %d+ muertes que hacen fiable una tasa. Aquí es donde faltan "
        "datos. Farmear cualquiera de estos con GoldScout y Companion en marcha lo completa para todos.",
    "The bar shows the share of mobs with %d+ kills (rated good); the brighter part has %d+ (rated high: solid).":
        "La barra muestra la parte de enemigos con %d+ muertes (buena); la parte más brillante tiene %d+ (alta: "
        "fiable).",
    "Each zone's goal: every mob players have recorded there with solid drop rates (%d+ kills), with milestones at "
    "10%%, 25%%, 50%% and 75%%. %d of %d zones complete, %d past a milestone. Least recorded first; zones nobody has "
    "looted in yet aren't listed.":
        "La meta de cada zona: cada enemigo registrado allí con tasas de botín fiables (%d+ muertes), con hitos en el "
        "10%%, 25%%, 50%% y 75%%. %d de %d zonas completadas, %d han pasado un hito. Primero las menos registradas; "
        "las zonas donde nadie ha despojado aún no aparecen.",
}
