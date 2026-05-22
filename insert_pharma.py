import os, psycopg2
url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id FROM chains WHERE name = '医药生物'")
chain_id = cur.fetchone()[0]

segments = [
    ('upstream', '原料药'), ('upstream', '药物发现(CRO)'), ('upstream', 'CDMO/生产外包'),
    ('upstream', '模式动物/实验试剂'), ('upstream', '制药设备'), ('upstream', '科研试剂'),
    ('midstream', '化学制药'), ('midstream', '生物制药'), ('midstream', '中药'),
    ('midstream', '医疗器械'), ('midstream', '疫苗'),
    ('midstream', '细胞与基因治疗(CGT)'), ('midstream', '核酸药物/mRNA'),
    ('downstream', '医药流通'), ('downstream', '零售药店'), ('downstream', '医疗机构'),
    ('downstream', '医保支付/商业保险')
]
seg_ids = {}
for pos, name in segments:
    cur.execute("INSERT INTO chain_segments (chain_id, position, segment_name) VALUES (%s, %s, %s) RETURNING id", (chain_id, pos, name))
    seg_ids[name] = cur.fetchone()[0]

sectors = [
    ('原料药', '原料药'), ('临床前CRO', '药物发现(CRO)'), ('CDMO', 'CDMO/生产外包'),
    ('实验动物', '模式动物/实验试剂'), ('制药设备', '制药设备'), ('科研试剂', '科研试剂'),
    ('化学制药', '化学制药'), ('生物制品', '生物制药'), ('中成药', '中药'),
    ('医疗器械', '医疗器械'), ('疫苗', '疫苗'),
    ('CGT疗法', '细胞与基因治疗(CGT)'), ('mRNA疫苗/药物', '核酸药物/mRNA'),
    ('医药流通', '医药流通'), ('连锁药店', '零售药店'), ('民营医院', '医疗机构'),
    ('医保IT', '医保支付/商业保险')
]
sector_ids = {}
for sname, segname in sectors:
    cur.execute("INSERT INTO sectors (name, segment_id) VALUES (%s, %s) RETURNING id", (sname, seg_ids[segname]))
    sector_ids[sname] = cur.fetchone()[0]

stocks = [
    ('600521', '华海药业', '原料药', '核心龙头'), ('000739', '普洛药业', '原料药', '核心龙头'),
    ('603259', '药明康德', '临床前CRO', '核心龙头'), ('300759', '康龙化成', '临床前CRO', '核心龙头'), ('300347', '泰格医药', '临床前CRO', '核心龙头'),
    ('002821', '凯莱英', 'CDMO', '核心龙头'), ('300363', '博腾股份', 'CDMO', '核心龙头'),
    ('688265', '南模生物', '实验动物', '核心龙头'), ('688046', '集萃药康', '实验动物', '一般关联'),
    ('300171', '东富龙', '制药设备', '核心龙头'), ('300358', '楚天科技', '制药设备', '核心龙头'),
    ('688179', '阿拉丁', '科研试剂', '核心龙头'), ('688133', '泰坦科技', '科研试剂', '一般关联'),
    ('600276', '恒瑞医药', '化学制药', '核心龙头'), ('01093.HK', '石药集团', '化学制药', '核心龙头'),
    ('688235', '百济神州', '生物制品', '核心龙头'), ('01801.HK', '信达生物', '生物制品', '核心龙头'),
    ('600436', '片仔癀', '中成药', '核心龙头'), ('600085', '同仁堂', '中成药', '核心龙头'), ('000538', '云南白药', '中成药', '核心龙头'),
    ('300760', '迈瑞医疗', '医疗器械', '核心龙头'), ('688271', '联影医疗', '医疗器械', '核心龙头'),
    ('300122', '智飞生物', '疫苗', '核心龙头'), ('300142', '沃森生物', '疫苗', '核心龙头'),
    ('LEGN', '传奇生物', 'CGT疗法', '核心龙头'), ('02126.HK', '药明巨诺', 'CGT疗法', '核心龙头'),
    ('300142', '沃森生物', 'mRNA疫苗/药物', '核心龙头'), ('688185', '康希诺', 'mRNA疫苗/药物', '核心龙头'),
    ('000028', '国药一致', '医药流通', '核心龙头'), ('601607', '上海医药', '医药流通', '核心龙头'),
    ('603939', '益丰药房', '连锁药店', '核心龙头'), ('603233', '大参林', '连锁药店', '核心龙头'), ('603883', '老百姓', '连锁药店', '核心龙头'),
    ('300015', '爱尔眼科', '民营医院', '核心龙头'), ('600763', '通策医疗', '民营医院', '核心龙头'),
    ('000503', '国新健康', '医保IT', '核心龙头'), ('002777', '久远银海', '医保IT', '一般关联')
]
for code, name, sname, rel in stocks:
    cur.execute("INSERT INTO stocks (code, name, sector_id, relevance) VALUES (%s, %s, %s, %s)", (code, name, sector_ids[sname], rel))

print("医药生物导入成功！")
cur.close(); conn.close()
