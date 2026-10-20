"""Strict, non-executing comparison of a documented exported-SDC profile.

This is not a Tcl interpreter or native timing-coverage certificate. Unsupported
constructs are UNKNOWN, including source/eval/variables, wildcards and exceptions.
"""
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json

class Unsupported(ValueError):pass

def tokens(text):
    text=text.replace('\\\r\n',' ').replace('\\\n',' ')
    if '\\' in text:raise Unsupported('backslash substitutions are unsupported')
    commands=[];words=[];word='';brace=bracket=0;quote=False;i=0
    while i<len(text):
        c=text[i]
        if c=='#' and not word and not words and not brace and not bracket and not quote:
            i=text.find('\n',i)
            if i<0:break
            continue
        if brace:
            word+=c
            if c=='{':brace+=1
            if c=='}':brace-=1
        elif c=='{' and not quote:brace=1;word+=c
        elif c=='}' and not quote:raise Unsupported('unmatched brace')
        elif c=='"':quote=not quote;word+=c
        elif c=='[' and not quote:bracket+=1;word+=c
        elif c==']' and not quote:
            bracket-=1;word+=c
            if bracket<0:raise Unsupported('unmatched bracket')
        elif not bracket and not quote and (c.isspace() or c==';'):
            if word:words.append(word);word=''
            if c in '\r\n;':
                if words:commands.append(words);words=[]
        else:word+=c
        i+=1
    if brace or bracket or quote:raise Unsupported('unclosed Tcl grouping')
    if word:words.append(word)
    if words:commands.append(words)
    return commands

def literal(value):
    braced=value.startswith('{') and value.endswith('}')
    quoted=value.startswith('"') and value.endswith('"')
    out=value[1:-1] if braced or quoted else value
    if '$' in out or '{' in out or '}' in out or '"' in out or (not braced and ('[' in out or ']' in out)):
        raise Unsupported('dynamic or unsupported literal')
    if any(ord(c)<32 for c in out):raise Unsupported('control character in literal')
    return out

def number(value):
    try:
        v=literal(value)
        if len(v)>128:raise Unsupported('numeric token size exceeded')
        n=Decimal(v)
    except (InvalidOperation,ValueError):raise Unsupported('nonliteral numeric value')
    if not n.is_finite():raise Unsupported('nonfinite numeric value')
    if not n:return '0'
    sign,digits,exponent=n.as_tuple();digits=list(digits)
    while len(digits)>1 and digits[-1]==0:digits.pop();exponent+=1
    if len(digits)>18 or n.copy_abs()>Decimal('1e12') or n.adjusted() < -18:raise Unsupported('out-of-profile numeric precision/range')
    return str(Decimal((sign,tuple(digits),exponent)))

def selector(value,kind):
    if not (value.startswith('[') and value.endswith(']')):raise Unsupported('explicit collection required')
    rows=tokens(value[1:-1])
    if len(rows)!=1 or len(rows[0])!=2 or rows[0][0]!='get_'+kind:raise Unsupported('unsupported collection expression')
    objects=literal(rows[0][1]).split()
    if not objects or len(objects)!=len(set(objects)):raise Unsupported('empty or duplicate collection')
    if any('*' in n or '?' in n for n in objects):raise Unsupported('wildcard requires native object inventory')
    return tuple(sorted(objects))

def options(words,values,flags):
    result={};tail=[];i=0
    while i<len(words):
        w=words[i]
        if w in result:raise Unsupported('duplicate option '+w)
        if w in values:
            if i+1==len(words):raise Unsupported('missing option value')
            result[w]=words[i+1];i+=2
        elif w in flags:result[w]=True;i+=1
        elif w.startswith('-'):raise Unsupported('unsupported option '+w)
        else:tail.append(w);i+=1
    return result,tail

