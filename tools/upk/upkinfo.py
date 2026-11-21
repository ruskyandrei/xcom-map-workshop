import struct, sys, collections, os

# lzo1x and decomp beside it, for load(): put on the path once, here
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# A damaged or cut-short package is refused with a ValueError that says what was met and where, never read on (KB-9):
# a string longer than the bytes left, a count of entries that can't fit in them, a field past the end, a name index
# or an object reference out of range, an outer chain that loops. The checks sit where a count or a length is read,
# not on each field: these readers are on every package's path (a struct.error at the buffer's end is turned into the
# ValueError instead).

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
            if s.o+n>len(s.b): raise ValueError(_long(s,n))
            v=s.b[s.o:s.o+n-1].decode('latin1'); s.o+=n; return v
        n=-n
        if s.o+2*n>len(s.b): raise ValueError(_long(s,2*n))
        v=s.b[s.o:s.o+2*n-2].decode('utf-16le'); s.o+=2*n; return v

def _long(r, size):
    return 'a string of %d bytes at byte %d runs past the end of the package (%d bytes)' % (size, r.o-4, len(r.b))

def _room(r, count, size, what):
    """Refuses `count` entries of at least `size` bytes each from the reader's place when the bytes left can't hold
    them, before a loop reads them (a wild count is refused at once, not read until the buffer ends)."""
    if count and count*size > len(r.b)-r.o:
        raise ValueError('the package lists %d %s at byte %d, more than the %d bytes left can hold'
                         % (count, what, r.o, max(0, len(r.b)-r.o)))

def _cut(r, what):
    return ValueError('the package is cut short in %s: a field at byte %d runs past its end (%d bytes)'
                      % (what, r.o, len(r.b)))

def summary(b):
    r=R(b)
    h={}
    what='the summary'
    try:
        h['tag']=hex(r.u32()); h['ver']=r.u16(); h['lic']=r.u16()
        h['headersize']=r.u32(); h['folder']=r.fstr(); h['flags']=hex(r.u32())
        h['namecount']=r.u32(); h['nameoff']=r.u32()
        h['expcount']=r.u32(); h['expoff']=r.u32()
        h['impcount']=r.u32(); h['impoff']=r.u32()
        h['dependsoff']=r.u32()
        h['ieguidsoff']=r.u32(); h['impguids']=r.u32(); h['expguids']=r.u32()
        h['thumboff']=r.u32()
        h['guid']=b[r.o:r.o+16].hex(); r.o+=16
        gc=r.u32(); _room(r,gc,12,'generations'); what='the generations'
        h['gens']=[(r.u32(),r.u32(),r.u32()) for _ in range(gc)]
        what='the summary'
        h['engine']=r.u32(); h['cooker']=r.u32()
        h['compflags']=r.u32()
        cc=r.u32(); _room(r,cc,16,'chunks'); what='the chunk table'
        h['chunks']=[(r.u32(),r.u32(),r.u32(),r.u32()) for _ in range(cc)]
        what='the summary'
        h['pkgsource']=hex(r.u32())
        ac=r.u32(); _room(r,ac,4,'additional packages'); what='the additional packages'
        h['addpkgs']=[r.fstr() for _ in range(ac)]
    except (struct.error, IndexError):
        raise _cut(r, what) from None
    return h

def tables(b,h):
    r=R(b,h['nameoff']); names=[]
    _room(r,h['namecount'],12,'names')
    k=0
    try:
        for k in range(h['namecount']):
            names.append(r.fstr()); r.u64()
    except (struct.error, IndexError):
        raise _cut(r, 'name %d of %d' % (k+1, h['namecount'])) from None
    def nm(r):
        i=r.i32(); n=r.i32()
        if not 0<=i<len(names):
            raise ValueError('a name index %d at byte %d: the package has %d names' % (i, r.o-8, len(names)))
        s=names[i]
        return s if n==0 else '%s_%d'%(s,n-1)
    r=R(b,h['impoff']); imps=[]
    _room(r,h['impcount'],28,'imports')
    try:
        for k in range(h['impcount']):
            cp=nm(r); cn=nm(r); outer=r.i32(); on=nm(r)
            imps.append(dict(cpkg=cp,cls=cn,outer=outer,name=on))
    except (struct.error, IndexError):
        raise _cut(r, 'import %d of %d' % (k+1, h['impcount'])) from None
    r=R(b,h['expoff']); exps=[]
    _room(r,h['expcount'],68,'exports')
    try:
        for k in range(h['expcount']):
            ci=r.i32(); si=r.i32(); oi=r.i32(); on=nm(r); ai=r.i32(); of=r.u64(); ss=r.u32(); so=r.u32(); ef=r.u32()
            nc=r.u32(); r.o+=4*nc; r.o+=16; pf=r.u32()
            exps.append(dict(cls=ci,sup=si,outer=oi,name=on,arch=ai,size=ss,off=so,flags=of))
    except (struct.error, IndexError):
        raise _cut(r, 'export %d of %d' % (k+1, h['expcount'])) from None
    return names,imps,exps

def _out_of_range(what, idx, imps, exps):
    return ValueError('%s %d is out of range: the package has %d imports and %d exports'
                      % (what, idx, len(imps), len(exps)))

def objname(idx,imps,exps):
    """The object's path (outer names first, joined by dots). ValueError for a reference out of range, its own or an
    outer's, and for an outer chain that loops."""
    if idx==0: return 'None'
    if idx>0:
        if idx>len(exps): raise _out_of_range('object', idx, imps, exps)
        e=exps[idx-1]
    else:
        if -idx>len(imps): raise _out_of_range('object', idx, imps, exps)
        e=imps[-idx-1]
    name=e['name']; o=e['outer']
    if not o: return name
    steps=0; limit=len(imps)+len(exps)
    while o:
        if o>0:
            if o>len(exps): raise _out_of_range('the outer chain of object %d names object' % idx, o, imps, exps)
            e=exps[o-1]
        else:
            if -o>len(imps): raise _out_of_range('the outer chain of object %d names object' % idx, o, imps, exps)
            e=imps[-o-1]
        name=e['name']+'.'+name; o=e['outer']
        steps+=1
        if steps>limit: raise ValueError('object %d: its outer chain loops' % idx)
    return name

def clsname(idx,imps,exps):
    """The name of the class `idx` names; ValueError for a reference out of range."""
    if idx==0: return 'Class'
    if idx<0:
        if -idx>len(imps): raise _out_of_range('class', idx, imps, exps)
        return imps[-idx-1]['name']
    if idx>len(exps): raise _out_of_range('class', idx, imps, exps)
    return exps[idx-1]['name']

def load(path, raw=False):
    """(the package's bytes, decoded when compressed, and its summary). `raw`: the bytes as they are in the file (the
    command line's --raw). A library function: it reads no command line and adds to sys.path once, when the module
    loads, not at every package (review finding 50). A damaged package is a ValueError (KB-9)."""
    with open(path,'rb') as f: b=f.read()
    if len(b)<8: raise ValueError('%s: %d bytes, too few for a package' % (path, len(b)))
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
