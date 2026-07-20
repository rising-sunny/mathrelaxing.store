"""
fb_test_post_love.py — one-off: publish the LOVE math sticker as an organic
Facebook photo post. Two-step for safety:

  # 1) verify which Page the token targets (prints the name, posts NOTHING):
  cd /var/www/mathrelaxing.store && .venv/bin/python fb_test_post_love.py

  # 2) if the Page is correct, actually publish:
  cd /var/www/mathrelaxing.store && .venv/bin/python fb_test_post_love.py --post
"""
import sys
import asyncio

from routers.meta_ads import _marketing_access_token, _page_id, _graph_get
from services.meta_organic_service import publish_facebook_photo

IMAGE = "https://i.etsystatic.com/66586766/r/il/f90151/8271489940/il_fullxfull.8271489940_eg3f.jpg"
MESSAGE = (
    "All you need is… ❤️\U0001F4C8\n"
    "Graph these four equations and they literally spell L-O-V-E:\n"
    "y = 1/x   ·   x² + y² = 9   ·   y = |−2x|   ·   x = −3|sin y|\n\n"
    "The nerdiest way to say \"I love you\" \U0001F913\n"
    "Durable kiss-cut vinyl — perfect on a laptop or water bottle.\n\n"
    "\U0001F449 https://www.etsy.com/listing/4540433548/math-equation-sticker-all-you-need-is\n\n"
    "#MathArt #Sticker #NerdyGifts #Mathematics"
)


async def main():
    token = await _marketing_access_token()
    pid = _page_id()
    page = await _graph_get(f"/{pid}", token, {"fields": "name,link,fan_count"})
    print(f"Target Facebook Page: {page.get('name')}  (id {pid})")
    print(f"  link: {page.get('link')}   followers: {page.get('fan_count')}")
    if "--post" not in sys.argv:
        print("\nDRY RUN — nothing posted. If the Page is correct, re-run with:  --post")
        return
    print("\nPublishing the LOVE sticker photo…")
    post_id = await publish_facebook_photo(IMAGE, MESSAGE)
    print("SUCCESS! Facebook post id:", post_id)


if __name__ == "__main__":
    asyncio.run(main())
