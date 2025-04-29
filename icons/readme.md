A collection of python scripts for generating emoji required by the bot. (And some manual emoji)

The faction icons are copyright FFG and taken from their website.

The icon fonts are from https://github.com/geordanr/xwing-miniatures-font

To generate:
- Install Python 3.4 or later
- Run `pip install -r requirements.txt`
- Run `python generate_emoji.py`

To add to slack:
- Install https://chrome.google.com/webstore/detail/slack-emoji-tools/anchoacphlfbdomdlomnbbfhcmcdmjej
- Go to your slack's add emoji page
- Then drag all the files in the emoji folder into Bulk section. (You'll need to do it in a couple of goes, there's a 100 file limit)

To add to Discord:
- Install https://github.com/favware/discord-application-emojis-manager
- Use the "post" command to upload all the emoji in the emoji directory
- Use the "list" command redirected into a file to replace discord_emoji_id.json
- Remove the first line of non-json text from the output