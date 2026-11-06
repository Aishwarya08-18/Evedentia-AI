from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, csv, json, re, io, os, hmac
try:
    import pandas as pd
except ImportError:
    pd = None

BASE=Path(__file__).resolve().parent
UPLOADS=BASE/'uploads'; REPORTS=BASE/'reports'; DB=BASE/'evedentia_ai.db'
UPLOADS.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
app=Flask(__name__)
app.secret_key=os.environ.get('EVEDENTIA_AI_SECRET', 'local-development-secret-change-before-deployment')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=25*1024*1024)

ALIASES={'id':'record_id','order':'order_id','order_no':'order_id','order_number':'order_id','invoice_id':'order_id','transaction_id':'order_id','customerid':'customer_id','client_id':'customer_id','customer_name':'customer','item':'product','item_name':'product','sku_name':'product','qty':'quantity','units':'quantity','total':'amount','revenue':'amount','sales_amount':'amount','order_status':'status','delivery_status':'status','transaction_date':'date','order_date':'date'}
KEY_CANDIDATES=['order_id','record_id','transaction_id','invoice_id','customer_id','email']
AUTHORITY_DEFAULT={'amount':'finance','quantity':'inventory','product':'inventory','sku':'inventory','status':'sales','date':'sales','customer':'crm','email':'crm','phone':'crm','address':'crm'}
DEMO={
'sales':[{'order_id':'ORD-1001','customer_id':'C101','customer':'Aarav Traders','product':'Laptop','quantity':'12','amount':'720000','status':'Delivered','date':'2026-10-28'},{'order_id':'ORD-1002','customer_id':'C102','customer':'BlueSky Stores','product':'Monitor','quantity':'8','amount':'96000','status':'Pending','date':'2026-10-29'},{'order_id':'ORD-1003','customer_id':'C103','customer':'Cedar Retail','product':'Keyboard','quantity':'25','amount':'37500','status':'Delivered','date':'2026-10-30'}],
'inventory':[{'order_id':'ORD-1001','customer_id':'C101','customer':'Aarav Traders','product':'Laptop','quantity':'10','amount':'720000','status':'Delivered','date':'2026-10-28'},{'order_id':'ORD-1002','customer_id':'C102','customer':'BlueSky Stores','customer':'BlueSky Stores','product':'Monitor','quantity':'8','amount':'96000','status':'Delivered','date':'2026-10-29'},{'order_id':'ORD-1003','customer_id':'C103','customer':'Cedar Retail','product':'Keyboard','quantity':'25','amount':'37500','status':'Delivered','date':'2026-10-30'}],
'finance':[{'order_id':'ORD-1001','customer_id':'C101','customer':'Aarav Traders','product':'Laptop','quantity':'12','amount':'700000','status':'Paid','date':'2026-10-28'},{'order_id':'ORD-1002','customer_id':'C102','customer':'BlueSky Stores','product':'Monitor','quantity':'8','amount':'96000','status':'Paid','date':'2026-10-29'},{'order_id':'ORD-1003','customer_id':'C103','customer':'Cedar Retail','product':'Keyboard','quantity':'25','amount':'37500','status':'Paid','date':'2026-10-30'}]}

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE COLLATE NOCASE NOT NULL, email TEXT UNIQUE COLLATE NOCASE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)')
        # One-time migration for the earlier demo login, only if no account exists.
        if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0 and os.environ.get('EVEDENTIA_AI_CREATE_DEMO_ADMIN')=='1':
            c.execute('INSERT INTO users(username,email,password_hash,created_at) VALUES(?,?,?,?)',('admin','admin@local.test',generate_password_hash('Trust@123'),datetime.now().isoformat(timespec='seconds')))
init_db()

def clean_header(s):
    s=re.sub(r'[^a-z0-9]+','_',str(s).strip().lower()).strip('_'); return ALIASES.get(s,s)
def clean_value(v):
    if v is None:return ''
    if isinstance(v,float) and v.is_integer():return str(int(v))
    return str(v).strip()
def normalize(rows):
    out=[]
    for row in rows:
        r={}
        for k,v in row.items():
            if k is not None:
                h=clean_header(k)
                if h:r[h]=clean_value(v)
        out.append(r)
    return out

def read_upload(file):
    ext=Path(file.filename).suffix.lower(); raw=file.read()
    if ext=='.csv':
        text=raw.decode('utf-8-sig')
        try:dialect=csv.Sniffer().sniff(text[:4096])
        except csv.Error:dialect=csv.excel
        return normalize(list(csv.DictReader(io.StringIO(text),dialect=dialect)))
    if ext=='.xlsx':
        if pd is None:raise ValueError('Excel support requires pandas and openpyxl. Install requirements.')
        frame=pd.read_excel(io.BytesIO(raw)); frame=frame.where(pd.notna(frame),'')
        return normalize(frame.to_dict(orient='records'))
    raise ValueError('Supported formats are CSV and .xlsx.')

