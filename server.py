import json, sqlite3, os, sys, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# >>> EDIT THIS: path to the stats.db the Minecraft plugin writes to
DB_PATH = os.environ.get("STATS_DB", "stats.db")
PORT = int(os.environ.get("PORT", "8080"))
HERE = os.path.dirname(os.path.abspath(__file__))

def q(sql, args=()):
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)  # read-only: website can never damage the DB
    c.row_factory = sqlite3.Row
    try: return [dict(r) for r in c.execute(sql, args)]
    finally: c.close()

def overview():
    players = q("SELECT uuid,name,kills,deaths,elo,duel_wins,duel_losses,best_streak,playtime_seconds,last_online FROM stats ORDER BY elo DESC, kills DESC LIMIT 50")
    tot = q("SELECT (SELECT COUNT(*) FROM stats) p, (SELECT COUNT(*) FROM duel_history) m")[0]
    return {"players": players, "totals": tot}

def ladders():
    rows = q("""SELECT gamemode,uuid,name,ar,rank_index,wins,losses FROM ranked_stats
                ORDER BY gamemode, rank_index DESC, ar DESC, wins DESC""")
    out = {}
    for r in rows: out.setdefault(r["gamemode"], []).append(r)
    kits = q("SELECT DISTINCT kit FROM duel_history")
    for k in kits: out.setdefault(k["kit"], [])
    return {k: v[:10] for k, v in out.items()}

def matches():
    return q("SELECT id,winner_uuid,winner_name,loser_uuid,loser_name,kit,winner_score,loser_score,arena,ended_at FROM duel_history ORDER BY id DESC LIMIT 100")

def player(name):
    p = q("SELECT * FROM stats WHERE name = ? COLLATE NOCASE", (name,))
    if not p: return None
    p = p[0]
    rank = q("SELECT COUNT(*)+1 AS r FROM stats WHERE elo > ?", (p["elo"],))[0]["r"]
    linked_rows = q("SELECT 1 AS linked FROM link_codes WHERE uuid=? AND claimed=1 ORDER BY created_at DESC LIMIT 1", (p["uuid"],))
    return {"stats": p, "rank": rank, "linked": bool(linked_rows),
            "kits": q("SELECT gamemode,ar,rank_index,wins,losses FROM ranked_stats WHERE uuid=?", (p["uuid"],)),
            "recent": q("SELECT * FROM duel_history WHERE winner_uuid=? OR loser_uuid=? ORDER BY id DESC LIMIT 15", (p["uuid"], p["uuid"]))}

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes): body = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u = urlparse(self.path); a = parse_qs(u.query)
        try:
            if u.path == "/api/overview": return self.send(200, overview())
            if u.path == "/api/ladders": return self.send(200, ladders())
            if u.path == "/api/matches": return self.send(200, matches())
            if u.path == "/api/player":
                r = player(a.get("name", [""])[0]); return self.send(200 if r else 404, r or {"error": "not found"})
        except Exception as e:
            return self.send(500, {"error": str(e)})
        f = "index.html" if u.path == "/" else u.path.lstrip("/")
        fp = os.path.normpath(os.path.join(HERE, f))
        if fp.startswith(HERE) and os.path.isfile(fp) and not fp.endswith((".py", ".db")):
            return self.send(200, open(fp, "rb").read(), mimetypes.guess_type(fp)[0] or "application/octet-stream")
        self.send(404, b"not found", "text/plain")

if __name__ == "__main__":
    print(f"AzurPvP site on http://0.0.0.0:{PORT}  (db: {DB_PATH})")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
