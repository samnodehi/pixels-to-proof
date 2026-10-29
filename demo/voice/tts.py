import json,sys,urllib.request,os
env={}
for l in open(os.environ.get("P2P_ENV_FILE",".meta.env")):
    if "=" in l and not l.startswith("#"):
        k,v=l.strip().split("=",1); env[k]=v.strip().strip('"')
secs=json.load(open("sections.json"))
for i in [int(a) for a in sys.argv[1:]]:
    body=json.dumps({"model":"elevenlabs/eleven-v4","input":secs[i]["text"],"voice":"daniel","response_format":"mp3"}).encode()
    req=urllib.request.Request("https://openrouter.ai/api/v1/audio/speech",data=body,headers={"Content-Type":"application/json","Authorization":"Bearer "+env["OPENROUTER_API_KEY"]})
    try:
        r=urllib.request.urlopen(req,timeout=180)
        data=r.read(); open(f"s{i}.mp3","wb").write(data)
        print(i,r.headers.get("Content-Type"),len(data),r.headers.get("X-Generation-Id"))
    except urllib.error.HTTPError as e:
        print(i,"HTTP",e.code,e.read()[:300])
