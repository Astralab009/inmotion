import os, psycopg2
url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id FROM chains WHERE name = '国防军工'")
chain_id = cur.fetchone()[0]

segments = [
    ('upstream', '高温合金'), ('upstream', '碳纤维'), ('upstream', '军用电子'),
    ('upstream', '军用电源'),
    ('midstream', '军用芯片'), ('midstream', '导弹制导'), ('midstream', '雷达与电子战'),
    ('midstream', '航空发动机'), ('midstream', '军用飞机'), ('midstream', '军用舰艇'),
    ('downstream', '国防采购'), ('downstream', '维修保障')
]
seg_ids = {}
for pos, name in segments:
    cur.execute("INSERT INTO chain_segments (chain_id, position, segment_name) VALUES (%s, %s, %s) RETURNING id", (chain_id, pos, name))
    seg_ids[name] = cur.fetchone()[0]

sectors = [
    ('高温合金', '高温合金'), ('碳纤维', '碳纤维'), ('军用电子', '军用电子'),
    ('军用电源', '军用电源'), ('军用芯片', '军用芯片'), ('导弹/制导', '导弹制导'),
    ('雷达', '雷达与电子战'), ('航空发动机', '航空发动机'),
    ('战斗机', '军用飞机'), ('军用船舶', '军用舰艇'),
    ('国防采购', '国防采购'), ('航空维修', '维修保障')
]
sector_ids = {}
for sname, segname in sectors:
    cur.execute("INSERT INTO sectors (name, segment_id) VALUES (%s, %s) RETURNING id", (sname, seg_ids[segname]))
    sector_ids[sname] = cur.fetchone()[0]

stocks = [
    ('600399', '抚顺特钢', '高温合金', '核心龙头'), ('300034', '钢研高纳', '高温合金', '核心龙头'),
    ('300699', '光威复材', '碳纤维', '核心龙头'), ('600862', '中航高科', '碳纤维', '核心龙头'),
    ('603267', '鸿远电子', '军用电子', '核心龙头'), ('603678', '火炬电子', '军用电子', '核心龙头'),
    ('300593', '新雷能', '军用电源', '核心龙头'), ('000733', '振华科技', '军用电源', '核心龙头'),
    ('002049', '紫光国微', '军用芯片', '核心龙头'), ('300101', '振芯科技', '军用芯片', '核心龙头'),
    ('600316', '洪都航空', '导弹/制导', '核心龙头'), ('002025', '航天电器', '导弹/制导', '核心龙头'),
    ('600562', '国睿科技', '雷达', '核心龙头'), ('600990', '四创电子', '雷达', '核心龙头'),
    ('600893', '航发动力', '航空发动机', '核心龙头'), ('000738', '航发控制', '航空发动机', '核心龙头'),
    ('600760', '中航沈飞', '战斗机', '核心龙头'), ('000768', '中航西飞', '战斗机', '核心龙头'),
    ('600150', '中国船舶', '军用船舶', '核心龙头'), ('600685', '中船防务', '军用船舶', '核心龙头'),
    ('600760', '中航沈飞', '国防采购', '核心龙头'), ('000768', '中航西飞', '国防采购', '核心龙头'),
    ('300424', '航新科技', '航空维修', '核心龙头'), ('002023', '海特高新', '航空维修', '一般关联')
]
for code, name, sname, rel in stocks:
    cur.execute("INSERT INTO stocks (code, name, sector_id, relevance) VALUES (%s, %s, %s, %s)", (code, name, sector_ids[sname], rel))

print("国防军工导入成功！")
cur.close(); conn.close()
