import asyncio, json
from playwright.async_api import async_playwright
URL="http://127.0.0.1:7861/"
async def settle(pg):
    await pg.wait_for_timeout(1500)
    for _ in range(60):
        if await pg.locator("text=processing").count()==0: break
        await pg.wait_for_timeout(500)
    await pg.wait_for_timeout(1500)
JS="""(args)=>{const [sel,txt]=args;const out=[];for(const el of document.querySelectorAll(sel)){if(txt===null||el.innerText.includes(txt)){const r=el.getBoundingClientRect();out.push([r.x+scrollX,r.y+scrollY,r.width,r.height,el.innerText.slice(0,80)]);}}return out;}"""
async def boxes(pg,sel,txt=None): return await pg.evaluate(JS,[sel,txt])
TJS="""(txt)=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;const out=[];
while(n=w.nextNode()){const i=n.textContent.indexOf(txt);if(i>=0){const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+txt.length);
for(const q of r.getClientRects()){if(q.width>0)out.push([q.x+scrollX,q.y+scrollY,q.width,q.height]);}}}return out;}"""
async def tbox(pg,txt): return await pg.evaluate(TJS,txt)
async def main():
    B={}
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":1280,"height":720},device_scale_factor=2)
        await pg.goto(URL); await settle(pg)
        B["beetle"]={"tables":await boxes(pg,"table"),"verdict":await boxes(pg,"div[style*='border-left:6px']"),
            "intro":await boxes(pg,"em","No number in a verdict"),"handsoff":await boxes(pg,"p","Hands-off"),
            "header":await boxes(pg,"h3"),"workdone":await boxes(pg,"p","Work done"),"recorded":await boxes(pg,"p","RECORDED RUN"),
            "rows":await boxes(pg,"tr"),"th":await boxes(pg,"th"),"cardlines":await boxes(pg,"div[style*='border-left:6px'] > div"),"t_handsoff":await tbox(pg,"Hands-off"),"t_rule":await tbox(pg,"No number in a verdict is written by a language model"),"t_proposes":await tbox(pg,"proposes")}
        await pg.screenshot(path="shots/beetle_full.png",full_page=True)
        await pg.get_by_text("Run ledger").click(); await settle(pg)
        B["ledger"]={"rows":await boxes(pg,"tr")}
        await pg.screenshot(path="shots/beetle_ledger_open.png",full_page=True)
        await pg.reload(); await settle(pg)
        await pg.get_by_label("Paper").click(); await pg.wait_for_timeout(800)
        await pg.get_by_role("option",name="Peacock",exact=False).first.click(); await settle(pg)
        B["peacock"]={"tables":await boxes(pg,"table"),"verdict":await boxes(pg,"div[style*='border-left:6px']"),"rows":await boxes(pg,"tr"),"th":await boxes(pg,"th"),"cardlines":await boxes(pg,"div[style*='border-left:6px'] > div")}
        await pg.screenshot(path="shots/peacock_full.png",full_page=True)
        await pg.get_by_role("tab",name="Breadth").click(); await settle(pg)
        B["breadth"]={"h2":await boxes(pg,"h2"),"h3":await boxes(pg,"h3"),"tables":await boxes(pg,"table"),"h1":await boxes(pg,"h1"),"strong":await boxes(pg,"p","Totals")}
        await pg.screenshot(path="shots/breadth_full.png",full_page=True)
        await pg.get_by_role("tab",name="Calibration").click(); await settle(pg)
        B["calib"]={"tables":await boxes(pg,"table"),"h1":await boxes(pg,"h1"),"summary":await boxes(pg,"p","caught 4")}
        await pg.screenshot(path="shots/calib_full.png",full_page=True)
        await b.close()
    json.dump(B,open("boxes.json","w"),indent=0)
if __name__ == "__main__":
    asyncio.run(main())
