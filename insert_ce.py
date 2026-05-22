import os, psycopg2
url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id FROM chains WHERE name = '消费电子'")
chain_id = cur.fetchone()[0]

segments = [
    ('upstream', '显示面板'), ('upstream', '芯片/SoC'), ('upstream', '光学镜头'),
    ('upstream', '精密结构件'), ('upstream', '传感器'), ('upstream', '消费电子电池'),
    ('upstream', 'MLCC/被动元件'), ('upstream', '连接器/线束'), ('upstream', '声学/马达'),
    ('midstream', '模组'), ('midstream', '整机组装'), ('midstream', '折叠屏铰链与盖板'),
    ('midstream', '品牌整机'),
    ('downstream', '终端渠道'), ('downstream', '售后服务'),
    ('downstream', '品牌出海/跨境电商')
]
seg_ids = {}
for pos, name in segments:
    cur.execute("INSERT INTO chain_segments (chain_id, position, segment_name) VALUES (%s, %s, %s) RETURNING id", (chain_id, pos, name))
    seg_ids[name] = cur.fetchone()[0]

sectors = [
    ('显示面板', '显示面板'), ('消费电子芯片', '芯片/SoC'), ('光学镜头', '光学镜头'),
    ('精密结构件', '精密结构件'), ('传感器', '传感器'), ('消费电子电池', '消费电子电池'),
    ('MLCC', 'MLCC/被动元件'), ('连接器', '连接器/线束'), ('声学部件', '声学/马达'),
    ('模组制造', '模组'), ('整机组装', '整机组装'),
    ('折叠屏结构件', '折叠屏铰链与盖板'),
    ('智能手机', '品牌整机'), ('可穿戴', '品牌整机'),
    ('消费电子零售', '终端渠道'), ('消费电子维修', '售后服务'),
    ('跨境消费电子', '品牌出海/跨境电商')
]
sector_ids = {}
for sname, segname in sectors:
    cur.execute("INSERT INTO sectors (name, segment_id) VALUES (%s, %s) RETURNING id", (sname, seg_ids[segname]))
    sector_ids[sname] = cur.fetchone()[0]

stocks = [
    ('000725', '京东方A', '显示面板', '核心龙头'), ('000100', 'TCL科技', '显示面板', '核心龙头'),
    ('603501', '韦尔股份', '消费电子芯片', '核心龙头'), ('300782', '卓胜微', '消费电子芯片', '核心龙头'),
    ('02382.HK', '舜宇光学科技', '光学镜头', '核心龙头'), ('002036', '联创电子', '光学镜头', '核心龙头'),
    ('002475', '立讯精密', '精密结构件', '核心龙头'), ('300115', '长盈精密', '精密结构件', '核心龙头'),
    ('002241', '歌尔股份', '传感器', '核心龙头'), ('688286', '敏芯股份', '传感器', '一般关联'),
    ('300207', '欣旺达', '消费电子电池', '核心龙头'), ('000049', '德赛电池', '消费电子电池', '核心龙头'),
    ('300408', '三环集团', 'MLCC', '核心龙头'), ('002138', '顺络电子', 'MLCC', '核心龙头'),
    ('002475', '立讯精密', '连接器', '核心龙头'), ('300679', '电连技术', '连接器', '一般关联'),
    ('002241', '歌尔股份', '声学部件', '核心龙头'), ('02018.HK', '瑞声科技', '声学部件', '核心龙头'),
    ('002475', '立讯精密', '模组制造', '核心龙头'), ('002241', '歌尔股份', '模组制造', '核心龙头'),
    ('002475', '立讯精密', '整机组装', '核心龙头'), ('00285.HK', '比亚迪电子', '整机组装', '核心龙头'),
    ('300709', '精研科技', '折叠屏结构件', '核心龙头'), ('600114', '东睦股份', '折叠屏结构件', '核心龙头'),
    ('01810.HK', '小米集团-W', '智能手机', '核心龙头'), ('688036', '传音控股', '智能手机', '核心龙头'),
    ('002241', '歌尔股份', '可穿戴', '核心龙头'), ('002351', '漫步者', '可穿戴', '一般关联'),
    ('09618.HK', '京东集团-SW', '消费电子零售', '核心龙头'), ('002024', '苏宁易购', '消费电子零售', '一般关联'),
    ('300736', '百邦科技', '消费电子维修', '一般关联'),
    ('300866', '安克创新', '跨境消费电子', '核心龙头'), ('688036', '传音控股', '跨境消费电子', '核心龙头')
]
for code, name, sname, rel in stocks:
    cur.execute("INSERT INTO stocks (code, name, sector_id, relevance) VALUES (%s, %s, %s, %s)", (code, name, sector_ids[sname], rel))

print("消费电子导入成功！")
cur.close(); conn.close()