def choose_key(data, requested='auto'):
    common=set.intersection(*[{k for row in rows for k in row} for rows in data.values()])
    if requested!='auto':
        if requested not in common:raise ValueError(f"Selected matching key '{requested}' is not present in every file.")
        return requested
    for key in KEY_CANDIDATES:
        if key in common:return key
    raise ValueError('No shared ID column found. Add a common order_id, record_id, transaction_id, customer_id or email column, or select a shared key.')

def norm_cmp(field,value):
    v=str(value).strip().lower()
    if field in ('amount','quantity'):
        try:return str(round(float(v.replace(',','').replace('₹','').replace('$','')),4))
        except ValueError:pass
    return re.sub(r'\s+',' ',v)

def root_cause(field):
    causes={'quantity':'Possible stock snapshot timing, partial fulfilment, return, or delayed stock movement. Verify dispatch notes and the stock ledger.','amount':'Possible discount, tax, freight, credit note, or posting-time difference. Verify the signed invoice and finance ledger.','status':'Departments may track different lifecycle states. Verify status definitions and event timestamps before treating these as equivalent.','date':'Possible timezone, export-time, or event-date versus posting-date mismatch. Verify original timestamps.'}
    return causes.get(field,'Possible independent edits, inconsistent master-data standards, or exports generated at different times. Check the source audit history.')

def analyze(data,key,authority,mode):
    groups={}; quality=[]; total=0
    all_fields=[]
    for rows in data.values():
        for row in rows:
            for field in row:
                if field!=key and field not in all_fields:all_fields.append(field)
    for source,rows in data.items():
        total+=len(rows); seen=set()
        for n,row in enumerate(rows,1):
            raw=row.get(key,'').strip()
            if not raw:
                quality.append({'source':source,'row':n,'issue':f'Missing matching key: {key}','severity':'High'}); continue
            match=norm_cmp(key,raw)
            if match in seen:quality.append({'source':source,'row':n,'issue':f'Duplicate {key}: {raw}','severity':'Medium'})
            seen.add(match); groups.setdefault(match,{'display':raw,'sources':{}})['sources'].setdefault(source,[]).append(row)
    issues=[]; canonical=[]
    for g in groups.values():
        srcrows=g['sources']; merged={key:g['display']}
        for field in all_fields:
            ev=[]
            for src,rows in srcrows.items():
                for row in rows:
                    value=row.get(field,'')
                    if value!='':ev.append({'source':src,'value':value})
            if not ev:continue
            distinct={norm_cmp(field,e['value']) for e in ev}
            if len(distinct)==1:merged[field]=ev[0]['value']; continue
            owner=authority.get(field,AUTHORITY_DEFAULT.get(field,''))
            preferred=[e['value'] for e in ev if owner and owner in e['source'].lower()]
            if preferred:proposed=preferred[-1]; method=f'Source priority: {owner}'
            else:
                counts={}
                for e in ev:counts[norm_cmp(field,e['value'])]=counts.get(norm_cmp(field,e['value']),0)+1
                top=max(counts.values()); winners={v for v,n in counts.items() if n==top}
                if len(winners)==1:
                    winner=next(iter(winners)); proposed=next(e['value'] for e in ev if norm_cmp(field,e['value'])==winner); method='Majority value'
                else:
                    proposed=''; method='Tie — human decision required'
            if proposed:merged[field]=proposed
            issues.append({'record':g['display'],'field':field,'values':ev,'proposed':proposed or 'Needs review','method':method,'severity':'High' if field in ('amount','quantity','status') else 'Medium','root_cause':root_cause(field)})
        canonical.append(merged)
    high=sum(x['severity']=='High' for x in issues)+sum(x['severity']=='High' for x in quality)
    return {'mode':mode,'sources':[{'name':k,'records':len(v)} for k,v in data.items()],'total_records':total,'matched_records':len(groups),'issue_count':len(issues)+len(quality),'high':high,'issues':issues,'data_quality_issues':quality,'corrected':canonical,'key':key,'authority':authority,'trust_index':max(0,100-round((len(issues)+len(quality))*30/max(total,1))),'agents':[{'name':'Ingestion & Schema Agent','detail':f'Validated and loaded {len(data)} uploaded source files; normalized headers while retaining all columns.'},{'name':'Record Linkage Agent','detail':f'Matched records using the selected shared key “{key}”.'},{'name':'Conflict Detection Agent','detail':f'Compared {len(all_fields)} available fields and found {len(issues)} field-level conflicts.'},{'name':'Evidence & Root-Cause Agent','detail':'Attached observed source values and generated testable root-cause hypotheses.'},{'name':'Resolution Agent','detail':'Applied configured source priorities or unambiguous majority; ties remain flagged for human review.'}]}

