"""Bounded structural Liberty cell extraction; never edits a retained model.

This is not a Liberty semantic verifier. Yosys must import every retained cell,
link the actual design and validate functional closure before any proof.
"""
import hashlib,re

HEADER=re.compile(rb'(library|cell)\s*\(\s*("[A-Za-z_][A-Za-z0-9_$]*"|[A-Za-z_][A-Za-z0-9_$]*)\s*\)\s*\{')
IDENT=re.compile(rb'[A-Za-z_][A-Za-z0-9_]*')

def _cells(source):
    if not isinstance(source,bytes) or not 1<=len(source)<=16*1024*1024:raise ValueError('HOLD Liberty input budget/type')
    i=depth=roots=parens=0;active=None;cells={};n=len(source)
    while i<n:
        c=source[i]
        if c in b' \t\r\n\f\v':i+=1;continue
        if source[i:i+2]==b'//':
            end=source.find(b'\n',i+2);i=n if end<0 else end+1;continue
        if source[i:i+2]==b'/*':
            end=source.find(b'*/',i+2)
            if end<0:raise ValueError('HOLD unterminated Liberty comment')
            i=end+2;continue
        if c==34:
            if depth==0:raise ValueError('HOLD text outside Liberty library')
            i+=1
            while i<n:
                if source[i]==92:i+=2;continue
                if source[i]==34:i+=1;break
                i+=1
            else:raise ValueError('HOLD unterminated Liberty string')
            if i>n:raise ValueError('HOLD unterminated Liberty escape')
            continue
        token=IDENT.match(source,i)
        if token:
            word=token.group()
            if word==b'library' and depth==0:
                header=HEADER.match(source,i)
                if roots or not header:raise ValueError('HOLD unsupported/multiple Liberty library')
                roots=depth=1;i=header.end();continue
            if word==b'cell' and parens==0:
                header=HEADER.match(source,i)
                if depth!=1 or not header:raise ValueError('HOLD unsupported/nested Liberty cell')
                name=header.group(2).strip(b'"').decode('ascii')
                if name in cells:raise ValueError('HOLD duplicate Liberty cell '+name)
                active=(name,i);depth=2;i=header.end();continue
            if depth==0:raise ValueError('HOLD text outside Liberty library')
            i=token.end();continue
        if depth==0:raise ValueError('HOLD text outside Liberty library')
        if c==40:
            parens+=1
            if parens>64:raise ValueError('HOLD Liberty parenthesis budget')
        elif c==41:
            if parens==0:raise ValueError('HOLD unmatched Liberty closing parenthesis')
            parens-=1
        elif c==123:
            if depth==0 or depth>=64 or parens:raise ValueError('HOLD unsupported Liberty nesting')
            depth+=1
        elif c==125:
            if depth==0 or parens:raise ValueError('HOLD unmatched Liberty closing brace')
            depth-=1
            if depth==1 and active:
                name,start=active;cells[name]=(start,i+1);active=None
                if len(cells)>4096:raise ValueError('HOLD Liberty cell budget')
        elif depth==0:raise ValueError('HOLD text outside Liberty library')
        i+=1
    if roots!=1 or depth or parens or active or not cells:raise ValueError('HOLD incomplete Liberty structure')
    return cells

def subset_liberty(source,used):
    if not isinstance(used,(set,frozenset)) or not 1<=len(used)<=512 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]{0,127}',x) for x in used):raise ValueError('HOLD invalid Liberty selection')
    cells=_cells(source);missing=sorted(used-cells.keys())
    if missing:raise ValueError('HOLD required Liberty cells absent: '+', '.join(missing))
    parts=[];cursor=0;selected={}
    for name,(start,end) in sorted(cells.items(),key=lambda item:item[1][0]):
        parts.append(source[cursor:start]);body=source[start:end]
        if name in used:
            parts.append(body);selected[name]={'start_byte':start,'end_byte':end,'bytes':end-start,'sha256':hashlib.sha256(body).hexdigest()}
        cursor=end
    parts.append(source[cursor:]);derived=b''.join(parts)
    check=_cells(derived)
    if set(check)!=set(used) or any(hashlib.sha256(derived[a:b]).hexdigest()!=selected[name]['sha256'] for name,(a,b) in check.items()):raise ValueError('HOLD derived Liberty identity/coverage')
    return derived,{'schema':'verieda.liberty-selection.v1','source_sha256':hashlib.sha256(source).hexdigest(),'derived_sha256':hashlib.sha256(derived).hexdigest(),'selected_cells':selected,'omitted_cells':sorted(cells.keys()-used),'model_gate':'NOT_IMPORTED','scope':'only unused top-level cell groups removed; retained groups and other bytes unchanged; no semantic proof'}
