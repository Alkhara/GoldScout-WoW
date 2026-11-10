-- Regional auction price estimates: the median lowest buyout per item across
-- each region's Alliance and Horde auction houses. Used only until you have
-- prices of your own (GoldScout/Prices.lua), and never after 30 days.
-- Written by tools/bundle_prices.py when a release is built.
-- Empty in git; release builds fill it in.
local _, ns = ...

ns.BUNDLED_PRICES = {
}
