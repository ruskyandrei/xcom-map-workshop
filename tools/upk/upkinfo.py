import struct, sys, collections, os

# lzo1x and decomp beside it, for load(): put on the path once, here
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class R:
    def __init__(s, b, o=0): s.b=b; s.o=o
    def i32(s): v=struct.unpack_from('<i',s.b,s.o)[0]; s.o+=4; return v
    def u32(s): v=struct.unpack_from('<I',s.b,s.o)[0]; s.o+=4; return v
    def u16(s): v=struct.unpack_from('<H',s.b,s.o)[0]; s.o+=2; return v
    def u64(s): v=struct.unpack_from('<Q',s.b,s.o)[0]; s.o+=8; return v
    def fstr(s):
        n=s.i32()
        if n==0: return ''
        if n>0:
            v=s.b[s.o:s.o+n-1].decode('latin1'); s.o+=n; return v
        n=-n; v=s.b[s.o:s.o+2*n-2].decode('utf-16le'); s.o+=2*n; return v

def summary(b):
    r=R(b)
    h={}
    h['tag']=hex(r.u32()); h['ver']=r.u16(); h['lic']=r.u16()
    h['headersize']=r.u32(); h['folder']=r.fstr(); h['flags']=hex(r.u32())
    h['namecount']=r.u32(); h['nameoff']=r.u32()
    h['expcount']=r.u32(); h['expoff']=r.u32()
    h['impcount']=r.u32(); h['impoff']=r.u32()
    h['dependsoff']=r.u32()
    h['ieguidsoff']=r.u32(); h['impguids']=r.u32(); h['expguids']=r.u32()
    h['thumboff']=r.u32()
    h['guid']=b[r.o:r.o+16].hex(); r.o+=16
    gc=r.u32(); h['gens']=[(r.u32(),r.u32(),r.u32()) for _ in range(gc)]
    h['engine']=r.u32(); h['cooker']=r.u32()
    h['compflags']=r.u32()
    cc=r.u32(); h['chunks']=[(r.u32(),r.u32(),r.u32(),r.u32()) for _ in range(cc)]
    h['pkgsource']=hex(r.u32())
    ac=r.u32(); h['addpkgs']=[r.fstr() for _ in range(ac)]
    return h

def tables(b,h):
    r=R(b,h['nameoff']); names=[]
    for _ in range(h['namecount']):
        names.append(r.fstr()); r.u64()
    def nm(r):
        i=r.i32(); n=r.i32(); s=names[i] if 0<=i<len(names) else '?%d'%i
        return s if n==0 else '%s_%d'%(s,n-1)
    r=R(b,h['impoff']); imps=[]
    for _ in range(h['impcount']):
        cp=nm(r); cn=nm(r); outer=r.i32(); on=nm(r)
        imps.append(dict(cpkg=cp,cls=cn,outer=outer,name=on))
    r=R(b,h['expoff']); exps=[]
    for _ in range(h['expcount']):
        ci=r.i32(); si=r.i32(); oi=r.i32(); on=nm(r); ai=r.i32(); of=r.u64(); ss=r.u32(); so=r.u32(); ef=r.u32()
        nc=r.u32(); r.o+=4*nc; r.o+=16; pf=r.u32()
        exps.append(dict(cls=ci,sup=si,outer=oi,name=on,arch=ai,size=ss,off=so,flags=of))
    return names,imps,exps

def objname(idx,imps,exps):
    if idx==0: return 'None'
    e=imps[-idx-1] if idx<0 else exps[idx-1]
    o=e['outer']
    return (objname(o,imps,exps)+'.' if o else '')+e['name']

def clsname(idx,imps,exps):
    if idx==0: return 'Class'
    if idx<0: return imps[-idx-1]['name']
    return exps[idx-1]['name']

def load(path, raw=False):
    """(the package's bytes, decoded when compressed, and its summary). `raw`: the bytes as they are in the file (the
    command line's --raw). A library function: it reads no command line and adds to sys.path once, when the module
    loads, not at every package (review finding 50)."""
    with open(path,'rb') as f: b=f.read()
    tag,block=struct.unpack_from('<II',b,0)
    if tag==0x9E2A83C1 and block==131072 and not raw:
        # a package the cooker compressed whole (the startup and script packages): one chunk, read and checked as
        # a map's are (decomp.read_chunk: its tag, block size and block table), each block of the size the table
        # gives (lzo1x raises ValueError on one cut short or of another length)
        import decomp
        _,_,_,blocks,at=decomp.read_chunk(b,0)
        b=bytes(decomp.decode_blocks(b,blocks,at))
        return b,summary(b)
    h=summary(b)
    if h['chunks'] and not raw:
        import decomp
        b,h=decomp.decompress_pkg(path)
    return b,h

if __name__=='__main__':
    b,h=load(sys.argv[1],raw='--raw' in sys.argv)
    mode=sys.argv[2] if len(sys.argv)>2 else 'summary'
    names,imps,exps=tables(b,h)
    if mode=='summary':
        for k,v in h.items():
            if k!='chunks': print(k,'=',v)
        print('chunks',len(h['chunks']))
        c=collections.Counter(clsname(e['cls'],imps,exps) for e in exps)
        print('export classes:'); [print('  ',n,k) for k,n in c.most_common(80)]
        pk=collections.Counter(objname(i['outer'],imps,exps).split('.')[0] if i['outer'] else i['name'] for i in imps)
        print('import top packages:'); [print('  ',n,k) for k,n in pk.most_common(40)]
    elif mode=='imports':
        for n,i in enumerate(imps): print(i['cls'], objname(-(n+1),imps,exps))
    elif mode=='exports':
        for n,e in enumerate(exps): print(clsname(e['cls'],imps,exps), objname(n+1,imps,exps), e['size'])
    elif mode=='names':
        print('\n'.join(names))
