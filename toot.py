import sqlite3
import datetime 

con = sqlite3.connect("pork.db")
curs = con.cursor()

class sqStuff:
    def __init__(self):
        curs.execute(''' 
            CREATE TABLE IF NOT EXISTS cop(
                sqbssid TEXT PRIMARY KEY, 
                sqssid TEXT, 
                sqsignal TEXT,
                protocal TEXT,  
                count INTEGER DEFAULT 0
            )'''
        )

        curs.execute('''
            CREATE TABLE IF NOT EXISTS groups(
                group_id TEXT PRIMARY KEY,
                bssids TEXT,
                blemacs TEXT,
                count INTEGER DEFAULT 1,
                last_seen TEXT
            )'''
        )
        con.commit()

        


    def addID(self, sqbssid, sqssid, sqsignal, protocal):
        if sqssid is None:
            curs.execute('''
                        UPDATE cop 
                        SET count = count + 1
                        WHERE sqbssid = ?
                        ''', (sqbssid, sqsignal, protocal))
        else:    
            curs.execute('''
                INSERT INTO cop (sqbssid, sqssid, sqsignal, protocal, count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(sqbssid)
                DO UPDATE SET
                    count = count + 1,
                    sqsignal = sqsignal,
                    sqssid = excluded.sqssid,
                    protocal =  protocal 
                         
            ''', (sqbssid, sqssid, sqsignal, protocal))
        con.commit()
    
    def updateGroup(self, mac, is_ble=False):
        
        mac_int = int(mac.replace(":", ""), 16)
        curs.execute("SELECT group_id, bssids, blemacs FROM groups")
        rows = curs.fetchall()

        for group_id, bssids, blemacs in rows:
            group_int = int(group_id.replace(":", ""), 16)
            if abs(mac_int - group_int) <= 2:
                now = datetime.datetime.now().isoformat()
                if is_ble:
                    ble_list = set(filter(None, blemacs.split(',')))
                    if mac not in ble_list:
                        ble_list.add(mac)
                        curs.execute("UPDATE groups SET blemacs = ?, count = count + 1, last_seen = ? WHERE group_id = ?",
                                        (','.join(ble_list), now, group_id))
                else:
                    bssid_list = set(filter(None, bssids.split(',')))
                    if mac not in bssid_list:
                        bssid_list.add(mac)
                        curs.execute("UPDATE groups SET bssids = ?, count = count + 1, last_seen = ? WHERE group_id = ?",
                                        (','.join(bssid_list), now, group_id))
                con.commit()
                return group_id  # Return the matching group

        # No match, create a new group
        now = datetime.datetime.now().isoformat()
        if is_ble:
            curs.execute("INSERT INTO groups (group_id, blemacs, bssids, last_seen) VALUES (?, ?, ?, ?)",
                            (mac, mac, "", now))
        else:
            curs.execute("INSERT INTO groups (group_id, bssids, blemacs, last_seen) VALUES (?, ?, ?, ?)",
                            (mac, mac, "", now))
        con.commit()
        return mac


# Create an instance of the class
db = sqStuff()