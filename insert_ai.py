import os, psycopg2
url = os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id FROM chains WHERE name = 'AI算力'")
chain_id = cur.fetchone()[0]

segments = [
    ('upstream', 'AI芯片'), ('upstream', 'GPU/加速卡'), ('upstream', '光模块'),
    ('upstream', 'AI服务器'), ('upstream', '存储'), ('upstream', '散热/液冷'),
    ('upstream', '先进封装(CoWoS)'),
    ('midstream', '算力平台'), ('midstream', '数据中心'), ('midstream', '智算中心'),
    ('midstream', '算力调度'), ('midstream', '高速互联/DPU'),
    ('downstream', '大模型'), ('downstream', 'AI应用'), ('downstream', 'AI Agent'),
    ('downstream', '数据要素/数据训练')
]
seg_ids = {}
for pos, name in segments:
    cur.execute("INSERT INTO chain_segments (chain_id, position, segment_name) VALUES (%s, %s, %s) RETURNING id", (chain_id, pos, name))
    seg_ids[name] = cur.fetchone()[0]

sectors = [
    ('AI芯片', 'AI芯片'), ('GPU', 'GPU/加速卡'), ('光通信', '光模块'),
    ('AI服务器', 'AI服务器'), ('HBM/存储芯片', '存储'), ('液冷散热', '散热/液冷'),
    ('先进封装', '先进封装(CoWoS)'), ('算力租赁', '算力平台'), ('IDC', '数据中心'),
    ('智算中心运营', '智算中心'), ('算力调度平台', '算力调度'),
    ('DPU/智能网卡', '高速互联/DPU'), ('大模型', '大模型'), ('AI应用', 'AI应用'),
    ('AI Agent', 'AI Agent'), ('数据标注/数据服务', '数据要素/数据训练')
]
sector_ids = {}
for sname, segname in sectors:
    cur.execute("INSERT INTO sectors (name, segment_id) VALUES (%s, %s) RETURNING id", (sname, seg_ids[segname]))
    sector_ids[sname] = cur.fetchone()[0]

stocks = [
    ('688256', '寒武纪', 'AI芯片', '核心龙头'), ('688041', '海光信息', 'AI芯片', '核心龙头'),
    ('300474', '景嘉微', 'GPU', '核心龙头'), ('688795', '摩尔线程', 'GPU', '核心龙头'),
    ('300308', '中际旭创', '光通信', '核心龙头'), ('300394', '天孚通信', '光通信', '核心龙头'), ('300502', '新易盛', '光通信', '核心龙头'),
    ('000977', '浪潮信息', 'AI服务器', '核心龙头'), ('603019', '中科曙光', 'AI服务器', '核心龙头'), ('000938', '紫光股份', 'AI服务器', '核心龙头'),
    ('603986', '兆易创新', 'HBM/存储芯片', '核心龙头'), ('688525', '佰维存储', 'HBM/存储芯片', '核心龙头'),
    ('002837', '英维克', '液冷散热', '核心龙头'), ('300499', '高澜股份', '液冷散热', '核心龙头'),
    ('600584', '长电科技', '先进封装', '核心龙头'), ('002156', '通富微电', '先进封装', '核心龙头'),
    ('002929', '润建股份', '算力租赁', '核心龙头'), ('300846', '首都在线', '算力租赁', '核心龙头'),
    ('GDS', '万国数据', 'IDC', '核心龙头'), ('600845', '宝信软件', 'IDC', '核心龙头'), ('603881', '数据港', 'IDC', '核心龙头'),
    ('688041', '海光信息', '智算中心运营', '核心龙头'), ('603019', '中科曙光', '智算中心运营', '核心龙头'),
    ('603019', '中科曙光', '算力调度平台', '核心龙头'), ('300846', '首都在线', '算力调度平台', '一般关联'),
    ('300799', '左江科技', 'DPU/智能网卡', '一般关联'),
    ('002230', '科大讯飞', '大模型', '核心龙头'), ('00020.HK', '商汤-W', '大模型', '核心龙头'),
    ('688111', '金山办公', 'AI应用', '核心龙头'), ('300624', '万兴科技', 'AI应用', '一般关联'),
    ('300229', '拓尔思', 'AI Agent', '核心龙头'), ('06682.HK', '第四范式', 'AI Agent', '一般关联'),
    ('688787', '海天瑞声', '数据标注/数据服务', '核心龙头'), ('300229', '拓尔思', '数据标注/数据服务', '核心龙头')
]
for code, name, sname, rel in stocks:
    cur.execute("INSERT INTO stocks (code, name, sector_id, relevance) VALUES (%s, %s, %s, %s)", (code, name, sector_ids[sname], rel))

print("AI算力导入成功！")
cur.close(); conn.close()
