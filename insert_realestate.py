import os, psycopg2
url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id FROM chains WHERE name = '房地产'")
row = cur.fetchone()
if not row:
    print("错误：chains 表中没有房地产记录。")
    cur.close(); conn.close(); exit(1)
chain_id = row[0]

segments_data = [
    ('upstream', '土地获取'), ('upstream', '建材供应'), ('upstream', '建筑设计与施工'), ('upstream', '工程机械'),
    ('midstream', '住宅开发'), ('midstream', '商业地产'), ('midstream', '产业地产'), ('midstream', '房地产金融'),
    ('downstream', '销售代理'), ('downstream', '物业管理'), ('downstream', '装修装饰')
]
seg_ids = {}
for pos, name in segments_data:
    cur.execute("INSERT INTO chain_segments (chain_id, position, segment_name) VALUES (%s, %s, %s) RETURNING id", (chain_id, pos, name))
    seg_ids[name] = cur.fetchone()[0]
    print(f"环节: {name}")

sectors_data = [
    ('土地一级开发', '土地获取'), ('水泥', '建材供应'), ('钢材', '建材供应'), ('玻璃', '建材供应'),
    ('建筑施工', '建筑设计与施工'), ('工程机械', '工程机械'),
    ('住宅开发', '住宅开发'), ('商业地产', '商业地产'), ('产业园区', '产业地产'),
    ('REITs/房地产基金', '房地产金融'),
    ('房产中介', '销售代理'), ('物业管理', '物业管理'), ('家装', '装修装饰')
]
sector_ids = {}
for sname, segname in sectors_data:
    cur.execute("INSERT INTO sectors (name, segment_id) VALUES (%s, %s) RETURNING id", (sname, seg_ids[segname]))
    sector_ids[sname] = cur.fetchone()[0]
    print(f"板块: {sname}")

stocks_data = [
    ('600340', '华夏幸福', '土地一级开发', '核心龙头'), ('600064', '南京高科', '土地一级开发', '一般关联'),
    ('600585', '海螺水泥', '水泥', '核心龙头'), ('600801', '华新水泥', '水泥', '核心龙头'),
    ('600019', '宝钢股份', '钢材', '核心龙头'), ('000898', '鞍钢股份', '钢材', '一般关联'),
    ('601636', '旗滨集团', '玻璃', '核心龙头'), ('000012', '南玻A', '玻璃', '一般关联'),
    ('601668', '中国建筑', '建筑施工', '核心龙头'), ('600170', '上海建工', '建筑施工', '核心龙头'),
    ('600031', '三一重工', '工程机械', '核心龙头'), ('000157', '中联重科', '工程机械', '核心龙头'),
    ('000002', '万科A', '住宅开发', '核心龙头'), ('600048', '保利发展', '住宅开发', '核心龙头'), ('001979', '招商蛇口', '住宅开发', '核心龙头'),
    ('01109.HK', '华润置地', '商业地产', '核心龙头'), ('00960.HK', '龙湖集团', '商业地产', '核心龙头'),
    ('001979', '招商蛇口', '产业园区', '核心龙头'), ('600340', '华夏幸福', '产业园区', '核心龙头'),
    ('000002', '万科A', 'REITs/房地产基金', '核心龙头'), ('001979', '招商蛇口', 'REITs/房地产基金', '核心龙头'),
    ('BEKE', '贝壳', '房产中介', '核心龙头'), ('000560', '我爱我家', '房产中介', '核心龙头'),
    ('06098.HK', '碧桂园服务', '物业管理', '核心龙头'), ('02602.HK', '万物云', '物业管理', '核心龙头'),
    ('002081', '金螳螂', '家装', '核心龙头'), ('002713', '东易日盛', '家装', '一般关联')
]
for code, name, sname, rel in stocks_data:
    cur.execute("INSERT INTO stocks (code, name, sector_id, relevance) VALUES (%s, %s, %s, %s)", (code, name, sector_ids[sname], rel))
    print(f"股票: {name}")

print("房地产产业链导入成功！")
cur.close(); conn.close()
