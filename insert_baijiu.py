import os, psycopg2
url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id FROM chains WHERE name = '白酒'")
row = cur.fetchone()
if not row:
    print("错误：chains 表中没有白酒记录。")
    cur.close(); conn.close(); exit(1)
chain_id = row[0]

segments_data = [
    ('upstream', '酿酒原料'), ('upstream', '包装材料'), ('upstream', '酿酒设备'),
    ('midstream', '基酒酿造与储存'), ('midstream', '成品酒勾调与灌装'),
    ('downstream', '经销商与渠道'), ('downstream', '终端消费'), ('downstream', '电商与直销')
]
seg_ids = {}
for pos, name in segments_data:
    cur.execute("INSERT INTO chain_segments (chain_id, position, segment_name) VALUES (%s, %s, %s) RETURNING id", (chain_id, pos, name))
    seg_ids[name] = cur.fetchone()[0]
    print(f"环节: {name}")

sectors_data = [
    ('粮食', '酿酒原料'), ('酒瓶/陶瓷', '包装材料'), ('酒盒/印刷', '包装材料'),
    ('酿酒设备', '酿酒设备'), ('基酒', '基酒酿造与储存'),
    ('高端白酒', '成品酒勾调与灌装'), ('次高端白酒', '成品酒勾调与灌装'), ('区域白酒', '成品酒勾调与灌装'),
    ('酒类流通', '经销商与渠道'), ('白酒消费', '终端消费'), ('酒类电商', '电商与直销')
]
sector_ids = {}
for sname, segname in sectors_data:
    cur.execute("INSERT INTO sectors (name, segment_id) VALUES (%s, %s) RETURNING id", (sname, seg_ids[segname]))
    sector_ids[sname] = cur.fetchone()[0]
    print(f"板块: {sname}")

stocks_data = [
    ('601952', '苏垦农发', '粮食', '核心龙头'), ('600598', '北大荒', '粮食', '一般关联'),
    ('603021', '山东华鹏', '酒瓶/陶瓷', '核心龙头'), ('603268', '松发股份', '酒瓶/陶瓷', '一般关联'),
    ('002191', '劲嘉股份', '酒盒/印刷', '核心龙头'), ('601515', '东风股份', '酒盒/印刷', '一般关联'),
    ('603076', '乐惠国际', '酿酒设备', '核心龙头'), ('300933', '中辰股份', '酿酒设备', '一般关联'),
    ('600519', '贵州茅台', '基酒', '核心龙头'), ('000858', '五粮液', '基酒', '核心龙头'),
    ('600519', '贵州茅台', '高端白酒', '核心龙头'), ('000858', '五粮液', '高端白酒', '核心龙头'), ('000568', '泸州老窖', '高端白酒', '核心龙头'),
    ('600809', '山西汾酒', '次高端白酒', '核心龙头'), ('000596', '古井贡酒', '次高端白酒', '核心龙头'), ('002304', '洋河股份', '次高端白酒', '核心龙头'),
    ('603369', '今世缘', '区域白酒', '核心龙头'), ('603589', '口子窖', '区域白酒', '核心龙头'),
    ('300755', '华致酒行', '酒类流通', '核心龙头'), ('835961', '名品世家', '酒类流通', '一般关联'),
    ('600519', '贵州茅台', '白酒消费', '核心龙头'), ('000858', '五粮液', '白酒消费', '核心龙头'),
    ('300792', '壹网壹创', '酒类电商', '一般关联'), ('003010', '若羽臣', '酒类电商', '一般关联')
]
for code, name, sname, rel in stocks_data:
    cur.execute("INSERT INTO stocks (code, name, sector_id, relevance) VALUES (%s, %s, %s, %s)", (code, name, sector_ids[sname], rel))
    print(f"股票: {name}")

print("白酒产业链导入成功！")
cur.close(); conn.close()
