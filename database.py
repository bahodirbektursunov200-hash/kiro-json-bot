import sqlite3, os, secrets
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
DB_PATH=Path(__file__).with_name('jsonmarket.db')
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
class Database:
 def __init__(self,path=DB_PATH): self.path=str(path); self.init()
 @contextmanager
 def conn(self):
  c=sqlite3.connect(self.path,timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=15000')
  try: yield c; c.commit()
  finally: c.close()
 def init(self):
  with self.conn() as c:
   c.executescript('''
   CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_user_id INTEGER UNIQUE NOT NULL,username TEXT,full_name TEXT NOT NULL,created_at TEXT NOT NULL,last_seen TEXT NOT NULL,balance INTEGER NOT NULL DEFAULT 0,blocked INTEGER NOT NULL DEFAULT 0);
   CREATE TABLE IF NOT EXISTS json_submissions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,plan TEXT NOT NULL,json_text TEXT NOT NULL,price INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',reject_reason TEXT,created_at TEXT NOT NULL,reviewed_at TEXT,FOREIGN KEY(user_id) REFERENCES users(id));
   CREATE TABLE IF NOT EXISTS withdrawals(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,amount INTEGER NOT NULL,payment_method TEXT NOT NULL,recipient TEXT NOT NULL,note TEXT,status TEXT NOT NULL DEFAULT 'pending',requested_at TEXT NOT NULL,paid_at TEXT,payment_id TEXT,reject_reason TEXT,paid_by_id INTEGER,paid_by_username TEXT,FOREIGN KEY(user_id) REFERENCES users(id));
   CREATE TABLE IF NOT EXISTS payment_methods(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,details TEXT NOT NULL DEFAULT '',note TEXT NOT NULL DEFAULT '',enabled INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,price INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,plan_id INTEGER NOT NULL,plan_name TEXT NOT NULL,price INTEGER NOT NULL,payment_method TEXT NOT NULL,proof TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',payment_id TEXT,reject_reason TEXT,created_at TEXT NOT NULL,reviewed_at TEXT,reviewed_by_id INTEGER,reviewed_by_username TEXT,FOREIGN KEY(user_id) REFERENCES users(id));
   CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,type TEXT NOT NULL,amount INTEGER NOT NULL,balance_after INTEGER NOT NULL,reference TEXT,note TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
   CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS saved_cards(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,label TEXT NOT NULL,number TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(user_id,number),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
   ''')
   # migrations for older DBs
   for col,typ,default in [('blocked','INTEGER NOT NULL DEFAULT 0','0')]:
    try:c.execute(f'ALTER TABLE users ADD COLUMN {col} {typ}')
    except sqlite3.OperationalError:pass
   for col,typ,default in [('note',"TEXT NOT NULL DEFAULT ''",None),('paid_by_id','INTEGER',None),('paid_by_username',"TEXT",None)]:
    try:c.execute(f'ALTER TABLE withdrawals ADD COLUMN {col} {typ}')
    except sqlite3.OperationalError:pass
   for col,typ in [('details',"TEXT NOT NULL DEFAULT ''"),('note',"TEXT NOT NULL DEFAULT ''")]:
    try:c.execute(f'ALTER TABLE payment_methods ADD COLUMN {col} {typ}')
    except sqlite3.OperationalError:pass
   for col,typ in [('reviewed_by_id','INTEGER'),('reviewed_by_username','TEXT')]:
    try:c.execute(f'ALTER TABLE subscriptions ADD COLUMN {col} {typ}')
    except sqlite3.OperationalError:pass
   defaults={'min_withdrawal':'10000','help_text':'Yordam uchun admin bilan bog‘laning.','admin_username':'','membership_required':'0','official_channel_id':'','official_channel_link':'','payment_channel_id':''}
   for k,v in defaults.items(): c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
   if c.execute('SELECT COUNT(*) FROM plans').fetchone()[0]==0:
    for n,p in [('Power',20000),('Pro',50000),('Pro Max',100000)]: c.execute('INSERT INTO plans(name,price,created_at,updated_at) VALUES(?,?,?,?)',(n,p,now(),now()))
   if c.execute('SELECT COUNT(*) FROM payment_methods').fetchone()[0]==0:
    for n in ('Click','Payme','Paynet','Uzum'): c.execute('INSERT INTO payment_methods(name,details,note,created_at) VALUES(?,?,?,?)',(n,'','',now()))
 def ensure_user(self,tg):
  with self.conn() as c:
   c.execute('''INSERT INTO users(telegram_user_id,username,full_name,created_at,last_seen) VALUES(?,?,?,?,?) ON CONFLICT(telegram_user_id) DO UPDATE SET username=excluded.username,full_name=excluded.full_name,last_seen=excluded.last_seen''',(tg.id,tg.username,tg.full_name,now(),now()))
   return c.execute('SELECT * FROM users WHERE telegram_user_id=?',(tg.id,)).fetchone()
 def user(self,tg):
  with self.conn() as c:return c.execute('SELECT * FROM users WHERE telegram_user_id=?',(tg,)).fetchone()
 def setting(self,k,d=''):
  with self.conn() as c:
   r=c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone();return r['value'] if r else d
 def set_setting(self,k,v):
  with self.conn() as c:c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
 def plans(self,enabled_only=False):
  with self.conn() as c:return c.execute('SELECT * FROM plans '+('WHERE enabled=1 ' if enabled_only else '')+'ORDER BY id').fetchall()
 def plan(self,pid):
  with self.conn() as c:return c.execute('SELECT * FROM plans WHERE id=?',(pid,)).fetchone()
 def add_plan(self,n,p):
  with self.conn() as c:
   cur=c.execute('INSERT INTO plans(name,price,created_at,updated_at) VALUES(?,?,?,?)',(n,p,now(),now()))
   return cur.lastrowid
 def update_plan(self,pid,price=None,name=None,enabled=None):
  with self.conn() as c:
   sets=[];vals=[]
   if price is not None:sets.append('price=?');vals.append(price)
   if name is not None:sets.append('name=?');vals.append(name)
   if enabled is not None:sets.append('enabled=?');vals.append(int(enabled))
   if sets: vals.append(pid);c.execute('UPDATE plans SET '+','.join(sets)+',updated_at=? WHERE id=?',(*vals[:-1],now(),vals[-1]))
 def delete_plan(self,pid):
  with self.conn() as c:c.execute('DELETE FROM plans WHERE id=?',(pid,))
 def payment_methods(self,enabled_only=True):
  with self.conn() as c:return c.execute('SELECT * FROM payment_methods '+('WHERE enabled=1 ' if enabled_only else '')+'ORDER BY id').fetchall()
 def payment_method(self,pid):
  with self.conn() as c:return c.execute('SELECT * FROM payment_methods WHERE id=?',(pid,)).fetchone()
 def add_payment(self,n,d='',note=''):
  with self.conn() as c:
   cur=c.execute('INSERT INTO payment_methods(name,details,note,created_at) VALUES(?,?,?,?)',(n,d,note,now()));return cur.lastrowid
 def update_payment(self,pid,name=None,details=None,note=None,enabled=None):
  with self.conn() as c:
   sets=[];vals=[]
   for col,val in [('name',name),('details',details),('note',note),('enabled',enabled)]:
    if val is not None:sets.append(col+'=?');vals.append(int(val) if col=='enabled' else val)
   if sets:vals.append(pid);c.execute('UPDATE payment_methods SET '+','.join(sets)+' WHERE id=?',vals)
 def delete_payment(self,pid):
  with self.conn() as c:c.execute('DELETE FROM payment_methods WHERE id=?',(pid,))
 def cards(self,tg):
  with self.conn() as c:
   u=c.execute('SELECT id FROM users WHERE telegram_user_id=?',(tg,)).fetchone()
   return c.execute('SELECT * FROM saved_cards WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall() if u else []
 def card(self,cid,tg=None):
  with self.conn() as c:
   if tg is None: return c.execute('SELECT * FROM saved_cards WHERE id=?',(cid,)).fetchone()
   return c.execute('SELECT sc.* FROM saved_cards sc JOIN users u ON u.id=sc.user_id WHERE sc.id=? AND u.telegram_user_id=?',(cid,tg)).fetchone()
 def add_card(self,tg,label,number):
  with self.conn() as c:
   u=c.execute('SELECT id FROM users WHERE telegram_user_id=?',(tg,)).fetchone()
   if not u: return None
   cur=c.execute('INSERT INTO saved_cards(user_id,label,number,created_at) VALUES(?,?,?,?)',(u['id'],label,number,now()))
   return cur.lastrowid
 def delete_card(self,cid,tg):
  with self.conn() as c:
   r=c.execute('DELETE FROM saved_cards WHERE id IN (SELECT sc.id FROM saved_cards sc JOIN users u ON u.id=sc.user_id WHERE sc.id=? AND u.telegram_user_id=?)',(cid,tg))
   return r.rowcount>0
 def create_submission(self,tg,plan,text,price):
  with self.conn() as c:
   u=c.execute('SELECT id FROM users WHERE telegram_user_id=?',(tg,)).fetchone();cur=c.execute('INSERT INTO json_submissions(user_id,plan,json_text,price,created_at) VALUES(?,?,?,?,?)',(u['id'],plan,text,price,now()));return cur.lastrowid
 def submission(self,sid):
  with self.conn() as c:return c.execute('SELECT s.*,u.telegram_user_id,u.username,u.full_name FROM json_submissions s JOIN users u ON u.id=s.user_id WHERE s.id=?',(sid,)).fetchone()
 def review_submission(self,sid,status,reason=None):
  changed=False
  with self.conn() as c:
   s=c.execute('SELECT * FROM json_submissions WHERE id=?',(sid,)).fetchone()
   if not s or s['status'] not in ('pending','processing'): return None
   cur=c.execute("UPDATE json_submissions SET status=?,reject_reason=?,reviewed_at=? WHERE id=? AND status IN ('pending','processing')",(status,reason,now(),sid))
   changed=cur.rowcount==1
   if changed and status=='approved':
    c.execute('UPDATE users SET balance=balance+? WHERE id=?',(s['price'],s['user_id']))
    b=c.execute('SELECT balance FROM users WHERE id=?',(s['user_id'],)).fetchone()['balance']
    c.execute('INSERT INTO transactions(user_id,type,amount,balance_after,reference,note,created_at) VALUES(?,?,?,?,?,?,?)',(s['user_id'],'json_sale',s['price'],b,f'JSON#{sid}',s['plan'],now()))
  return self.submission(sid) if changed else None
 def create_withdrawal(self,tg,amount,method,recipient,note):
  with self.conn() as c:
   u=c.execute('SELECT * FROM users WHERE telegram_user_id=?',(tg,)).fetchone()
   if not u or amount<=0 or amount>u['balance']: return None
   # Reserve/deduct the amount atomically when the withdrawal is created.
   cur=c.execute('INSERT INTO withdrawals(user_id,amount,payment_method,recipient,note,requested_at) VALUES(?,?,?,?,?,?)',(u['id'],amount,method,recipient,note,now()))
   wid=cur.lastrowid
   c.execute('UPDATE users SET balance=balance-? WHERE id=? AND balance>=?',(amount,u['id'],amount))
   if c.execute('SELECT changes()').fetchone()[0] != 1:
    c.execute('DELETE FROM withdrawals WHERE id=?',(wid,))
    return None
   b=c.execute('SELECT balance FROM users WHERE id=?',(u['id'],)).fetchone()['balance']
   c.execute('INSERT INTO transactions(user_id,type,amount,balance_after,reference,note,created_at) VALUES(?,?,?,?,?,?,?)',(u['id'],'withdrawal_hold',-amount,b,f'WD#{wid}',method,now()))
   return wid
 def withdrawal(self,wid):
  with self.conn() as c:return c.execute('SELECT w.*,u.telegram_user_id,u.username,u.full_name FROM withdrawals w JOIN users u ON u.id=w.user_id WHERE w.id=?',(wid,)).fetchone()
 def set_withdrawal_processing(self,wid):
  with self.conn() as c:
   r=c.execute("UPDATE withdrawals SET status='processing' WHERE id=? AND status='pending'",(wid,));return r.rowcount>0
 def finish_withdrawal(self,wid,paid,reason=None,paid_by_id=None,paid_by_username=None):
  changed=False
  with self.conn() as c:
   w=c.execute('SELECT * FROM withdrawals WHERE id=?',(wid,)).fetchone()
   if not w or w['status'] not in ('pending','processing'): return None
   if paid:
    pid='PAY-'+secrets.token_hex(4).upper()
    cur=c.execute("UPDATE withdrawals SET status='paid',paid_at=?,payment_id=?,paid_by_id=?,paid_by_username=? WHERE id=? AND status IN ('pending','processing')",(now(),pid,paid_by_id,paid_by_username,wid))
    changed=cur.rowcount==1
   else:
    cur=c.execute("UPDATE withdrawals SET status='rejected',reject_reason=? WHERE id=? AND status IN ('pending','processing')",(reason or 'Admin rad etdi',wid))
    changed=cur.rowcount==1
    if changed:
     c.execute('UPDATE users SET balance=balance+? WHERE id=?',(w['amount'],w['user_id']))
     b=c.execute('SELECT balance FROM users WHERE id=?',(w['user_id'],)).fetchone()['balance']
     c.execute('INSERT INTO transactions(user_id,type,amount,balance_after,reference,note,created_at) VALUES(?,?,?,?,?,?,?)',(w['user_id'],'withdrawal_refund',w['amount'],b,f'WD#{wid}',reason or 'Withdrawal rad etildi',now()))
  return self.withdrawal(wid) if changed else None
 def create_subscription(self,tg,pid,method,proof):
  with self.conn() as c:
   u=c.execute('SELECT id FROM users WHERE telegram_user_id=?',(tg,)).fetchone();p=c.execute('SELECT * FROM plans WHERE id=? AND enabled=1',(pid,)).fetchone()
   if not u or not p:return None
   cur=c.execute('INSERT INTO subscriptions(user_id,plan_id,plan_name,price,payment_method,proof,created_at) VALUES(?,?,?,?,?,?,?)',(u['id'],p['id'],p['name'],p['price'],method,proof,now()));return cur.lastrowid
 def subscription(self,sid):
  with self.conn() as c:return c.execute('SELECT s.*,u.telegram_user_id,u.username,u.full_name FROM subscriptions s JOIN users u ON u.id=s.user_id WHERE s.id=?',(sid,)).fetchone()
 def set_subscription_processing(self,sid):
  with self.conn() as c:return c.execute("UPDATE subscriptions SET status='processing' WHERE id=? AND status='pending'",(sid,)).rowcount>0
 def review_subscription(self,sid,paid,reason=None,paid_by_id=None,paid_by_username=None):
  changed=False
  with self.conn() as c:
   s=c.execute('SELECT * FROM subscriptions WHERE id=?',(sid,)).fetchone()
   if not s or s['status'] not in ('pending','processing'): return None
   if paid:
    pid='PAY-'+secrets.token_hex(4).upper()
    cur=c.execute("UPDATE subscriptions SET status='paid',payment_id=?,reviewed_at=?,reviewed_by_id=?,reviewed_by_username=? WHERE id=? AND status IN ('pending','processing')",(pid,now(),sid))
   else:
    cur=c.execute("UPDATE subscriptions SET status='rejected',reject_reason=?,reviewed_at=? WHERE id=? AND status IN ('pending','processing')",(reason or 'Admin rad etdi',now(),sid))
   changed=cur.rowcount==1
  return self.subscription(sid) if changed else None
 def all_users(self,limit=50,offset=0):
  with self.conn() as c:return c.execute('SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?',(limit,offset)).fetchall()
 def set_block(self,tg,blocked):
  with self.conn() as c:c.execute('UPDATE users SET blocked=? WHERE telegram_user_id=?',(int(blocked),tg))
 def adjust_balance(self,tg,amount,note):
  with self.conn() as c:
   u=c.execute('SELECT * FROM users WHERE telegram_user_id=?',(tg,)).fetchone()
   if not u or u['balance']+amount<0:return None
   b=u['balance']+amount;c.execute('UPDATE users SET balance=? WHERE id=?',(b,u['id']));c.execute('INSERT INTO transactions(user_id,type,amount,balance_after,reference,note,created_at) VALUES(?,?,?,?,?,?,?)',(u['id'],'admin_adjust',amount,b,'ADMIN',note,now()));return b
 def transactions(self,tg,limit=30):
  with self.conn() as c:return c.execute('SELECT t.* FROM transactions t JOIN users u ON u.id=t.user_id WHERE u.telegram_user_id=? ORDER BY t.id DESC LIMIT ?',(tg,limit)).fetchall()
 def submissions(self,tg,limit=30):
  with self.conn() as c:return c.execute('SELECT s.* FROM json_submissions s JOIN users u ON u.id=s.user_id WHERE u.telegram_user_id=? ORDER BY s.id DESC LIMIT ?',(tg,limit)).fetchall()
 def pending_submissions(self):
  with self.conn() as c:return c.execute("SELECT s.*,u.telegram_user_id,u.username,u.full_name FROM json_submissions s JOIN users u ON u.id=s.user_id WHERE s.status='pending' ORDER BY s.id DESC").fetchall()
 def withdrawals_by_status(self,status=None):
  with self.conn() as c:return c.execute("SELECT w.*,u.telegram_user_id,u.username,u.full_name FROM withdrawals w JOIN users u ON u.id=w.user_id "+('WHERE w.status=? ' if status else '')+'ORDER BY w.id DESC',(status,) if status else ()).fetchall()
 def subscriptions_by_status(self,status=None):
  with self.conn() as c:return c.execute("SELECT s.*,u.telegram_user_id,u.username,u.full_name FROM subscriptions s JOIN users u ON u.id=s.user_id "+('WHERE s.status=? ' if status else '')+'ORDER BY s.id DESC',(status,) if status else ()).fetchall()
 def stats(self):
  with self.conn() as c:
   q=lambda x:c.execute(x).fetchone()[0]
   return {'users':q('SELECT COUNT(*) FROM users'),'json':q('SELECT COUNT(*) FROM json_submissions'),'json_pending':q("SELECT COUNT(*) FROM json_submissions WHERE status='pending'"),'json_approved':q("SELECT COUNT(*) FROM json_submissions WHERE status='approved'"),'withdrawals':q('SELECT COUNT(*) FROM withdrawals'),'wd_pending':q("SELECT COUNT(*) FROM withdrawals WHERE status='pending'"),'wd_processing':q("SELECT COUNT(*) FROM withdrawals WHERE status='processing'"),'wd_paid':q("SELECT COUNT(*) FROM withdrawals WHERE status='paid'"),'subs':q('SELECT COUNT(*) FROM subscriptions'),'sub_pending':q("SELECT COUNT(*) FROM subscriptions WHERE status='pending'"),'sub_processing':q("SELECT COUNT(*) FROM subscriptions WHERE status='processing'"),'sub_paid':q("SELECT COUNT(*) FROM subscriptions WHERE status='paid'"),'revenue':q("SELECT COALESCE(SUM(price),0) FROM subscriptions WHERE status='paid'"),'json_amount':q("SELECT COALESCE(SUM(price),0) FROM json_submissions WHERE status='approved'")}
