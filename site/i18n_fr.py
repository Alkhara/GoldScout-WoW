"""French text for the website's data pages (site/data_pages.py T()): English text -> French.

Keys are the exact English text, placeholders and all; a translation keeps every %s and %d in the same
order (Python's % can't reorder them) and every %% as %%. Words the addon uses keep the addon's French
(GoldScout/Locale_frFR.lua: monstre, victimes, butin, taux de butin, composant d'artisanat, hôtel des ventes,
banc de poissons, élevée/bonne/moyenne/faible...), and players are "vous", as in the addon. Write plain spaces
before : ; ? ! and %: French pages turn them into non-breaking spaces (data_pages.french_typography).
tests/test_site.py fails if a French page looks up text that isn't here.
"""
# The /drop-rates page (data_pages.RATES_BODY), in French.
RATES_BODY = """<h1>Comment fonctionnent les taux de butin de GoldScout</h1>
<p class=summary>Chaque chiffre de cette page vient de joueurs de GoldScout qui ramassent du butin dans WoW Forever. Rien n'est copié de Wowhead ni d'aucune autre base de données.</p>
<h2>Chance</h2>
<p>La chance d'un objet, c'est le nombre de victimes sur lesquelles il est tombé, divisé par les victimes enregistrées. Un monstre avec 200 victimes enregistrées qui a donné un objet 50 fois affiche 25 %%. La pile moyenne est le nombre d'exemplaires obtenus chaque fois qu'il tombe. Pour le vol à la tire, la chance est par vol plutôt que par victime.</p>
<p>À côté de chaque chance se trouve l'intervalle qui contient la vraie chance avec une certitude de 95 %%, selon le nombre de victimes derrière : 25 %% sur 200 victimes donne 20&ndash;31 %% ; sur 20 victimes, 11&ndash;47 %%. Quand un objet tombe sur plusieurs monstres, ils sont classés selon le bas de cet intervalle, pour que quelques victimes chanceuses ne passent pas devant un monstre que des centaines de victimes ont établi.</p>
<p>Tout est compté dans WoW Forever. Aucun chiffre de Classic Era n'est mélangé, donc les taux de butin de Forever apparaissent tels qu'ils sont.</p>
<h2>Fiabilité</h2>
<p>Plus il y a de victimes enregistrées, plus la chance se rapproche de la vraie. Chaque monstre indique la fiabilité de ses chiffres :</p>
<ul class=ticks>%s</ul>
<p>Seuls les monstres avec au moins %d victimes enregistrées ont une page. En jeu, GoldScout évalue prudemment les farms de monstres avec peu de victimes, pour qu'une série chanceuse ne fasse pas grimper un monstre en tête.</p>
<h2>Des données honnêtes</h2>
<ul class=ticks>
<li>Pour chaque monstre, au plus %s victimes d'un même joueur comptent, pour qu'aucun joueur ne décide seul des chiffres d'un monstre.</li>
<li>Chaque envoi est vérifié, et les taux de butin inhabituels sont contrôlés avant d'être utilisés.</li>
<li>Dépecer, miner ou cueillir sur un cadavre ne compte pas comme une victime. Les victimes dont le cadavre n'avait aucun butin, si.</li>
<li>Les objets gris sont de la camelote et ne sont pas affichés. L'équipement, les recettes et les gemmes sont des butins rares du monde et apparaissent sous les autres butins.</li>
</ul>
<h2>Prix et or par victime</h2>
<p>Les prix sont l'achat immédiat le plus bas de l'hôtel des ventes pour le type de royaume et la faction que vous choisissez, d'après les données de l'hôtel des ventes de Blizzard, mises à jour environ toutes les heures. L'or par victime additionne, pour chaque composant d'artisanat, la chance multipliée par la pile moyenne et par le prix. L'équipement, les recettes et les gemmes ne sont pas inclus (leurs prix varient trop), ni le temps que prend une victime.</p>
<p>L'addon GoldScout en fait de l'or par heure pour votre personnage, et utilise vos propres analyses de l'hôtel des ventes quand elles sont plus récentes.</p>
<p class=small>%s</p>
"""