def persist(result):
    result['generated_at']=datetime.now().isoformat(timespec='seconds')
    (REPORTS/f"latest_report_user_{session.get('user_id','guest')}.json").write_text(json.dumps(result,indent=2),encoding='utf-8')

@app.before_request
def require_login():
    if request.endpoint in {'login','signup','health','static'}:return None
    if not session.get('user_id'):
        if request.path.startswith('/api/'):return jsonify(error='Please sign in to continue.'),401
        return redirect(url_for('login'))

@app.route('/signup',methods=['GET','POST'])
def signup():
    if session.get('user_id'):return redirect(url_for('home'))
    error=None
    if request.method=='POST':
        username=request.form.get('username','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if len(username)<3 or len(username)>30 or not re.fullmatch(r'[A-Za-z0-9_.-]+',username):error='Username must be 3–30 characters (letters, numbers, dot, underscore or hyphen).'
        elif not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email):error='Enter a valid email address.'
        elif len(password)<8:error='Password must contain at least 8 characters.'
        elif password!=confirm:error='Passwords do not match.'
        else:
            try:
                with db() as c:c.execute('INSERT INTO users(username,email,password_hash,created_at) VALUES(?,?,?,?)',(username,email,generate_password_hash(password),datetime.now().isoformat(timespec='seconds')))
                return redirect(url_for('login',registered='1'))
            except sqlite3.IntegrityError:error='That username or email is already registered. Sign in or use another one.'
    return render_template('signup.html',error=error)

@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('user_id'):return redirect(url_for('home'))
    error=None
    if request.method=='POST':
        username=request.form.get('username','').strip()
        with db() as c:user=c.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE',(username,username)).fetchone()
        if user and check_password_hash(user['password_hash'],request.form.get('password','')):
            session.clear(); session['user_id']=user['id']; session['username']=user['username']; return redirect(url_for('home'))
        error='Invalid username/email or password. Please try again.'
    return render_template('login.html',error=error,registered=request.args.get('registered')=='1')

@app.route('/logout',methods=['POST'])
def logout():session.clear(); return redirect(url_for('login'))
@app.route('/')
def home():return render_template('index.html',username=session.get('username','User'))
@app.route('/api/demo',methods=['POST'])
def demo():
    d=analyze({k:normalize(v) for k,v in DEMO.items()},'order_id',{'amount':'finance','quantity':'inventory','status':'sales'},'Built-in demonstration (3 sample sources)');persist(d);return jsonify(d)
@app.route('/api/analyze',methods=['POST'])
def upload():
    files=[f for f in request.files.getlist('files') if f and f.filename]
    if len(files)<2:return jsonify(error='Select at least two CSV or XLSX files.'),400
    data={}
    for f in files:
        safe=secure_filename(f.filename); stem=Path(safe).stem or 'source'; name=stem; suffix=2
        while name.lower() in {x.lower() for x in data}:name=f'{stem}_{suffix}';suffix+=1
        try:
            rows=read_upload(f)
            if not rows:return jsonify(error=f'{f.filename}: file contains no data rows.'),400
            data[name]=rows
        except Exception as e:return jsonify(error=f'{f.filename}: {e}'),400
    requested=request.form.get('key','auto')
    try:key=choose_key(data,requested)
    except ValueError as e:return jsonify(error=str(e)),400
    authority={}
    for field in set(AUTHORITY_DEFAULT)|{'quantity','amount'}:
        val=request.form.get('authority_'+field,'').strip().lower()
        if val:authority[field]=val
    d=analyze(data,key,authority,'Uploaded business files');persist(d);return jsonify(d)
@app.route('/api/report')
def report():
    p=REPORTS/f"latest_report_user_{session.get('user_id','guest')}.json"
    if not p.exists():return jsonify(error='Run an investigation first.'),404
    response=send_file(p, mimetype='application/json', as_attachment=True, download_name='EVEDENTIA_AI_investigation.json', conditional=False, max_age=0)
    response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
    response.headers['X-Content-Type-Options']='nosniff'
    return response
@app.route('/health')
def health():return jsonify(status='ok',application='EVEDENTIA AI')
if __name__=='__main__':
    print('\nEVEDENTIA AI ready at http://127.0.0.1:5000\n')
    app.run(host='127.0.0.1',port=5000,debug=False)
