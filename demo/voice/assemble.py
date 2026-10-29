import json,re,subprocess,difflib
LEAD,GAP=0.5,0.7
secs=json.load(open("sections.json")); words=json.load(open("words.json"))
dur=[float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"s{i}.mp3"],capture_output=True,text=True).stdout) for i in range(len(secs))]
NUM={"25":"twenty five","319":"three hundred and nineteen","63":"sixty three","11":"eleven","12":"twelve","3.1":"three one","3":"three"}
def norm(w):
    w=w.lower().strip(" .,?!—-\"'")
    return NUM.get(w,w)
def chunks(text,maxc=46):
    # sentences, then clauses (dash, colon, comma) kept with their punctuation, then balanced word splits
    out=[]
    for sent in re.split(r"(?<=[.?!])\s+",text):
        clauses=[c for c in re.split(r"(?<=[—:,])\s+",sent) if c]
        cur=""
        for c in clauses:
            if cur and len(cur)+1+len(c)<=maxc: cur+=" "+c
            else:
                if cur: out.append(cur)
                cur=c
        out.append(cur)
    res=[]
    for c in out:
        if len(c)<=maxc: res.append(c); continue
        ws=c.split(); k=-(-len(c)//maxc); target=len(c)/k; cur=""
        for w in ws:
            if cur and len(cur)+1+len(w)>target+6 and len(res_tail:=cur)>0: res.append(cur); cur=w
            else: cur=(cur+" "+w).strip()
        res.append(cur)
    return res
def ts(t):
    h,m=divmod(t,3600); m,s=divmod(m,60); return f"{int(h):02}:{int(m):02}:{int(s):02},{int(round((s%1)*1000)):03}"
srt=[];n=0;t0=LEAD;cues=[]
for i,x in enumerate(secs):
    aw=[w for w in words[str(i)]]
    a_tok=[];a_idx=[]
    for k,w in enumerate(aw):
        for t in norm(w["w"]).split(): a_tok.append(t); a_idx.append(k)
    cs=chunks(x["text"])
    s_tok=[];s_chunk=[]
    for ci,c in enumerate(cs):
        for w in c.split():
            for t in norm(w).split():
                if t: s_tok.append(t); s_chunk.append(ci)
    sm=difflib.SequenceMatcher(None,s_tok,a_tok,autojunk=False)
    st=[None]*len(s_tok); en=[None]*len(s_tok)
    for b in sm.get_matching_blocks():
        for j in range(b.size):
            w=aw[a_idx[b.b+j]]; st[b.a+j]=w["s"]; en[b.a+j]=w["e"]
    matched=sum(v is not None for v in st)
    for ci,c in enumerate(cs):
        ids=[k for k,cc in enumerate(s_chunk) if cc==ci and st[k] is not None]
        if not ids: raise SystemExit(f"section {i} chunk {ci} unaligned: {c}")
        a=min(st[k] for k in ids); b=max(en[k] for k in ids)
        cues.append([t0+a,t0+b,c])
    print(i,f"{matched}/{len(s_tok)} script tokens aligned")
    t0+=dur[i]+GAP
# close small gaps so captions do not flicker; keep each cue on screen until the next starts if gap < 0.6 s
for k in range(len(cues)-1):
    if cues[k+1][0]-cues[k][1]<0.6: cues[k][1]=cues[k+1][0]-0.02
with open("narration.srt","w") as f:
    for k,(a,b,c) in enumerate(cues,1): f.write(f"{k}\n{ts(a)} --> {ts(b)}\n{c}\n\n")
# audio: lead silence + sections with gaps, normalised to -16 LUFS
inp=[];flt=[]
for i in range(len(secs)): inp+=["-i",f"s{i}.mp3"]
parts="".join(f"[{i}:a]aresample=44100,apad=pad_dur={GAP if i<len(secs)-1 else 1.0}[a{i}];" for i in range(len(secs)))
cat="".join(f"[a{i}]" for i in range(len(secs)))+f"concat=n={len(secs)}:v=0:a=1,adelay={int(LEAD*1000)}:all=1,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
subprocess.run(["ffmpeg","-v","error","-y",*inp,"-filter_complex",parts+cat,"-map","[out]","-ar","44100","-b:a","192k","narration.mp3"],check=True)
print("cues",len(cues),"end",round(t0,2))