FR = {
    # -- words ----------------------------------------------------------------
    "Mob": "Monstre",
    "Mobs": "Monstres",
    "Item": "Objet",
    "Zone": "Zone",
    "Level": "Niveau",
    "Levels": "Niveaux",
    "Home": "Accueil",
    "Goal": "Objectif",
    "Next": "Suivant",
    "Solid": "Fiable",
    "Community goals": "Objectifs de la communauté",
    "Players sharing data": "Joueurs qui partagent des données",
    "Kills recorded": "Victimes enregistrées",
    "Mobs with solid drop rates (%d+ kills)": "Monstres avec des taux de butin fiables (%d+ victimes)",
    "%s of %s": "%s sur %s",
    "<b>%s</b> of %s": "<b>%s</b> sur %s",
    "<b class=done>%s</b> of %s": "<b class=done>%s</b> sur %s",
    "%d day left": "%d jour restant",
    "%d days left": "%d jours restants",
    "today": "aujourd'hui",
    "Goals for everyone sharing data, by %s (%s). Every player who adds the companion and every kill moves them.":
        "Des objectifs pour tous ceux qui partagent des données, d'ici le %s (%s). Chaque joueur qui ajoute "
        "GoldScout Companion et chaque victime les font avancer.",
    "The goals for %s, and how far everyone got.": "Les objectifs pour le %s, et où nous en sommes arrivés.",
    "Every goal for %s reached. Thank you, everyone who shares!":
        "Tous les objectifs pour le %s sont atteints. Merci à tous ceux qui partagent !",
    "Price": "Prix",
    "Kills": "Victimes",
    "kills": "victimes",
    "Catch": "Prise",
    "Catches": "Prises",
    "catches": "prises",
    "Pickpockets": "Vols",
    "pickpockets": "vols",
    "Where": "Où",
    "Chance": "Chance",
    "Reagent": "Composant",
    "Recorded": "Enregistrées",
    "Fishing": "Pêche",
    "low": "faible",
    "fair": "moyenne",
    "good": "bonne",
    "high": "élevée",
    " and ": " et ",
    "none yet": "aucun pour l'instant",
    "nobody yet": "personne pour l'instant",
    "fished up": "pêché",
    "Complete": "Terminée",
    "Open water": "Eau libre",
    "Fishing pool": "Banc de poissons",
    "Fishing pool %d": "Banc de poissons %d",
    "Item %d": "Objet %d",
    "Mob %d": "Monstre %d",
    "level %s": "niveau %s",
    "Level %s": "Niveau %s",
    "Levels %d-%d": "Niveaux %d-%d",
    "levels %d-%d": "niveaux %d-%d",
    " level %d": " de niveau %d",
    " level %d-%d": " de niveau %d-%d",
    "%d mob": "%d monstre",
    "%d mobs": "%d monstres",
    "%d source": "%d source",
    "%d sources": "%d sources",
    "%d+ kills": "%d+ victimes",
    "Crafting reagent": "Composant d'artisanat",
    "Rare drop": "Butin rare",
    "a crafting reagent": "un composant d'artisanat",
    "a rare world drop": "un butin rare du monde",
    "an item": "un objet",
    "No name recorded in this language yet": "Aucun nom français enregistré pour l'instant",

    # -- headings and table heads ---------------------------------------------
    "By zone": "Par zone",
    "By level": "Par niveau",
    "Zone goal": "Objectif de la zone",
    "Zone goals": "Objectifs des zones",
    "Avg. stack": "Pile moy.",
    "Other drops": "Autres butins",
    "Best source": "Meilleure source",
    "Dropped by": "Donné par",
    "Pickpocketed from": "Volé sur",
    "Other levels": "Autres niveaux",
    "Almost there": "Presque",
    "Lowest skill": "Compétence min.",
    "Best catches": "Meilleures prises",
    "Pickpocketing": "Vol à la tire",
    "Per kill": "Par victime",
    "Per catch": "Par prise",
    "Per pickpocket": "Par vol",
    "Gold per hour": "Or par heure",
    "Gold per kill": "Or par victime",
    "Gold per catch": "Or par prise",
    "Gold per pickpocket": "Or par vol",
    "Where it drops": "Où il tombe",
    "Farms by level": "Farm par niveau",
    "Crafting reagents": "Composants d'artisanat",
    "Best reagent drops": "Meilleurs composants",
    "Where on the map": "Où sur la carte",
    "Where to find it": "Où le trouver",
    "Fishing for gold": "Pêcher pour l'or",
    "Fishing elsewhere": "Pêcher ailleurs",
    "Zones at these levels": "Zones de ces niveaux",
    "How drop rates work": "Comment fonctionnent les taux de butin",
    "How these numbers work": "D'où viennent ces chiffres",
    "Contributor leaderboard": "Classement des contributeurs",
    "Where data is needed": "Où il manque des données",
    "Where GoldScout needs data": "Où GoldScout a besoin de données",
    "Farm these at the same time": "À farmer en même temps",
    "Closest to solid:": "Les plus proches d'être fiables :",
    "Lowest price:": "Prix le plus bas :",
    "Help fill this in.": "Aidez à compléter.",
    "Auction prices for": "Prix de l'hôtel des ventes pour",
    "Realm type and faction": "Type de royaume et faction",
    "More farms in %s": "Plus de farms dans %s",
    "Fishing in %s": "Pêche dans %s",
    "Farming in %s": "Farm dans %s",
    "Gold farms for %s": "Farm d'or pour les %s",
    "Crafting reagents in %s": "Composants d'artisanat dans %s",

    # -- short phrases ----------------------------------------------------------
    "Around %s": "Vers %s",
    "Around %s: looted %s here": "Vers %s : ramassé %s fois ici",
    "Most around <b>%s</b>.": "Surtout vers <b>%s</b>.",
    "%s gives %s.": "%s donne %s.",
    "%s catches %s": "%s prises %s",
    "%s on %s of catches": "%s dans %s des prises",
    "%d kills recorded": "%d victimes enregistrées",
    "%s kills recorded %s": "%s victimes enregistrées %s",
    "%d of %d mobs solid": "%d sur %d monstres fiables",
    "%d more mob to %d%%": "encore %d monstre pour %d %%",
    "%d more mobs to %d%%": "encore %d monstres pour %d %%",
    "%d kills, <b>%d to go</b>": "%d victimes, <b>encore %d</b>",
    "lowest skill seen %d": "compétence la plus basse vue : %d",
    "about %s a catch, %s an hour*": "environ %s par prise, %s par heure*",
    "Zone · %d mob": "Zone · %d monstre",
    "Zone · %d mobs": "Zone · %d monstres",
    "Fishing · %s catches": "Pêche · %s prises",
    "Farms by level · %d mobs": "Farm par niveau · %d monstres",
    "All %d farm for %s": "%d farm pour les %s",
    "All %d farms for %s": "Les %d farms pour les %s",
    " and %d other mob": " et %d autre monstre",
    " and %d other mobs": " et %d autres monstres",
    ", and %d other zone": " et %d autre zone",
    ", and %d other zones": " et %d autres zones",
    ", dropping %d crafting reagent": ", qui donnent %d composant d'artisanat",
    ", dropping %d crafting reagents": ", qui donnent %d composants d'artisanat",
    "Its best source, %s,": "Sa meilleure source, %s,",
    "Its best spot, %s in %s,": "Son meilleur endroit, %s dans %s,",
    "95%% likely between these, from %d recorded": "entre ces valeurs avec 95 %% de certitude, sur %d enregistrées",
    "Map of %s: where players found %s": "Carte de %s : où les joueurs ont trouvé %s",
    "Map of %s: where players looted %s": "Carte de %s : où les joueurs ont ramassé %s",
    "Map art &copy; Blizzard Entertainment.": "Illustration de la carte &copy; Blizzard Entertainment.",
    "Faint squares on a grid are where players have looted anything else in the zone.":
        "Les carrés pâles de la grille montrent où les joueurs ont ramassé tout le reste dans la zone.",

    # -- sentences ----------------------------------------------------------------
    "No drops recorded yet.": "Aucun butin enregistré pour l'instant.",
    "No mobs have enough kills recorded yet.": "Aucun monstre n'a encore assez de victimes enregistrées.",
    "No fishing recorded yet.": "Aucune pêche enregistrée pour l'instant.",
    "Chance per pickpocket, over %d attempts.": "Chance par vol, sur %d tentatives.",
    "Other items from the same mobs and fishing spots.": "Autres objets des mêmes monstres et lieux de pêche.",
    "Turn on JavaScript to see current auction prices.":
        "Activez JavaScript pour voir les prix actuels de l'hôtel des ventes.",
    "Auction data from the Blizzard Entertainment Game Data API. GoldScout is not affiliated with or endorsed by "
    "Blizzard.": "Données de l'hôtel des ventes issues de la Game Data API de Blizzard Entertainment. GoldScout "
                 "n'est ni affilié à Blizzard ni approuvé par Blizzard.",
    "Zone champions: the players with the most kills here.":
        "Champions de la zone : les joueurs avec le plus de victimes ici.",
    "Named only if they choose it in GoldScout Companion.": "Nommés seulement s'ils le choisissent dans GoldScout Companion.",
    "Mobs a few kills from solid rates, the closest first.":
        "Monstres à quelques victimes de taux fiables, les plus proches d'abord.",
    "Chance is how often players got the item per kill; the small numbers are the range it is 95% likely to be in, "
    "which narrows as more kills are recorded. Counted in WoW Forever only: no Classic Era data is mixed in.":
        "La chance indique à quelle fréquence les joueurs ont obtenu l'objet par victime ; les petits nombres sont "
        "l'intervalle qui la contient avec une certitude de 95 %, qui se resserre à mesure que des victimes sont "
        "enregistrées. Compté dans WoW Forever uniquement : aucune donnée de Classic Era n'est mélangée.",
    "Chance is how often players got the item per catch; the small numbers are the range it is 95% likely to be in, "
    "which narrows as more catches are recorded. Counted in WoW Forever only: no Classic Era data is mixed in.":
        "La chance indique à quelle fréquence les joueurs ont obtenu l'objet par prise ; les petits nombres sont "
        "l'intervalle qui la contient avec une certitude de 95 %, qui se resserre à mesure que des prises sont "
        "enregistrées. Compté dans WoW Forever uniquement : aucune donnée de Classic Era n'est mélangée.",
    "Every number here comes from players looting in game. Install <a href=\"%s\">GoldScout</a> and add "
    "<a href=\"%s\">GoldScout Companion</a>: it brings auction prices into the game every hour without "
    "scanning, and shares what you loot automatically. More players, better data for everyone. <a href=\"%s\">See "
    "where data is needed most</a>.":
        "Chaque chiffre ici vient de joueurs qui ramassent du butin en jeu. Installez <a href=\"%s\">GoldScout</a> et "
        "ajoutez <a href=\"%s\">GoldScout Companion</a> : il apporte les prix de l'hôtel des ventes dans le jeu toutes "
        "les heures sans analyse, et partage automatiquement ce que vous ramassez. Plus de joueurs, de meilleures "
        "données pour tous. <a href=\"%s\">Voyez où il manque le plus de données</a>.",
    "%s has %s %s recorded so far, so the ranges are wide; %d more and its rates are solid.":
        "%s a %s %s enregistrées pour l'instant, donc les intervalles sont larges ; encore %d et ses taux seront "
        "fiables.",
    'Crafting reagents only, at how fast GoldScout players kill each mob, or %d kills an hour until enough kills are timed. In game, GoldScout works it out for your character.':
        "Composants d'artisanat uniquement, au rythme auquel les joueurs de GoldScout tuent chaque monstre, ou à %d victimes par heure tant que trop peu de victimes sont chronométrées. En jeu, GoldScout le calcule pour votre personnage.",
    'At how fast GoldScout players kill each mob, or %d kills an hour until enough kills are timed. In game, GoldScout works it out for your character and level.':
        'Au rythme auquel les joueurs de GoldScout tuent chaque monstre, ou à %d victimes par heure tant que trop peu de victimes sont chronométrées. En jeu, GoldScout le calcule pour votre personnage et votre niveau.',
    "At %d pickpockets an hour. In game, GoldScout works it out for your character, at your own pace and level.":
        "À %d vols par heure. En jeu, GoldScout le calcule pour votre personnage, à votre rythme et à votre niveau.",
    "At %d catches an hour in open water, half that at pools (finding the next one takes time).":
        "À %d prises par heure en eau libre, moitié moins sur les bancs de poissons (trouver le suivant prend du "
        "temps).",
    "At %d catches an hour in open water, half that at pools. Gray junk is left out.":
        "À %d prises par heure en eau libre, moitié moins sur les bancs de poissons. La camelote grise n'est pas "
        "comptée.",
    "At %d catches an hour in open water, half that at pools. Lowest skill is the lowest Fishing skill a player has "
    "caught there with.": "À %d prises par heure en eau libre, moitié moins sur les bancs de poissons. La compétence "
                          "min. est la compétence de pêche la plus basse avec laquelle un joueur a pêché ici.",
    "Brightest where players loot %s most: around <b>%s</b> in %s. Coordinates match the in-game map.":
        "Plus lumineux là où les joueurs ramassent le plus souvent %s : vers <b>%s</b> dans %s. Les coordonnées "
        "correspondent à la carte du jeu.",
    "Brightest where the most %s turned up: squares where players looted or fished more of it. Coordinates match "
    "the in-game map.": "Plus lumineux là où %s est le plus souvent apparu : les carrés où les joueurs en ont ramassé "
                       "ou pêché le plus. Les coordonnées correspondent à la carte du jeu.",
    "Fishing here too: see <a href=\"%s\">what players catch in %s</a>.":
        "On pêche aussi ici : voyez <a href=\"%s\">ce que les joueurs pêchent dans %s</a>.",
    "Mobs to farm here too: see <a href=\"%s\">farming in %s</a>.":
        "Il y a aussi des monstres à farmer ici : voyez <a href=\"%s\">le farm dans %s</a>.",
    "<a href=\"%s\">The best fishing spots for gold</a>, by zone.":
        "<a href=\"%s\">Les meilleurs lieux de pêche pour l'or</a>, par zone.",

    # -- mob pages --------------------------------------------------------------
    "%s is a level %s mob in %s in WoW Forever.": "%s est un monstre de niveau %s présent dans %s, dans WoW Forever.",
    "%s is a level %s mob in WoW Forever.": "%s est un monstre de niveau %s dans WoW Forever.",
    "%s is a mob in %s in WoW Forever.": "%s est un monstre présent dans %s, dans WoW Forever.",
    "%s is a mob in WoW Forever.": "%s est un monstre de WoW Forever.",
    "GoldScout players have recorded %s kill.": "Les joueurs de GoldScout ont enregistré %s victime.",
    "GoldScout players have recorded %s kills.": "Les joueurs de GoldScout ont enregistré %s victimes.",
    "Its most common crafting reagent is %s (%s of kills).":
        "Son composant d'artisanat le plus courant est %s (dans %s des victimes).",
    "Its most common drop is %s (%s of kills).": "Son butin le plus courant est %s (dans %s des victimes).",
    "Its crafting reagents are worth about <b data-value=\"%s\">%s</b> per kill at current prices.":
        "Ses composants d'artisanat valent environ <b data-value=\"%s\">%s</b> par victime aux prix actuels.",
    "Its drops are worth about <b data-value=\"%s\">%s</b> per kill at current prices.":
        "Son butin vaut environ <b data-value=\"%s\">%s</b> par victime aux prix actuels.",
    "%s drops and drop rates (WoW Forever)": "%s : butin et taux de butin (WoW Forever)",
    "%s drop rates in WoW Forever: %s, from %d kills recorded by GoldScout players.":
        "Taux de butin de %s dans WoW Forever : %s, sur %d victimes enregistrées par des joueurs de GoldScout.",
    "What %s drops in WoW Forever, with drop rates from %d kills recorded by GoldScout players.":
        "Ce que donne %s dans WoW Forever, avec des taux de butin issus de %d victimes enregistrées par des joueurs "
        "de GoldScout.",

    # -- item pages ---------------------------------------------------------------
    "%s is %s in WoW Forever.": "%s est %s dans WoW Forever.",
    "GoldScout players have looted it from %d mob;": "Les joueurs de GoldScout l'ont ramassé sur %d monstre ;",
    "GoldScout players have looted it from %d mobs;": "Les joueurs de GoldScout l'ont ramassé sur %d monstres ;",
    "GoldScout players have pickpocketed it from %d mob;": "Les joueurs de GoldScout l'ont volé sur %d monstre ;",
    "GoldScout players have pickpocketed it from %d mobs;": "Les joueurs de GoldScout l'ont volé sur %d monstres ;",
    "GoldScout players have fished it up in %d zone;": "Les joueurs de GoldScout l'ont pêché dans %d zone ;",
    "GoldScout players have fished it up in %d zones;": "Les joueurs de GoldScout l'ont pêché dans %d zones ;",
    "the best source is %s%s, which gave it on %s of %s kills.":
        "la meilleure source est %s%s, qui l'a donné dans %s des %s victimes.",
    "the best source is %s%s, which gave it on %s of %s pickpockets.":
        "la meilleure source est %s%s, qui l'a donné dans %s des %s vols.",
    "the best spot is %s in %s, which gave it on %s of %s catches.":
        "le meilleur endroit est %s dans %s, qui l'a donné dans %s des %s prises.",
    "It's also fished up in %d zone.": "On le pêche aussi dans %d zone.",
    "It's also fished up in %d zones.": "On le pêche aussi dans %d zones.",
    "%s drops from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot.":
        "%s tombe sur %s (%s)%s dans WoW Forever. Taux de butin calculés d'après le butin des joueurs de GoldScout.",
    "%s is pickpocketed from %s (%s)%s in WoW Forever. Drop rates counted from GoldScout players' loot.":
        "%s se vole sur %s (%s)%s dans WoW Forever. Taux de butin calculés d'après le butin des joueurs de "
        "GoldScout.",
    "Where to fish %s in WoW Forever: %s in %s (%s of catches)%s. Counted from GoldScout players' catches.":
        "Où pêcher %s dans WoW Forever : %s dans %s (%s des prises)%s. Calculé d'après les prises des joueurs de "
        "GoldScout.",
    "Where to farm %s (WoW Forever)": "Où farmer %s (WoW Forever)",
    "Where to fish %s (WoW Forever)": "Où pêcher %s (WoW Forever)",

    # -- zone pages and goals ---------------------------------------------------
    "GoldScout players have recorded %d%s mob in %s with enough kills for reliable drop rates":
        "Les joueurs de GoldScout ont enregistré %d monstre%s dans %s avec assez de victimes pour des taux de butin "
        "fiables",
    "GoldScout players have recorded %d%s mobs in %s with enough kills for reliable drop rates":
        "Les joueurs de GoldScout ont enregistré %d monstres%s dans %s avec assez de victimes pour des taux de butin "
        "fiables",
    "Where to farm gold in %s (WoW Forever)": "Où farmer de l'or dans %s (WoW Forever)",
    "Mobs to farm in %s, WoW Forever, and the crafting reagents they drop, from GoldScout players' loot.":
        "Monstres à farmer dans %s, WoW Forever, et les composants d'artisanat qu'ils donnent, d'après le butin des "
        "joueurs de GoldScout.",
    "<b>Goal reached:</b> every mob players have recorded in %s has solid drop rates. New mobs recorded here join "
    "the goal.": "<b>Objectif atteint :</b> chaque monstre enregistré dans %s a des taux de butin fiables. Les "
                 "nouveaux monstres enregistrés ici rejoignent l'objectif.",
    "Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far, past %d%%. Next milestone: %s.":
        "Chaque monstre d'ici avec des taux de butin fiables (%d+ victimes) : <b>%d sur %d</b> pour l'instant, plus "
        "de %d %%. Prochaine étape : %s.",
    "Every mob here with solid drop rates (%d+ kills): <b>%d of %d</b> so far. Next milestone: %s.":
        "Chaque monstre d'ici avec des taux de butin fiables (%d+ victimes) : <b>%d sur %d</b> pour l'instant. "
        "Prochaine étape : %s.",

    # -- level ranges and farms ---------------------------------------------------
    "Gold farms by level (WoW Forever)": "Farm d'or par niveau (WoW Forever)",
    "The best WoW Forever gold farms for every level range, ranked by gold per hour at current auction prices, from "
    "GoldScout players' loot.": "Les meilleurs farms d'or de WoW Forever pour chaque tranche de niveaux, classés par "
                               "or par heure aux prix actuels de l'hôtel des ventes, d'après le butin des joueurs de "
                               "GoldScout.",
    "Mobs GoldScout players have recorded at least %d kills of, with the crafting reagents they drop most often, "
    "ranked by gold per hour at current auction prices. Open a level range for every farm in it, a mob for every "
    "drop, or an item for everywhere it drops.":
        "Les monstres dont les joueurs de GoldScout ont enregistré au moins %d victimes, avec les composants "
        "d'artisanat qu'ils donnent le plus souvent, classés par or par heure aux prix actuels de l'hôtel des ventes. "
        "Ouvrez une tranche de niveaux pour voir chacun de ses farms, un monstre pour chacun de ses butins, ou un objet "
        "pour tous les endroits où il tombe.",
    "Best gold farms for %s (WoW Forever)": "Meilleurs farms d'or pour les %s (WoW Forever)",
    "%d mobs at %s that GoldScout players have recorded, from %s kills, ranked by what their crafting reagents are "
    "worth an hour at current auction prices. Pick your realm type and faction for your prices.":
        "%d monstres pour les %s enregistrés par les joueurs de GoldScout, sur %s victimes, classés selon ce que "
        "valent leurs composants d'artisanat par heure aux prix actuels de l'hôtel des ventes. Choisissez votre type "
        "de royaume et votre faction pour voir vos prix.",
    "The WoW Forever mobs worth farming at %s, ranked by gold per hour at current auction prices, from %s kills "
    "recorded by GoldScout players.":
        "Les monstres de WoW Forever qui valent le farm pour les %s, classés par or par heure aux prix actuels de "
        "l'hôtel des ventes, sur %s victimes enregistrées par des joueurs de GoldScout.",

    # -- fishing ------------------------------------------------------------------------
    "GoldScout players have recorded %s catches fishing in %s, WoW Forever.":
        "Les joueurs de GoldScout ont enregistré %s prises en pêchant dans %s, WoW Forever.",
    "The lowest Fishing skill seen catching here is %d.": "La compétence de pêche la plus basse vue ici est %d.",
    "Fishing in %s: catches and gold per hour (WoW Forever)": "Pêche dans %s : prises et or par heure (WoW Forever)",
    "What you catch fishing in %s, WoW Forever%s, from %s catches recorded by GoldScout players.":
        "Ce que vous pêchez dans %s, WoW Forever%s, d'après %s prises enregistrées par des joueurs de GoldScout.",
    "Best fishing spots for gold (WoW Forever)": "Meilleurs lieux de pêche pour l'or (WoW Forever)",
    "Where to fish for gold in WoW Forever: every zone ranked by gold per hour at current auction prices, from %s "
    "catches recorded by GoldScout players.":
        "Où pêcher pour l'or dans WoW Forever : chaque zone classée par or par heure aux prix actuels de l'hôtel des "
        "ventes, d'après %s prises enregistrées par des joueurs de GoldScout.",
    "Every zone GoldScout players have fished in WoW Forever, from %s catches, ranked by what the catch is worth an "
    "hour at current auction prices. Pick your realm type and faction for your prices.":
        "Chaque zone où les joueurs de GoldScout ont pêché dans WoW Forever, sur %s prises, classée selon ce que "
        "rapporte la pêche par heure aux prix actuels de l'hôtel des ventes. Choisissez votre type de royaume et "
        "votre faction pour voir vos prix.",

    # -- drop rates page ----------------------------------------------------------------
    "How GoldScout drop rates work": "Comment fonctionnent les taux de butin de GoldScout",
    "Where GoldScout's WoW Forever drop rates come from, what the chance and confidence mean, and how the data is "
    "checked.": "D'où viennent les taux de butin de GoldScout pour WoW Forever, ce que signifient la chance et la "
                "fiabilité, et comment les données sont vérifiées.",
    "fewer than 5 kills. A first look; expect it to change.": "moins de 5 victimes. Un premier aperçu ; cela changera.",
    "5 to 14 kills. Common drops are roughly right.": "de 5 à 14 victimes. Les butins courants sont à peu près justes.",
    "15 to 49 kills. Good for most drops.": "de 15 à 49 victimes. Bonne pour la plupart des butins.",
    "50 kills or more. Reliable, even for uncommon drops.":
        "50 victimes ou plus. Fiable, même pour les butins peu courants.",

    # -- data wanted ------------------------------------------------------------------------
    "Where GoldScout needs drop data (WoW Forever)": "Où GoldScout a besoin de données de butin (WoW Forever)",
    "The WoW Forever level ranges, zones and mobs with the least drop data recorded by GoldScout players, and how to "
    "help fill them in.": "Les tranches de niveaux, zones et monstres de WoW Forever avec le moins de données de butin "
                         "enregistrées par les joueurs de GoldScout, et comment aider à les compléter.",
    "Every drop rate on this site comes from GoldScout players' loot: %s kills so far, %d mobs with drop rates, "
    "%d of them with the %d+ kills that make a rate solid. Here's where it's thin. Farming any of these with GoldScout and the "
    "companion running fills it in for everyone.":
        "Chaque taux de butin de ce site vient du butin des joueurs de GoldScout : %s victimes pour l'instant, %d "
        "monstres avec des taux de butin, dont %d avec les %d+ victimes qui rendent un taux fiable. Voici où il en "
        "manque. Farmer l'un d'eux avec GoldScout et Companion lancés le complète pour tout le monde.",
    "The bar shows the share of mobs with %d+ kills (rated good); the brighter part has %d+ (rated high: solid).":
        "La barre montre la part de monstres avec %d+ victimes (bonne) ; la partie plus lumineuse en a %d+ (élevée : "
        "fiable).",
    "Each zone's goal: every mob players have recorded there with solid drop rates (%d+ kills), with milestones at "
    "10%%, 25%%, 50%% and 75%%. %d of %d zones complete, %d past a milestone. Least recorded first; zones nobody has "
    "looted in yet aren't listed.":
        "L'objectif de chaque zone : chaque monstre qui y est enregistré avec des taux de butin fiables (%d+ "
        "victimes), avec des étapes à 10 %%, 25 %%, 50 %% et 75 %%. %d sur %d zones terminées, %d ont passé une "
        "étape. Les moins enregistrées d'abord ; les zones où personne n'a encore ramassé de butin n'apparaissent pas.",
}