def normalize(text):
    clocks={};delays={};latency={};propagated=set();design=None
    for words in tokens(text):
        cmd,args=words[0],words[1:]
        if cmd!='current_design' and design is None:raise Unsupported('current_design must precede constraints')
        if cmd=='current_design':
            if len(args)!=1 or design is not None:raise Unsupported('ambiguous current_design')
            design=literal(args[0])
        elif cmd=='create_clock':
            opt,tail=options(args,{'-name','-period','-waveform'},set())
            if '-name' not in opt or '-period' not in opt or len(tail)>1:raise Unsupported('clock name/period/target missing or ambiguous')
            name=literal(opt['-name']);period=number(opt['-period'])
            if not name or Decimal(period)<=0 or name in clocks:raise Unsupported('invalid or duplicate clock')
            source=selector(tail[0],'ports') if tail else ()
            if len(source)>1 or any(source and source==c['source'] for c in clocks.values()):raise Unsupported('multiple clocks or sources require native evaluation')
            with localcontext() as ctx:
                ctx.prec=40
                wave=literal(opt['-waveform']).split() if '-waveform' in opt else ['0',str(Decimal(period)/2)]
            if len(wave)!=2:raise Unsupported('unsupported waveform')
            wave=tuple(number(x) for x in wave)
            if not Decimal(0)<=Decimal(wave[0])<Decimal(wave[1])<Decimal(period):raise Unsupported('unsupported clock edge range')
            clocks[name]={'period':period,'waveform':wave,'source':source}
        elif cmd=='set_propagated_clock':
            if len(args)!=1:raise Unsupported('propagated clock arguments')
            selected=selector(args[0],'clocks')
            if not set(selected).issubset(clocks):raise Unsupported('unresolved propagated clock')
            if propagated.intersection(selected):raise Unsupported('duplicate propagation declaration')
            propagated.update(selected)
        elif cmd=='set_clock_latency':
            if len(args)!=2:raise Unsupported('latency flags require native evaluation')
            for clock in selector(args[1],'clocks'):
                if clock not in clocks:raise Unsupported('unresolved latency clock')
                if clock in latency:raise Unsupported('duplicate network latency')
                latency[clock]=number(args[0])
        elif cmd in ('set_input_delay','set_output_delay'):
            if not args:raise Unsupported('missing I/O delay')
            delay=number(args[0]);opt,tail=options(args[1:],{'-clock'},{'-add_delay','-min','-max'})
            if '-clock' not in opt or len(tail)!=1 or ('-min' in opt and '-max' in opt):raise Unsupported('ambiguous I/O delay options')
            clock=selector(opt['-clock'],'clocks') if opt['-clock'].startswith('[') else (literal(opt['-clock']),)
            if len(clock)!=1:raise Unsupported('multiple I/O clocks')
            if clock[0] not in clocks:raise Unsupported('unresolved I/O clock')
            modes=['min'] if '-min' in opt else ['max'] if '-max' in opt else ['min','max']
            for port in selector(tail[0],'ports'):
                for mode in modes:
                    key=(cmd,clock[0],port,mode)
                    if key in delays:raise Unsupported('repeated delay specification requires native evaluation')
                    delays[key]=delay
        else:raise Unsupported('unsupported SDC command: '+cmd)
    refs=set(latency)|propagated|{k[1] for k in delays}
    if not clocks or not design or not refs.issubset(clocks):raise Unsupported('missing design/clocks or unresolved clock reference')
    return {'current_design':design,'clocks':clocks,'network_latency':latency,
            'propagated_clocks':sorted(propagated),'io_delays':[list(k)+[v] for k,v in sorted(delays.items())]}

def compare_sdc(reference,candidate):
    result={'profile':'exported-sdc-literals.v1','full_constraint_gate':'UNKNOWN',
            'scope':'static literal contract comparison only; native context, inventory and coverage are not certified',
            'reference_text_sha256':hashlib.sha256(reference.encode()).hexdigest(),
            'candidate_text_sha256':hashlib.sha256(candidate.encode()).hexdigest(),'changes':[]}
    try:
        a=normalize(reference);b=normalize(candidate)
        result['comparison']='EQUAL_WITHIN_PROFILE' if a==b else 'DIFFERENT'
        for k in a:
            if a[k]!=b[k]:result['changes'].append({'field':k,'reference':a[k],'candidate':b[k]})
        for label,value in [('reference',a),('candidate',b)]:
            result[label+'_contract_sha256']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    except Unsupported as ex:result.update(comparison='UNKNOWN',reason=str(ex))
    return result
