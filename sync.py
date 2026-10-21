"""Run this on the PC that hosts the Minecraft server. Pushes stats.db to Supabase whenever it changes."""
import json, hashlib, time, os, urllib.request
import server  # reuses the read-only queries

SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SERVICE_KEY  = "YOUR-SERVICE-ROLE-KEY"   # SECRET: never put this on GitHub
server.DB_PATH = os.environ.get("STATS_DB", r"stats.db")   # <- path to the plugin's stats.db
EVERY = 10  # seconds

def build():
    players = {}
    for r in server.q("SELECT name FROM stats"):
        players[r["name"].lower()] = server.player(r["name"])
    return {"overview": server.overview(), "ladders": server.ladders(),
            "matches": server.matches(), "players": players}

def push(data):
    req = urllib.request.Request(SUPABASE_URL + "/rest/v1/snapshot?on_conflict=id",
        data=json.dumps({"id": 1, "data": data}).encode(), method="POST",
        headers={"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"})
    urllib.request.urlopen(req, timeout=15).read()

last = None
while True:
    try:
        d = build(); h = hashlib.md5(json.dumps(d, sort_keys=True).encode()).hexdigest()
        if h != last: push(d); last = h; print(time.strftime("%H:%M:%S"), "pushed update")
    except Exception as e:
        print("sync error:", e)
    time.sleep(EVERY)
