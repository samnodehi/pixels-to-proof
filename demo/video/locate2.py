import asyncio, json
from playwright.async_api import async_playwright
from locate import settle, boxes, URL
async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
        await pg.goto(URL); await settle(pg)
        await pg.get_by_text("Run ledger").click(); await settle(pg)
        n = await pg.evaluate("(()=>{let n=0;for(const d of document.querySelectorAll('div')){if(d.style.maxHeight==='520px'){d.style.maxHeight='none';d.id='ledgerbox';n++;}}return n;})()")
        print("ledger boxes", n)
        await pg.wait_for_timeout(500)
        tab = pg.locator("#ledgerbox table").first
        await tab.screenshot(path="shots/ledger_table.png")
        tb = await tab.bounding_box()
        rows = await boxes(pg, "#ledgerbox table tr")
        out["ledger"] = {"table": tb, "rows": [[r[0] - tb["x"], r[1] - tb["y"], r[2], r[3], r[4]] for r in rows]}
        await pg.get_by_role("tab", name="Breadth").click(); await settle(pg)
        out["breadth_rows"] = await boxes(pg, "table tr")
        await b.close()
    json.dump(out, open("boxes2.json", "w"))
asyncio.run(main())
