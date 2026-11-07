# Community drop data

`submissions/` holds accepted `/gscout export` submissions, one file per
contributor, named after their numeric GitHub user ID. Each file is rebuilt
from validated data by `tools/data_bot.py`, never copied from the issue text.
A newer export from the same player replaces their file.

`tools/merge_data.py` combines these files into `GoldScout/Data_Community.lua`.
Contributions are covered by the [Contributor Terms](../docs/CONTRIBUTOR_TERMS.md).
Everything in this folder is covered by the [GoldScout Data License](../DATA_LICENSE.md),
not the MIT License.
