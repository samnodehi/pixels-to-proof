import json,sys,subprocess,numpy as np
def load(f):
    raw=subprocess.run(['ffmpeg','-v','error','-i',f,'-f','f32le','-ac','1','-ar','16000','-'],capture_output=True,check=True).stdout
    return np.frombuffer(raw,np.float32)
from faster_whisper import WhisperModel
m=WhisperModel("small.en",device="cpu",compute_type="int8")
out={}
for i in range(8):
    segs,_=m.transcribe(load(f"s{i}.mp3"),word_timestamps=True,beam_size=5)
    words=[{"w":w.word,"s":w.start,"e":w.end} for sg in segs for w in sg.words]
    out[i]=words
    print(i,"".join(w["w"] for w in words),flush=True)
json.dump(out,open("words.json","w"))
