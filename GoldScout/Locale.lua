-- Translations. GoldScout's text is written in English, and each piece of it
-- is looked up through L["English text"] (L = ns.L in every file). The Locale_*
-- files add a language's translations when the game runs in that language;
-- anything not translated yet shows in English.
--
-- Translators: keep every %s, %d, %g and %% (in the same order, or use %1$s
-- style positions where the language needs a different order), and every
-- |cff......|r colour code and \n line break.
local _, ns = ...

ns.LOCALE = (GetLocale and GetLocale()) or "enUS"

ns.L = setmetatable({}, {
  __index = function(_, text)
    return text
  end,
})

-- Called by each Locale_*.lua file: only the game's own language is kept.
function ns.AddLocale(locale, strings)
  if locale ~= ns.LOCALE then
    return
  end
  for english, translated in pairs(strings) do
    if type(translated) == "string" and translated ~= "" then
      rawset(ns.L, english, translated)
    end
  end
end
